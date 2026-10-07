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

"""Run the Part 5 experiment: four questions, three ways to answer them.

Usage:
    python run_part5.py [TRIALS]

Each build (no library, library, library with dates and rules) is asked each
question TRIALS times. Every reply is graded in code against the library.
Results go to results/part5_answers.json.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from workforce import harness
from workforce.knowledge import answer

RESULTS = Path(__file__).parent / "results" / "part5_answers.json"


async def run_once(build: str, question: answer.Question, trial: int) -> dict[str, Any]:
    """Ask one build one question and grade the reply."""
    row: dict[str, Any] = {"build": build, "question": question.key, "trial": trial}
    try:
        rec = await harness.run(
            f"{build}/{question.key}", agent=answer.build(build), message=question.text
        )
    except Exception as exc:  # noqa: BLE001 - a failed run is a finding, so record it
        row["error"] = f"{type(exc).__name__}: {exc}"[:400]
        return row
    row.update(answer.grade(question, rec.final_text))
    row.update(
        {
            "searches": [call["args"] for call in rec.calls if "search" in call["name"]],
            "seconds": round(rec.seconds, 1),
            "timed_out": rec.timed_out,
            "model_calls": rec.model_calls,
            "input_tokens": rec.input_tokens,
            "output_tokens": rec.output_tokens,
        }
    )
    return row


async def main(trials: int) -> None:
    """Run every build against every question and save the rows."""
    rows = []
    for build in answer.BUILDS:
        for question in answer.QUESTIONS:
            for trial in range(trials):
                rows.append(await run_once(build, question, trial))
                print(json.dumps(rows[-1]), flush=True)
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 5))
