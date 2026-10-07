"""A revise-until-approved loop, with and without the things that make it end.

The graph is a cycle: a writer drafts, two reviewers judge, and a failed review
routes back to the writer. Brand review and legal review are separate agents
with separate rubrics, which is how it works in most companies and is exactly
how a loop ends up with no exit: each reviewer can be right and the pair can
still be impossible to satisfy.

Two design choices matter here.

LLM agents do not choose the route. Small function nodes ("gates") read each
reply, validate it, and emit the route, so every branch is a line of code.

The agents reply in JSON because they are asked to, not because a response
schema forces them to. On this model, requests that carry a response schema
failed to return more often than not (see failures/structured_output_stall.py),
which made a loop impossible to measure. The contract is still enforced: each
gate validates the reply against the same Pydantic model and treats anything
else as a failed step.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import Agent
from google.adk.agents.context import Context
from google.adk.events import Event, EventActions
from google.adk.workflow import START, FunctionNode, Workflow
from google.genai import types
from pydantic import BaseModel, ValidationError

from workforce import cast

APPROVED_FACTS = cast.lookup_product("TrailLock 2")["facts"]
FACTS_LINE = "Approved product facts: " + "; ".join(APPROVED_FACTS) + "."

ROUNDS_KEY = "review_rounds"
OUTCOME_KEY = "review_outcome"

# JSON by request, with no response schema. Same retry and timeout as the rest.
JSON_REPLY = types.GenerateContentConfig(
    response_mime_type="application/json", http_options=cast.RETRY.http_options
)

DRAFT_FORMAT = (
    "Reply with only a JSON object with the keys email_subject, email_body"
    " (under 120 words) and linkedin_post (under 80 words)."
)
VERDICT_FORMAT = (
    "Reply with only a JSON object with the keys passed (true or false), score"
    " (1 to 10) and fixes (a list of specific changes, empty if passed)."
)

BRAND_RUBRIC = (
    "Score the draft against this rubric: (1) every product claim is"
    " an approved fact, (2) speaks to the fleet manager's pains,"
    " (3) one clear call to action, (4) no hype words. Pass at 8 or"
    " above. "
)
# The two rubrics that cannot both be met. Brand wants every approved fact in
# the email. Legal wants one of those facts kept out.
BRAND_NEEDS_EVERY_FACT = (
    "The email must state all three approved product facts, including the warranty."
    " Fail any draft that leaves one out."
)
LEGAL_RULE = (
    "You are legal review for Corvane Outdoor. Fail any draft that mentions a"
    " warranty in any form, in the email or the post. Pass every other draft."
    " Do not comment on style."
)
# The same brand rubric with a stated order of authority.
BRAND_DEFERS_TO_LEGAL = (
    "The email should state the approved product facts. Legal review outranks"
    " brand review: never require a claim that legal forbids, and legal forbids"
    " any mention of a warranty."
)


def parse_reply(text: str, contract: type[BaseModel]) -> dict[str, Any] | None:
    """Validate an agent's JSON reply against its contract.

    Returns:
        The reply as a plain dict, or ``None`` if it is not valid JSON or does
        not match the contract.
    """
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return contract.model_validate_json(cleaned).model_dump()
    except ValidationError:
        return None


def writer() -> Agent:
    """Build the copywriter, replying with a ``Draft`` as JSON."""
    return Agent(
        name="copywriter",
        model=cast.MODEL,
        generate_content_config=JSON_REPLY,
        description="Writes the campaign email and LinkedIn post from research.",
        instruction=(
            "You write B2B campaign copy for Corvane Outdoor. Use only the"
            " research you are given. Claim only approved product facts."
            " Plain, direct, no hype. " + DRAFT_FORMAT
        ),
    )


def brand_reviewer(extra_rubric: str = "") -> Agent:
    """Build the brand reviewer, replying with a ``Verdict`` as JSON."""
    return Agent(
        name="brand_judge",
        model=cast.MODEL,
        generate_content_config=JSON_REPLY,
        description="Scores a draft against the Corvane brand rubric.",
        instruction=" ".join(
            filter(None, [BRAND_RUBRIC, FACTS_LINE, extra_rubric, VERDICT_FORMAT])
        ),
    )


def legal_reviewer() -> Agent:
    """Build the legal reviewer, replying with a ``Verdict`` as JSON."""
    return Agent(
        name="legal_reviewer",
        model=cast.MODEL,
        generate_content_config=JSON_REPLY,
        description="Checks a draft against Corvane's legal rules.",
        instruction=f"{LEGAL_RULE} {VERDICT_FORMAT}",
    )


def _request(state: Any) -> str:
    """Compose everything the writer needs, since a node is shown only its input."""
    parts = [state.get("brief", ""), FACTS_LINE]
    if state.get("draft"):
        parts.append(f"Your previous draft: {state['draft']}")
    for label, key in (("Brand review", "verdict"), ("Legal review", "legal_verdict")):
        verdict = state.get(key)
        if verdict and not verdict.get("passed", True):
            parts.append(f"{label} failed it. Required fixes: {verdict.get('fixes')}")
    return "\n\n".join(parts)


def prepare(node_input: str, ctx: Context) -> str:
    """Save the brief and hand the writer its first request."""
    ctx.state["brief"] = node_input
    ctx.state[ROUNDS_KEY] = 0
    return _request(ctx.state)


def _send_back(ctx: Context, max_rounds: int | None, reason: str) -> Event:
    """Count a failed step, then route to the writer or, at the limit, to a person."""
    rounds = ctx.state.get(ROUNDS_KEY, 0) + 1
    ctx.state[ROUNDS_KEY] = rounds
    if max_rounds is not None and rounds >= max_rounds:
        return Event(output=reason, actions=EventActions(route="escalate"))
    return Event(output=_request(ctx.state), actions=EventActions(route="revise"))


def _draft_gate(max_rounds: int | None) -> Any:
    """Build the gate that accepts the writer's reply only if it is a valid ``Draft``."""

    def draft_gate(node_input: str, ctx: Context) -> Event:
        draft = parse_reply(node_input, cast.Draft)
        if draft is None:
            return _send_back(ctx, max_rounds, "the writer did not return a valid draft")
        ctx.state["draft"] = draft
        # Clear the last round's verdicts so each draft is judged fresh.
        ctx.state["verdict"] = None
        ctx.state["legal_verdict"] = None
        return Event(output=f"Draft to review: {draft}", actions=EventActions(route="ok"))

    return draft_gate


