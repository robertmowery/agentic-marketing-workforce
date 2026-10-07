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

"""Runs Part 1 builds against the same brief and saves what happened.

Usage:
    python run_part1.py [BUILD ...] [TRIALS]

    python run_part1.py graph 3          # three trials of the graph build
    python run_part1.py                  # one trial of every build

Environment:
    RUN_TIMEOUT_S   Seconds before a run is abandoned (default 150).
    RESULT_SUFFIX   Appended to the results file name, for example "_180s".
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from workforce import cast, harness
from workforce.topologies import coordinator, graph, hybrid, legacy

RESULTS_DIR = Path(__file__).parent / "results"

# Each entry returns the keyword arguments for harness.run: an agent-rooted
# build passes ``agent``, a graph-rooted build passes ``node``.
BUILDS: dict[str, Callable[[], dict[str, Any]]] = {
    "coordinator": lambda: {"agent": coordinator.build()},
    "coordinator_guarded": lambda: {"agent": coordinator.build(guarded=True)},
    "graph": lambda: {"node": graph.build()},
    "graph_sequential": lambda: {"node": graph.build(parallel=False)},
    "hybrid": lambda: {"agent": hybrid.build()},
    "legacy": lambda: {"agent": legacy.build()},
}


def summarize(build: str, trial: int, rec: harness.RunRecord) -> dict[str, Any]:
    """Flatten a run record into the JSON row saved under ``results/``."""
    return {
        "build": build,
        "trial": trial,
        "seconds": round(rec.seconds, 1),
        "model_calls": rec.model_calls,
        "tokens": rec.total_tokens,
        "input_tokens": rec.input_tokens,
        "output_tokens": rec.output_tokens,
        "order": rec.order,
        "has_draft": "draft" in rec.state,
        "has_verdict": "verdict" in rec.state,
        "timed_out": rec.timed_out,
        "trace": rec.trace,
        "warnings": rec.warnings,
        "spans": {
            author: [round(first, 1), round(last, 1)] for author, (first, last) in rec.spans.items()
        },
        "final": rec.final_text[:300],
    }


async def main(names: list[str], trials: int) -> None:
    """Run each named build ``trials`` times, one after another."""
    rows: list[dict[str, Any]] = []
    for name in names:
        for trial in range(trials):
            try:
                rec = await harness.run(name, message=cast.BRIEF, **BUILDS[name]())
                rows.append(summarize(name, trial, rec))
            except Exception as exc:  # noqa: BLE001 - a failed build is a finding, so record it
                rows.append(
                    {"build": name, "trial": trial, "error": f"{type(exc).__name__}: {exc}"[:600]}
                )
            print(json.dumps(rows[-1]), flush=True)

    RESULTS_DIR.mkdir(exist_ok=True)
    suffix = os.environ.get("RESULT_SUFFIX", "")
    out_path = RESULTS_DIR / f"part1_{'_'.join(names)}{suffix}.json"
    out_path.write_text(json.dumps(rows, indent=1))


def parse_args(argv: list[str]) -> tuple[list[str], int]:
    """Split arguments into build names and an optional trial count."""
    names = [arg for arg in argv if not arg.isdigit()] or list(BUILDS)
    unknown = [name for name in names if name not in BUILDS]
    if unknown:
        raise SystemExit(
            f"Unknown build(s): {', '.join(unknown)}. Choose from: {', '.join(BUILDS)}"
        )
    trials = next((int(arg) for arg in argv if arg.isdigit()), 1)
    return names, trials


if __name__ == "__main__":
    asyncio.run(main(*parse_args(sys.argv[1:])))
