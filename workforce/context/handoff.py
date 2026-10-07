"""Handoffs: what a specialist is actually shown when work is passed to it.

The scenario is a two-turn conversation. In turn one the marketer gives a
standing rule. In turn two the marketer sends the brief. The question is
whether the rule reaches the copywriter, who never spoke to the marketer.
"""

from __future__ import annotations

import json
from typing import Any

from google.adk.agents import Agent
from google.adk.tools import ToolContext

from workforce import cast
from workforce.topologies import graph

SIGN_OFF = "The Corvane Fleet Desk"

# The rule is chosen so that breaking it is easy to detect and likely by
# default: the warranty is one of the three approved product facts.
RULE_TURN = (
    f"Before we start, a standing rule for everything you write for me: sign every"
    f" email '{SIGN_OFF}' and never mention the warranty."
)

HOUSE_RULES_KEY = "user:house_rules"


def save_house_rule(rule: str, tool_context: ToolContext) -> dict[str, str]:
    """Saves a standing rule the marketer wants applied to all future copy."""
    existing = tool_context.state.get(HOUSE_RULES_KEY, "")
    tool_context.state[HOUSE_RULES_KEY] = f"{existing} {rule}".strip()
    return {"status": "saved"}


def build_hybrid_with_rules() -> Agent:
    """Build the hybrid with standing rules carried in state, not in the handoff.

    The Director saves each rule to user-scoped state with a tool. The
    pipeline's writer and judge read that key in their own instructions, so
    the rule reaches them whether or not the Director repeats it in the brief.
    """
    return Agent(
        name="campaign_director",
        model=cast.MODEL,
        generate_content_config=cast.RETRY,
        description="Front door for marketers. Hands briefs to the pipeline.",
        instruction=(
            "You are the front door for marketers at Corvane Outdoor. When"
            " the marketer gives you a standing rule or preference, call"
            " save_house_rule with it and confirm in one sentence. When"
            " you receive a campaign brief, call the campaign_pipeline tool"
            " with the full brief. Then report the draft and the verdict."
            " Do not write copy yourself."
        ),
        # ADK accepts a Workflow with an input schema as a tool, though its type hints lag.
        tools=[save_house_rule, graph.build(as_tool=True, house_rules=True)],  # type: ignore[list-item]
    )


def check_draft(state: dict[str, Any]) -> dict[str, bool]:
    """Report whether the saved draft obeyed the marketer's standing rule."""
    draft = state.get("draft")
    text = json.dumps(draft) if draft else ""
    return {
        "has_draft": bool(draft),
        "signed_as_told": SIGN_OFF.lower() in text.lower(),
        "left_out_warranty": bool(draft) and "warranty" not in text.lower(),
    }
