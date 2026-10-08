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

"""Part 6: a run that stops for a person, and what happens after they answer.

Part 4 put a confirmation on the dangerous tools and stopped there. This
module answers the confirmation and lets the run continue, with two stand-ins
for the person:

``rubber_stamp``   approves everything it is shown.
``reads_request``  approves a dangerous call only if the marketer's request
                   asked for it (the same rule as the code guard in guard.py).

Neither is a real person. They are the two ends of how a real person behaves
at the hundredth approval of the day.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types

from workforce.trust import guard

CONFIRMATION_CALL = "adk_request_confirmation"
APPROVERS = ("rubber_stamp", "reads_request")
MAX_PAUSES = 8

Approver = Callable[[str, dict[str, Any], str], bool]


def rubber_stamp(tool_name: str, args: dict[str, Any], request: str) -> bool:
    """Approve whatever is asked."""
    del tool_name, args, request
    return True


def reads_request(tool_name: str, args: dict[str, Any], request: str) -> bool:
    """Approve only what the marketer's request asked for."""
    del args
    return guard.allowed(tool_name, request)


@dataclass
class ApprovalRun:
    """What happened in one run that could stop for approval."""

    asked: list[dict[str, Any]] = field(default_factory=list)  # each approval request
    final_text: str = ""
    pauses: int = 0
    timed_out: bool = False


def _pending(events: list[Any]) -> list[Any]:
    """Return the confirmation requests in a batch of events."""
    calls: list[Any] = []
    for event in events:
        calls.extend(c for c in event.get_function_calls() if c.name == CONFIRMATION_CALL)
    return calls


async def run(agent: Agent, request: str, approver: Approver, limit_s: float = 150) -> ApprovalRun:
    """Run an agent, answering each approval request with ``approver`` until it finishes."""
    runner = InMemoryRunner(agent=agent, app_name="approval")
    session = await runner.session_service.create_session(app_name="approval", user_id="u")
    result = ApprovalRun()
    message = types.Content(role="user", parts=[types.Part(text=request)])

    async def turn(content: types.Content) -> list[Any]:
        events = []
        async for event in runner.run_async(
            user_id="u", session_id=session.id, new_message=content
        ):
            events.append(event)
            if event.is_final_response() and event.content and event.content.parts:
                text = "".join(part.text or "" for part in event.content.parts)
                result.final_text = text or result.final_text
        return events

    async def drive() -> None:
        nonlocal message
        for _ in range(MAX_PAUSES + 1):
            pending = _pending(await turn(message))
            if not pending:
                return
            result.pauses += 1
            answers = []
            for call in pending:
                original = (call.args or {}).get("originalFunctionCall", {})
                name, args = original.get("name", ""), original.get("args", {})
                approved = approver(name, args, request)
                hint = ((call.args or {}).get("toolConfirmation") or {}).get("hint", "")
                result.asked.append(
                    {"tool": name, "args": args, "approved": approved, "shown": hint}
                )
                answers.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=call.id, name=CONFIRMATION_CALL, response={"confirmed": approved}
                        )
                    )
                )
            message = types.Content(role="user", parts=answers)

    try:
        await asyncio.wait_for(drive(), limit_s)
    except asyncio.TimeoutError:
        result.timed_out = True
    return result
