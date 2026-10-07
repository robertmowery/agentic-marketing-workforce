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

"""Topology B: the graph decides. Order is fixed in code; no model picks the next step."""

from typing import Any

from google.adk.workflow import START, JoinNode, Workflow

from workforce import cast

# In a straight chain there is no join, so each node receives only the output
# of the node before it. The writer reads the research from session state.
RESEARCH_FROM_STATE = "Research: audience={audience} competitors={competitors} product={product}"


def build(as_tool: bool = False, parallel: bool = True) -> Workflow:
    """Build the campaign pipeline as a ``Workflow``.

    Args:
        as_tool: Declare an input schema and description so an agent can call
            the workflow as a tool. ADK rejects a workflow tool without one.
        parallel: Fan out to the three researchers and join. When false, run
            them one after another.
    """
    r1, r2, r3 = cast.researchers(mode=None)
    join = JoinNode(name="gather_research")
    writer = cast.copywriter(mode=None, instruction_extra="" if parallel else RESEARCH_FROM_STATE)
    judge = cast.brand_judge(mode=None)

    tool_kwargs: dict[str, Any] = {}
    if as_tool:
        tool_kwargs = {
            "input_schema": cast.Brief,
            "description": "Runs research, drafting, and brand review for a campaign brief.",
        }

    if parallel:
        # A nested tuple is a fan-out; the JoinNode waits for all three.
        edge: tuple[Any, ...] = (START, (r1, r2, r3), join, writer, judge)
    else:
        edge = (START, r1, r2, r3, writer, judge)

    return Workflow(name="campaign_pipeline", edges=[edge], **tool_kwargs)
