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
    python run_part5.py [TRIALS] [local|vertex|grounded]

Each build (no library, library, library with dates and rules) is asked each
question TRIALS times. Every reply is graded in code against the library.

``local`` (the default) searches with the keyword search in library.py and
saves to results/part5_answers.json. ``vertex`` searches a Vertex AI Search
data store instead (create it first with
``python -m workforce.knowledge.vertex_search setup``) and saves to
results/part5_answers_vertex.json. The build with no library does not search,
so it is skipped on the second run.

``grounded`` runs one more build that has no search function of ours: ADK's
built-in VertexAiSearchTool on the same data store. It saves to
results/part5_answers_grounded.json.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from workforce import harness
from workforce.knowledge import answer

RESULTS = Path(__file__).parent / "results"


async def run_once(
    build: str, question: answer.Question, trial: int, search: str = "local"
) -> dict[str, Any]:
    """Ask one build one question and grade the reply."""
    row: dict[str, Any] = {
        "build": build,
        "question": question.key,
        "trial": trial,
        "search": search,
    }
    try:
        rec = await harness.run(
            f"{build}/{question.key}",
            agent=answer.build(build, "vertex" if search != "local" else "local"),
            message=question.text,
        )
    except Exception as exc:  # noqa: BLE001 - a failed run is a finding, so record it
        row["error"] = f"{type(exc).__name__}: {exc}"[:400]
        return row
    cited = rec.grounded_documents if build == answer.GROUNDED else None
    row.update(answer.grade(question, rec.final_text, cited))
    row.update(
        {
            "searches": [call["args"] for call in rec.calls if "search" in call["name"]]
            or [{"query": query} for query in rec.retrieval_queries],
            "seconds": round(rec.seconds, 1),
            "timed_out": rec.timed_out,
            "model_calls": rec.model_calls,
            "input_tokens": rec.input_tokens,
            "output_tokens": rec.output_tokens,
        }
    )
    return row


async def main(trials: int, search: str = "local") -> None:
    """Run every build against every question and save the rows."""
    builds: tuple[str, ...] = answer.BUILDS if search == "local" else answer.BUILDS[1:]
    if search == answer.GROUNDED:
        builds = (answer.GROUNDED,)
    name = "part5_answers.json" if search == "local" else f"part5_answers_{search}.json"
    rows = []
    for build in builds:
        for question in answer.QUESTIONS:
            for trial in range(trials):
                rows.append(await run_once(build, question, trial, search))
                print(json.dumps(rows[-1]), flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / name).write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(
        main(
            int(sys.argv[1]) if len(sys.argv) > 1 else 5,
            sys.argv[2] if len(sys.argv) > 2 else "local",
        )
    )
