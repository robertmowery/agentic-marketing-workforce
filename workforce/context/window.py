"""The context window: what a long conversation costs, and what trimming it loses.

One agent, one long session. The marketer states a purchase order number in
the first turn, asks for a run of unrelated copy, and asks for the number
back at the end. Every turn resends the whole conversation, so input grows
turn over turn until something compacts it.
"""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.apps.app import EventsCompactionConfig

from workforce import cast

PO_NUMBER = "PO-48213"

OPENING_TURN = (
    f"For the record, the purchase order for this campaign is {PO_NUMBER}. Just acknowledge it."
)
CLOSING_TURN = "What is the purchase order number for this campaign? Reply with the number only."

FILLER_TOPICS = [
    "the 20-minute install",
    "keyed-alike locking for a 500-vehicle fleet",
    "winter storm response crews",
    "reducing theft from open racks",
    "a fleet manager's January budget planning",
    "crew downtime from damaged gear",
    "onboarding a new depot",
    "a trade show booth",
    "a webinar invitation",
    "a customer anniversary note",
]


def turns(filler: int = len(FILLER_TOPICS)) -> list[str]:
    """Return the scripted conversation: the fact, ``filler`` requests, then the question."""
    middle = [
        f"Write a 120-word LinkedIn post for the TrailLock 2 about {topic}."
        for topic in FILLER_TOPICS[:filler]
    ]
    return [OPENING_TURN, *middle, CLOSING_TURN]


def build_writer() -> Agent:
    """Build a single conversational copywriter with no tools and no schema."""
    return Agent(
        name="campaign_writer",
        model=cast.MODEL,
        generate_content_config=cast.RETRY,
        description="Writes short campaign copy for Corvane Outdoor on request.",
        instruction=(
            "You write short B2B campaign copy for Corvane Outdoor. Plain, direct, no hype."
        ),
    )


def build_app(name: str, compaction_interval: int | None = None, overlap_size: int = 1) -> App:
    """Wrap the writer in an ``App``, optionally with sliding-window compaction.

    Args:
        name: The app name.
        compaction_interval: Summarize older events after this many new
            invocations. ``None`` leaves the history untouched.
        overlap_size: Invocations carried over between compaction windows.
    """
    config = None
    if compaction_interval is not None:
        config = EventsCompactionConfig(
            compaction_interval=compaction_interval, overlap_size=overlap_size
        )
    return App(name=name, root_agent=build_writer(), events_compaction_config=config)
