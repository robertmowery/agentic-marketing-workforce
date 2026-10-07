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

"""Claims the Part 3 articles make about loops in an ADK graph, checked without a model call."""

import asyncio
from typing import Any

from google.adk.agents.context import Context
from google.adk.events import Event, EventActions
from google.adk.runners import InMemoryRunner
from google.adk.workflow import START, FunctionNode, JoinNode, Workflow
from google.genai import types

from workforce.review import judge, loop


def _write(ctx: Context) -> str:
    ctx.state["rounds"] = ctx.state.get("rounds", 0) + 1
    return f"draft {ctx.state['rounds']}"


def _publish(ctx: Context) -> str:
    ctx.state["published"] = True
    return "published"


def _review_loop(approve_on_round: int | None) -> Workflow:
    """Writer and judge in a cycle. ``None`` builds a judge that never approves."""

    def judge_node(ctx: Context) -> Event:
        approved = approve_on_round is not None and ctx.state.get("rounds", 0) >= approve_on_round
        return Event(
            output="verdict", actions=EventActions(route="approve" if approved else "revise")
        )

    writer = FunctionNode(func=_write, name="writer")
    reviewer = FunctionNode(func=judge_node, name="judge")
    done = FunctionNode(func=_publish, name="publish")
    return Workflow(
        name="loop",
        edges=[(START, writer, reviewer), (reviewer, {"revise": writer, "approve": done})],
    )


async def _run(workflow: Workflow, give_up_after: float) -> tuple[bool, dict[str, Any]]:
    """Run a workflow and return (finished on its own, final state)."""
    runner = InMemoryRunner(node=workflow, app_name="t")
    session = await runner.session_service.create_session(app_name="t", user_id="u")
    message = types.Content(role="user", parts=[types.Part(text="go")])

    async def consume() -> None:
        async for _ in runner.run_async(user_id="u", session_id=session.id, new_message=message):
            pass

    finished = True
    try:
        await asyncio.wait_for(consume(), give_up_after)
    except asyncio.TimeoutError:
        finished = False
    final = await runner.session_service.get_session(
        app_name="t", user_id="u", session_id=session.id
    )
    assert final is not None
    return finished, dict(final.state)


def test_a_cycle_is_allowed_and_ends_when_the_judge_approves() -> None:
    finished, state = asyncio.run(_run(_review_loop(approve_on_round=3), give_up_after=5))
    assert finished
    assert state["rounds"] == 3
    assert state["published"] is True


def test_a_judge_that_never_approves_loops_until_something_outside_stops_it() -> None:
    finished, state = asyncio.run(_run(_review_loop(approve_on_round=None), give_up_after=1))
    assert not finished
    # No built-in limit stepped in. With no model to wait for, it spins fast.
    assert state["rounds"] > 50
    assert "published" not in state


def test_a_join_waiting_on_a_branch_that_was_not_taken_ends_quietly() -> None:
    def route_to_a() -> Event:
        return Event(output="x", actions=EventActions(route="a"))

    router = FunctionNode(func=route_to_a, name="router")
    branch_a = FunctionNode(func=lambda: "a done", name="a")
    branch_b = FunctionNode(func=lambda: "b done", name="b")
    join = JoinNode(name="join")
    done = FunctionNode(func=_publish, name="publish")
    workflow = Workflow(
        name="skipped_branch",
        edges=[
            (START, router),
            (router, {"a": branch_a, "b": branch_b}),
            (branch_a, join),
            (branch_b, join),
            (join, done),
        ],
    )
    finished, state = asyncio.run(_run(workflow, give_up_after=5))
    # It does not hang and it does not raise. It stops, and the work after the
    # join never happens.
    assert finished
    assert "published" not in state


def test_review_loop_builds_in_every_configuration() -> None:
    loop.build(conflict=False)
    loop.build(conflict=True)
    loop.build(conflict=True, max_rounds=3)
    loop.build(legal_outranks_brand=True)


def test_the_two_rubrics_really_do_contradict() -> None:
    assert "including the warranty" in loop.BRAND_NEEDS_EVERY_FACT
    assert "mentions a" in loop.LEGAL_RULE and "warranty" in loop.LEGAL_RULE
    assert any("warranty" in fact for fact in loop.APPROVED_FACTS)


def test_code_check_catches_exactly_the_faults_code_can_see() -> None:
    results = {name: judge.code_check(draft)["passed"] for name, (draft, _) in judge.DRAFTS.items()}
    assert results == {
        "clean": True,
        "hype": False,
        "unapproved_claim": False,
        # A missing call to action is a judgment call. Code passes it.
        "no_call_to_action": True,
    }
