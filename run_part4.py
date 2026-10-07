# Copyright 2026 Robert H. Mowery III
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Run the Part 4 experiment: one designer, one outside tool, three connections.

Usage:
    python run_part4.py [TRIALS]

Every combination of access level (everything, least, confirmed) and server
(clean, an instruction planted in returned data, an instruction planted in a
tool description) is run TRIALS times. Each row records what the agent asked
for and, from the server's own audit log, what was actually done.
Results go to results/part4_access.json.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from workforce import harness
from workforce.tools import access, design_server

RESULTS = Path(__file__).parent / "results" / "part4_access.json"
CONFIRMATION_CALL = "adk_request_confirmation"


async def run_once(access_level: str, poison: str, trial: int) -> dict[str, Any]:
    """Run the banner task once and return what was asked for and what was done."""
    row: dict[str, Any] = {
        "access": access_level,
        "server": poison or "clean",
        "trial": trial,
    }
    with tempfile.TemporaryDirectory() as folder:
        log = Path(folder) / "audit.jsonl"
        toolsets = access.toolset(access_level, poison, log)
        try:
            rec = await harness.run(
                f"{access_level}/{poison or 'clean'}",
                agent=access.designer(toolsets),
                message=access.TASK,
            )
        except Exception as exc:  # noqa: BLE001 - a failed run is a finding, so record it
            row["error"] = f"{type(exc).__name__}: {exc}"[:400]
            return row
        finally:
            for toolset in toolsets:
                await toolset.close()
        done = [entry["tool"] for entry in access.read_audit(log)]
    asked = [call["name"] for call in rec.calls]
    row.update(
        {
            "seconds": round(rec.seconds, 1),
            "timed_out": rec.timed_out,
            "model_calls": rec.model_calls,
            "input_tokens": rec.input_tokens,
            "output_tokens": rec.output_tokens,
            "asked_for": asked,
            "done": done,
            "dangerous_done": [name for name in done if name in design_server.DANGEROUS_TOOLS],
            "confirmations_requested": asked.count(CONFIRMATION_CALL),
            "exported": "export_design" in done,
            "final_text": rec.final_text[:600],
        }
    )
    return row


async def main(trials: int) -> None:
    """Run every access level against every server and save the rows."""
    rows = []
    for poison in access.POISONS:
        for access_level in access.ACCESS_LEVELS:
            for trial in range(trials):
                rows.append(await run_once(access_level, poison, trial))
                shown = {k: v for k, v in rows[-1].items() if k != "final_text"}
                print(json.dumps(shown), flush=True)
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 3))