def _review_gate(verdict_key: str, max_rounds: int | None) -> Any:
    """Build a gate that routes on one reviewer's verdict.

    Routes: ``ok`` when the review passed, ``revise`` when it failed, and
    ``escalate`` when it failed and the round limit has been reached. A reply
    that is not a valid ``Verdict`` counts as a failed review.
    """

    def review_gate(node_input: str, ctx: Context) -> Event:
        verdict = parse_reply(node_input, cast.Verdict)
        if verdict is None:
            verdict = {"passed": False, "score": 0, "fixes": ["the reviewer's reply was not valid"]}
        ctx.state[verdict_key] = verdict
        if verdict["passed"]:
            draft = ctx.state.get("draft")
            return Event(output=f"Draft to review: {draft}", actions=EventActions(route="ok"))
        return _send_back(ctx, max_rounds, f"{verdict_key} failed")

    return review_gate


def publish(ctx: Context) -> str:
    """Record that both reviews passed."""
    ctx.state[OUTCOME_KEY] = "approved"
    return "approved"


def escalate(node_input: str, ctx: Context) -> str:
    """Record that the loop gave up and a person has to decide.

    Part 6 replaces this with a real human approval step. Here it only has to
    exist, so the loop has somewhere to go that is not another round.
    """
    ctx.state[OUTCOME_KEY] = f"escalated after {ctx.state.get(ROUNDS_KEY)} rounds ({node_input})"
    return "escalated"


def build(
    conflict: bool = True, max_rounds: int | None = None, legal_outranks_brand: bool = False
) -> Workflow:
    """Build the review loop.

    Args:
        conflict: Give brand review a rubric that legal review contradicts.
        max_rounds: Failed steps allowed before the loop escalates. ``None``
            leaves the loop with no exit except approval.
        legal_outranks_brand: Replace the conflicting brand rubric with one
            that states which reviewer wins.
    """
    brand_rubric = ""
    if legal_outranks_brand:
        brand_rubric = BRAND_DEFERS_TO_LEGAL
    elif conflict:
        brand_rubric = BRAND_NEEDS_EVERY_FACT

    start = FunctionNode(func=prepare, name="prepare")
    write = writer()
    draft_gate = FunctionNode(func=_draft_gate(max_rounds), name="draft_gate")
    brand = brand_reviewer(brand_rubric)
    brand_gate = FunctionNode(func=_review_gate("verdict", max_rounds), name="brand_gate")
    legal = legal_reviewer()
    legal_gate = FunctionNode(func=_review_gate("legal_verdict", max_rounds), name="legal_gate")
    done = FunctionNode(func=publish, name="publish")
    give_up = FunctionNode(func=escalate, name="escalate")

    return Workflow(
        name="review_loop",
        edges=[
            (START, start, write, draft_gate),
            (draft_gate, {"ok": brand, "revise": write, "escalate": give_up}),
            (brand, brand_gate),
            (brand_gate, {"ok": legal, "revise": write, "escalate": give_up}),
            (legal, legal_gate),
            (legal_gate, {"ok": done, "revise": write, "escalate": give_up}),
        ],
    )
