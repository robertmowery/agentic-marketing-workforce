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

"""Runs any topology against the same brief and records what happened."""

from __future__ import annotations

import asyncio
import os
import time
import warnings
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.genai import types

load_dotenv()

USER_ID = "u"
TRANSFER_TOOL = "transfer_to_agent"

# Seconds before a run is abandoned. Nothing inside a runaway build stops it,
# so the harness has to.
TIMEOUT_S = float(os.environ.get("RUN_TIMEOUT_S", "150"))


@dataclass
class RunRecord:
    """Everything measured about one run of one build."""

    name: str
    seconds: float = 0.0
    model_calls: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    # Includes thinking tokens, which bill as output.
    output_tokens: int = 0
    # Event authors, collapsed so consecutive events by one author count once.
    order: list[str] = field(default_factory=list)
    final_text: str = ""
    state: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    # One line per event.
    trace: list[str] = field(default_factory=list)
    timed_out: bool = False
    # Author -> (first seen, last seen), in seconds since the brief arrived.
    spans: dict[str, tuple[float, float]] = field(default_factory=dict)


def _describe_calls(event: Event) -> list[str]:
    """Name each function call in an event, with the target of any transfer."""
    described = []
    for call in event.get_function_calls():
        label = call.name or "?"
        if call.name == TRANSFER_TOOL:
            label += f"->{(call.args or {}).get('agent_name')}"
        described.append(label)
    return described


def _record_event(rec: RunRecord, event: Event, now: float) -> None:
    """Fold one event into the run record."""
    author = event.author or "?"
    partial = bool(getattr(event, "partial", False))

    if not rec.order or rec.order[-1] != author:
        rec.order.append(author)
    first_seen, _ = rec.spans.get(author, (now, now))
    rec.spans[author] = (first_seen, now)

    calls = _describe_calls(event)
    line = f"{now:6.1f}s {author}"
    if calls:
        line += f" calls={calls}"
    if partial:
        line += " partial"
    rec.trace.append(line)

    usage = getattr(event, "usage_metadata", None)
    if usage is not None and not partial:
        rec.model_calls += 1
        rec.total_tokens += usage.total_token_count or 0
        rec.input_tokens += usage.prompt_token_count or 0
        rec.output_tokens += (usage.candidates_token_count or 0) + (
            getattr(usage, "thoughts_token_count", 0) or 0
        )

    if event.content and event.content.parts:
        text = "".join(
            part.text or "" for part in event.content.parts if not getattr(part, "thought", False)
        )
        if text.strip():
            rec.final_text = text


async def run(
    name: str,
    *,
    agent: BaseAgent | None = None,
    node: Any = None,
    message: str,
) -> RunRecord:
    """Run one build against one message and return what happened.

    Args:
        name: Label for the run; also used as the ADK app name.
        agent: The root agent, for builds rooted in an agent.
        node: The root workflow, for builds rooted in a graph.
        message: The user message, normally ``cast.BRIEF``.

    Returns:
        A ``RunRecord``. A run that exceeds ``TIMEOUT_S`` is returned with
        ``timed_out`` set, not raised.
    """
    rec = RunRecord(name=name)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        runner = InMemoryRunner(agent=agent, node=node, app_name=name)
        session = await runner.session_service.create_session(app_name=name, user_id=USER_ID)
        started = time.perf_counter()

        async def consume() -> None:
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=session.id,
                new_message=types.Content(role="user", parts=[types.Part(text=message)]),
            ):
                _record_event(rec, event, time.perf_counter() - started)

        try:
            await asyncio.wait_for(consume(), TIMEOUT_S)
        except asyncio.TimeoutError:
            rec.timed_out = True
        rec.seconds = time.perf_counter() - started

        final = await runner.session_service.get_session(
            app_name=name, user_id=USER_ID, session_id=session.id
        )
        rec.state = dict(final.state) if final else {}

    rec.warnings = sorted(
        {str(w.message)[:200] for w in caught if "deprecat" in str(w.message).lower()}
    )
    return rec
