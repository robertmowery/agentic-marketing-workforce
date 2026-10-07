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

"""Runs the Part 3 experiments that need a model and saves what happened.

Usage:
    python run_part3.py loops [TRIALS]    # review loops: plain, conflicting, capped, ranked
    python run_part3.py judge [TRIALS]    # the same four drafts scored repeatedly

Graph behavior that needs no model is in tests/test_part3_claims.py.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from workforce import cast, harness
from workforce.review import judge, loop

RESULTS_DIR = Path(__file__).parent / "results"

# name -> keyword arguments for loop.build
LOOP_BUILDS: dict[str, dict[str, Any]] = {
    "no_conflict": {"conflict": False},
    "conflict_uncapped": {"conflict": True},
    "conflict_capped_at_3": {"conflict": True, "max_rounds": 3},
    "legal_outranks_brand": {"legal_outranks_brand": True},
}


async def run_loops(trials: int) -> list[dict[str, Any]]:
    """Run each review loop and record how it ended and what it cost."""
    rows = []
    for name, kwargs in LOOP_BUILDS.items():
        for trial in range(trials):
            try:
                rec = await harness.run(name, node=loop.build(**kwargs), message=cast.BRIEF)
            except Exception as exc:  # noqa: BLE001 - a failed run is a finding, so record it
                error = f"{type(exc).__name__}: {exc}"[:400]
                rows.append({"experiment": "loops", "build": name, "trial": trial, "error": error})
                print(json.dumps(rows[-1]), flush=True)
                continue
            reviews = [line for line in rec.trace if "brand_judge" in line or "legal_rev" in line]
            drafts = [line for line in rec.trace if "copywriter" in line]
            row = {
                "experiment": "loops",
                "build": name,
                "trial": trial,
                "outcome": rec.state.get(loop.OUTCOME_KEY, "stopped by the harness timeout"),
                "failed_reviews": rec.state.get(loop.ROUNDS_KEY),
                "seconds": round(rec.seconds, 1),
                "timed_out": rec.timed_out,
                "model_calls": rec.model_calls,
                "input_tokens": rec.input_tokens,
                "output_tokens": rec.output_tokens,
                "drafts_written": len(drafts),
                "reviews_done": len(reviews),
                "verdict": rec.state.get("verdict"),
                "legal_verdict": rec.state.get("legal_verdict"),
                "draft": rec.state.get("draft"),
                "trace": rec.trace,
            }
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "trace"}), flush=True)
    return rows


async def run_judge(trials: int) -> list[dict[str, Any]]:
    """Score each fixed draft ``trials`` times with the brand judge, and once in code."""
    rows = []
    for name, (draft, fault) in judge.DRAFTS.items():
        for trial in range(trials):
            rec = await harness.run(
                f"judge_{name}", agent=loop.brand_reviewer(), message=judge.judge_request(draft)
            )
            verdict = loop.parse_reply(rec.final_text, cast.Verdict) or {}
            row = {
                "experiment": "judge",
                "draft": name,
                "planted_fault": fault,
                "trial": trial,
                "judge_passed": verdict.get("passed"),
                "judge_score": verdict.get("score"),
                "judge_fixes": verdict.get("fixes"),
                "reply_was_valid": bool(verdict),
                "code_check": judge.code_check(draft),
                "input_tokens": rec.input_tokens,
                "output_tokens": rec.output_tokens,
                "timed_out": rec.timed_out,
            }
            rows.append(row)
            print(json.dumps(row), flush=True)
    return rows


EXPERIMENTS = {"loops": run_loops, "judge": run_judge}


async def main(names: list[str], trials: int) -> None:
    """Run each named experiment and write one results file per experiment."""
    RESULTS_DIR.mkdir(exist_ok=True)
    suffix = os.environ.get("RESULT_SUFFIX", "")
    for name in names:
        rows = await EXPERIMENTS[name](trials)
        (RESULTS_DIR / f"part3_{name}{suffix}.json").write_text(json.dumps(rows, indent=1))


def parse_args(argv: list[str]) -> tuple[list[str], int]:
    """Split arguments into experiment names and an optional trial count."""
    names = [arg for arg in argv if not arg.isdigit()] or list(EXPERIMENTS)
    unknown = [name for name in names if name not in EXPERIMENTS]
    if unknown:
        raise SystemExit(
            f"Unknown experiment(s): {', '.join(unknown)}. Choose from: {', '.join(EXPERIMENTS)}"
        )
    trials = next((int(arg) for arg in argv if arg.isdigit()), 1)
    return names, trials


if __name__ == "__main__":
    asyncio.run(main(*parse_args(sys.argv[1:])))
