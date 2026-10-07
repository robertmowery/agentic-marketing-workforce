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

"""Claims the Part 1 articles make about ADK 2.11.0, checked without a model call."""

import asyncio
import importlib.metadata
import warnings
from collections.abc import AsyncGenerator
from typing import Any, get_args

import google.adk.agents as adk_agents
import pytest
from google.adk.agents import Agent, BaseAgent
from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.adk.workflow import START, Workflow
from google.genai import types
from pydantic import ValidationError

from workforce import cast
from workforce.topologies import coordinator, graph, hybrid, legacy


def test_adk_version_is_pinned() -> None:
    assert importlib.metadata.version("google-adk") == "2.11.0"


@pytest.mark.parametrize("cls_name", ["SequentialAgent", "ParallelAgent", "LoopAgent"])
def test_template_agents_still_work_but_warn_of_removal(cls_name: str) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        getattr(adk_agents, cls_name)(name="x")
    messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
    assert any("deprecated in favor of Workflow and will be removed" in m for m in messages)
    # The warning itself admits the migration gap.
    assert any("Workflow cannot yet be used as an LlmAgent sub-agent" in m for m in messages)


def test_workflow_cannot_be_a_sub_agent() -> None:
    workflow = Workflow(name="wf", edges=[(START, cast.copywriter(mode=None))])
    with pytest.raises(ValidationError):
        Agent(name="director", model=cast.MODEL, sub_agents=[workflow])  # type: ignore[list-item]


def test_workflow_as_tool_needs_an_input_schema() -> None:
    with pytest.raises(ValidationError, match="input_schema"):
        Agent(name="director", model=cast.MODEL, tools=[graph.build(as_tool=False)])  # type: ignore[list-item]
    Agent(name="director", model=cast.MODEL, tools=[graph.build(as_tool=True)])  # type: ignore[list-item]


def test_custom_base_agent_override_still_executes() -> None:
    class Mine(BaseAgent):
        async def _run_async_impl(self, ctx: Any) -> AsyncGenerator[Event, None]:
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text="custom override ran")]),
            )

    async def collect_replies() -> list[str | None]:
        runner = InMemoryRunner(agent=Mine(name="mine"), app_name="t")
        session = await runner.session_service.create_session(app_name="t", user_id="u")
        message = types.Content(role="user", parts=[types.Part(text="hi")])
        return [
            event.content.parts[0].text
            async for event in runner.run_async(
                user_id="u", session_id=session.id, new_message=message
            )
            if event.content and event.content.parts
        ]

    assert asyncio.run(collect_replies()) == ["custom override ran"]


def test_every_topology_builds() -> None:
    coordinator.build()
    coordinator.build(guarded=True)
    graph.build()
    graph.build(parallel=False)
    hybrid.build()
    legacy.build()


def test_guarded_coordinator_blocks_every_specialist_transfer() -> None:
    for specialist in coordinator.build(guarded=True).sub_agents:
        assert isinstance(specialist, Agent)
        assert specialist.disallow_transfer_to_parent is True
        assert specialist.disallow_transfer_to_peers is True
    for specialist in coordinator.build().sub_agents:
        assert isinstance(specialist, Agent)
        assert specialist.disallow_transfer_to_parent is False
        assert specialist.disallow_transfer_to_peers is False


def test_an_agent_can_have_only_one_parent() -> None:
    writer = cast.copywriter()
    Agent(name="first", model=cast.MODEL, sub_agents=[writer])
    with pytest.raises(ValueError, match="already has a parent"):
        Agent(name="second", model=cast.MODEL, sub_agents=[writer])


def test_default_mode_depends_on_where_the_agent_sits() -> None:
    # Unset on construction; ADK resolves it at run time from the agent's position.
    assert Agent(name="a", model=cast.MODEL).mode is None
    mode_literal = get_args(Agent.model_fields["mode"].annotation)[0]
    assert set(get_args(mode_literal)) == {"chat", "task", "single_turn"}
