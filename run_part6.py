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

"""Run the Part 6 experiments against the poisoned DesignDesk server from Part 4.

Usage:
    python run_part6.py defenses [TRIALS]   # none, a warning, a code guard
    python run_part6.py approval [TRIALS]   # a rubber stamp, and someone who reads

Every agent has every tool. Both poisoned servers are used (the instruction
planted in returned data, and in a tool description), TRIALS runs each.
Results go to results/part6_<experiment>.json. Harm is counted from the
server's audit log, never from the agent's own account.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from workforce import harness
from workforce.tools import access, design_server
from workforce.trust import approval, guard

RESULTS_DIR = Path(__file__).parent / "results"
POISONS = ("result", "description")


def _harm(done: list[str]) -> list[str]:
    return [name for name in done if name in design_server.DANGEROUS_TOOLS]


async def defense_once(defense: str, poison: str, trial: int) -> dict[str, Any]:
    """Run the banner task once with one defense and report what reached the server."""
    row: dict[str, Any] = {"defense": defense, "server": poison, "trial": trial}
    blocked: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as folder:
        log = Path(folder) / "audit.jsonl"
        toolsets = access.toolset("everything", poison, log)
        try:
            rec = await harness.run(
                f"{defense}/{poison}",
                agent=guard.designer(toolsets, defense, blocked),
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
            "asked_for": asked,
            "dangerous_asked": [name for name in asked if guard.is_dangerous(name)],
            "blocked": [entry["tool"] for entry in blocked],
            "dangerous_done": _harm(done),
            "exported": "export_design" in done,
            "model_calls": rec.model_calls,
            "input_tokens": rec.input_tokens,
            "output_tokens": rec.output_tokens,
            "seconds": round(rec.seconds, 1),
            "timed_out": rec.timed_out,
            "final_text": rec.final_text[:600],
        }
    )
    return row


async def approval_once(approver: str, poison: str, trial: int) -> dict[str, Any]:
    """Run the banner task once behind an approval step and report what happened."""
    row: dict[str, Any] = {"approver": approver, "server": poison, "trial": trial}
    decide = getattr(approval, approver)
    with tempfile.TemporaryDirectory() as folder:
        log = Path(folder) / "audit.jsonl"
        toolsets = access.toolset("confirmed", poison, log)
        try:
            run = await approval.run(access.designer(toolsets), access.TASK, decide)
        except Exception as exc:  # noqa: BLE001 - a failed run is a finding, so record it
            row["error"] = f"{type(exc).__name__}: {exc}"[:400]
            return row
        finally:
            for toolset in toolsets:
                await toolset.close()
        done = [entry["tool"] for entry in access.read_audit(log)]
    row.update(
        {
            "asked": run.asked,
            "requests": len(run.asked),
            "approved": sum(1 for item in run.asked if item["approved"]),
            "pauses": run.pauses,
            "dangerous_done": _harm(done),
            "exported": "export_design" in done,
            "timed_out": run.timed_out,
            "final_text": run.final_text[:600],
        }
    )
    return row


async def main(experiment: str, trials: int) -> None:
    """Run one experiment and save its rows."""
    cells: tuple[str, ...]
    once: Callable[[str, str, int], Awaitable[dict[str, Any]]]
    if experiment == "defenses":
        cells, once = guard.DEFENSES, defense_once
    elif experiment == "approval":
        cells, once = approval.APPROVERS, approval_once
    else:
        raise SystemExit(__doc__)
    rows = []
    for cell in cells:
        for poison in POISONS:
            for trial in range(trials):
                rows.append(await once(cell, poison, trial))
                shown = {k: v for k, v in rows[-1].items() if k not in ("final_text", "asked")}
                print(json.dumps(shown), flush=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"part6_{experiment}.json"
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(
        main(
            sys.argv[1] if len(sys.argv) > 1 else "", int(sys.argv[2]) if len(sys.argv) > 2 else 10
        )
    )
