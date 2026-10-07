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

"""The same pipeline on the template agents ADK 2.x deprecates.

Kept for comparison: they still run in 2.11 and remain the only way to nest
a fixed pipeline under an LLM coordinator as a sub-agent.
"""

import warnings

from google.adk.agents import BaseAgent

from workforce import cast
from workforce.topologies.graph import RESEARCH_FROM_STATE


def build() -> BaseAgent:
    """Build the pipeline from ``SequentialAgent`` and ``ParallelAgent``."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from google.adk.agents import ParallelAgent, SequentialAgent

    research = ParallelAgent(name="research", sub_agents=[*cast.researchers(mode=None)])
    writer = cast.copywriter(mode=None, instruction_extra=RESEARCH_FROM_STATE)
    judge = cast.brand_judge(mode=None, instruction_extra="Draft: {draft}")
    return SequentialAgent(name="campaign_pipeline", sub_agents=[research, writer, judge])
