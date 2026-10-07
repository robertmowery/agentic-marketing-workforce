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

"""Topology A: the model decides. A coordinator reads the brief and delegates."""

from google.adk.agents import Agent

from workforce import cast


def build(guarded: bool = False) -> Agent:
    """Build the coordinator: one Director with five specialist sub-agents.

    Args:
        guarded: When true, specialists may not transfer the conversation to
            their parent or peers. This is the two-line fix for the runaway
            review loop.
    """
    specialists = [*cast.researchers(), cast.copywriter(), cast.brand_judge()]
    if guarded:
        # Specialists may only return their result; they cannot hand the
        # conversation to anyone else.
        for a in specialists:
            a.disallow_transfer_to_parent = True
            a.disallow_transfer_to_peers = True
    return Agent(
        name="campaign_director",
        model=cast.MODEL,
        generate_content_config=cast.RETRY,
        description="Runs a campaign from brief to judged draft.",
        instruction=(
            "You run campaign production. For every brief: delegate to all"
            " three researchers, then give their findings to the copywriter,"
            " then give the draft to the brand_judge. Report the draft and"
            " the verdict. Do not write copy yourself."
        ),
        sub_agents=[*specialists],
    )
