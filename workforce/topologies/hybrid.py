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

"""Topology C: hybrid. The model handles the conversation; the graph does the work.

A Workflow cannot be an Agent's sub-agent in ADK 2.11, so the pipeline is
handed to the Director as a tool.
"""

from google.adk.agents import Agent

from workforce import cast
from workforce.topologies import graph


def build() -> Agent:
    """Build the hybrid: a conversational Director with the pipeline as its one tool."""
    return Agent(
        name="campaign_director",
        model=cast.MODEL,
        generate_content_config=cast.RETRY,
        description="Front door for marketers. Hands briefs to the pipeline.",
        instruction=(
            "You are the front door for marketers at Corvane Outdoor. When"
            " you receive a campaign brief, call the campaign_pipeline tool"
            " with the full brief. Then report the draft and the verdict."
            " Do not write copy yourself."
        ),
        # ADK accepts a Workflow with an input schema as a tool; its type hints do not say so yet.
        tools=[graph.build(as_tool=True)],  # type: ignore[list-item]
    )
