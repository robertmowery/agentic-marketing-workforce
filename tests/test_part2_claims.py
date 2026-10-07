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

"""Claims the Part 2 articles make about sessions and state, checked without a model call."""

import asyncio
from pathlib import Path
from typing import Any

from google.adk.events import Event, EventActions
from google.adk.sessions import BaseSessionService, DatabaseSessionService, InMemorySessionService

from workforce.context import handoff, window
from workforce.topologies import graph

APP = "campaigns"

EVERY_SCOPE = {
    "campaign": "TrailLock 2 launch",
    "user:house_rules": "never mention the warranty",
    "app:brand_voice": "plain, direct, no hype",
    "temp:scratch": "working notes",
}


async def _write(service: BaseSessionService, session: Any, delta: dict[str, str]) -> None:
    """Write to state the supported way: as an event carrying a state delta."""
    event = Event(author="system", invocation_id="test", actions=EventActions(state_delta=delta))
    await service.append_event(session, event)


async def _state(service: BaseSessionService, user_id: str, session_id: str) -> dict[str, Any]:
    session = await service.get_session(app_name=APP, user_id=user_id, session_id=session_id)
    assert session is not None
    return dict(session.state)


def test_in_memory_sessions_do_not_survive_a_new_service() -> None:
    async def scenario() -> Any:
        first = InMemorySessionService()
        session = await first.create_session(app_name=APP, user_id="dana", session_id="s1")
        await _write(first, session, {"campaign": "TrailLock 2 launch"})
        # A restart, a second replica, or a scale-to-zero all look like this.
        second = InMemorySessionService()
        return await second.get_session(app_name=APP, user_id="dana", session_id="s1")

    assert asyncio.run(scenario()) is None


def test_database_sessions_survive_a_new_service(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'sessions.db'}"

    async def scenario() -> dict[str, Any]:
        first = DatabaseSessionService(db_url=url)
        session = await first.create_session(app_name=APP, user_id="dana", session_id="s1")
        await _write(first, session, {"campaign": "TrailLock 2 launch"})
        second = DatabaseSessionService(db_url=url)
        return await _state(second, "dana", "s1")

    assert asyncio.run(scenario()) == {"campaign": "TrailLock 2 launch"}


def test_each_state_prefix_has_a_different_reach() -> None:
    async def scenario() -> dict[str, dict[str, Any]]:
        service = InMemorySessionService()
        session = await service.create_session(app_name=APP, user_id="dana", session_id="s1")
        await _write(service, session, EVERY_SCOPE)
        await service.create_session(app_name=APP, user_id="dana", session_id="s2")
        await service.create_session(app_name=APP, user_id="lee", session_id="s3")
        return {
            "same_session": await _state(service, "dana", "s1"),
            "same_user_new_session": await _state(service, "dana", "s2"),
            "different_user": await _state(service, "lee", "s3"),
        }

    seen = asyncio.run(scenario())
    # No prefix: this session only. "temp:" is never stored at all.
    assert seen["same_session"] == {
        "campaign": "TrailLock 2 launch",
        "user:house_rules": "never mention the warranty",
        "app:brand_voice": "plain, direct, no hype",
    }
    # "user:" follows the user into a new session.
    assert seen["same_user_new_session"] == {
        "user:house_rules": "never mention the warranty",
        "app:brand_voice": "plain, direct, no hype",
    }
    # "app:" is shared by every user of the app.
    assert seen["different_user"] == {"app:brand_voice": "plain, direct, no hype"}


def test_state_set_directly_on_a_fetched_session_is_not_saved() -> None:
    async def scenario() -> dict[str, Any]:
        service = InMemorySessionService()
        await service.create_session(app_name=APP, user_id="dana", session_id="s1")
        fetched = await service.get_session(app_name=APP, user_id="dana", session_id="s1")
        assert fetched is not None
        fetched.state["campaign"] = "set without an event"
        return await _state(service, "dana", "s1")

    assert asyncio.run(scenario()) == {}


def test_house_rules_are_read_from_user_scoped_state() -> None:
    assert handoff.HOUSE_RULES_KEY.startswith("user:")
    # The trailing "?" keeps a user with no saved rules from raising a missing-key error.
    assert "{user:house_rules?}" in graph.HOUSE_RULES_FROM_STATE


def test_window_script_states_the_fact_first_and_asks_for_it_last() -> None:
    script = window.turns()
    assert window.PO_NUMBER in script[0]
    assert window.PO_NUMBER not in " ".join(script[1:])
    assert len(script) == len(window.FILLER_TOPICS) + 2


def test_compaction_is_off_unless_configured() -> None:
    assert window.build_app("plain").events_compaction_config is None
    configured = window.build_app("compacted", compaction_interval=3).events_compaction_config
    assert configured is not None
    assert configured.compaction_interval == 3
