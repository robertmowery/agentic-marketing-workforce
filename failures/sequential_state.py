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

"""Reproduction: in a straight chain, the writer sees only the last node's output.

A fan-out ends in a JoinNode that hands the writer all three research results.
A sequential chain has no join, so each node receives only the output of the
node before it. Without reading research from session state, the copywriter
is given the product facts and nothing else: no audience, no competitors, and
not even the brief.

This calls the model. Run it from the repo root:

    python -m failures.sequential_state
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from google.adk.workflow import START, Workflow

from workforce import cast, harness

TRIALS = 2


def build_chain_without_state() -> Workflow:
    """Build the sequential pipeline with no state template on the writer."""
    r1, r2, r3 = cast.researchers(mode=None)
    writer = cast.copywriter(mode=None)
    judge = cast.brand_judge(mode=None)
    return Workflow(name="seq_no_template", edges=[(START, r1, r2, r3, writer, judge)])


def inspect_draft(rec: harness.RunRecord, trial: int) -> dict[str, Any]:
    """Report which research made it into the draft."""
    draft = json.dumps(rec.state.get("draft", ""))
    lowered = draft.lower()
    return {
        "trial": trial,
        "has_draft": "draft" in rec.state,
        "mentions_audience_pain": "theft" in lowered,
        "mentions_competitor": "RackMaster" in draft or "SummitHaul" in draft,
        "mentions_product_fact": "keyed-alike" in lowered or "20 minutes" in draft,
        "timed_out": rec.timed_out,
        "draft": draft[:500],
    }


async def main() -> None:
    """Run the chain and print what the writer was able to use."""
    for trial in range(TRIALS):
        rec = await harness.run(
            "seq_no_template", node=build_chain_without_state(), message=cast.BRIEF
        )
        print(json.dumps(inspect_draft(rec, trial)), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
