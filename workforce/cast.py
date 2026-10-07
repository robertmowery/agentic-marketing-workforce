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

"""The cast: the specialist agents every topology in Part 1 reuses.

Each build gets fresh instances from these factories, because an ADK agent
can have only one parent.

Docstrings on the ``lookup_*`` tools and every ``description`` and
``instruction`` string are sent to the model. Changing their wording changes
the experiment, so edit them deliberately.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import Agent
from google.genai import types
from pydantic import BaseModel, Field

MODEL = "gemini-3.5-flash"

# Retry transient quota errors (429) instead of failing the whole campaign.
RETRY = types.GenerateContentConfig(
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(attempts=6, initial_delay=2.0, max_delay=30.0)
    )
)

BRIEF = (
    "Campaign brief for Corvane Outdoor: launch the TrailLock 2 rooftop cargo"
    " system to fleet managers at regional utility companies. One email and"
    " one LinkedIn post. Goal: booked demos in Q1."
)


# --- Stub tools ---------------------------------------------------------------
# Real retrieval arrives in Part 5. Fixed data keeps Part 1 runs comparable
# across topologies.


def lookup_audience(segment: str) -> dict:
    """Returns what Corvane knows about a buyer segment."""
    return {
        "segment": segment,
        "pains": ["crew downtime from gear damage", "theft from open racks"],
        "buying_trigger": "annual fleet refresh budget, set in January",
    }


def lookup_competitors(product_category: str) -> dict:
    """Returns the competitive picture for a product category."""
    return {
        "category": product_category,
        "competitors": ["RackMaster Pro", "SummitHaul"],
        "gap": "neither offers a keyed-alike lock across a whole fleet",
    }


def lookup_product(product_name: str) -> dict:
    """Returns approved product facts. Copy may not claim anything else."""
    return {
        "product": product_name,
        "facts": [
            "keyed-alike locking across up to 500 vehicles",
            "installs in 20 minutes with no drilling",
            "5-year warranty",
        ],
    }


# --- Contracts ----------------------------------------------------------------
# These classes carry comments, not docstrings: Pydantic copies a class docstring
# into the JSON schema, and that schema is sent to the model.


# Input contract for the campaign pipeline when it is used as a tool.
class Brief(BaseModel):  # noqa: D101
    brief: str = Field(description="The full campaign brief, verbatim.")


# What the copywriter must return.
class Draft(BaseModel):  # noqa: D101
    email_subject: str
    email_body: str = Field(description="Under 120 words.")
    linkedin_post: str = Field(description="Under 80 words.")


# What the brand judge must return.
class Verdict(BaseModel):  # noqa: D101
    passed: bool
    score: int = Field(description="1 to 10 against the brand rubric.")
    fixes: list[str] = Field(description="Specific changes; empty if passed.")


# --- Agent factories ----------------------------------------------------------


def _mode_kwargs(mode: str | None) -> dict[str, Any]:
    """Return the ``mode`` keyword only when one is set.

    Passing no mode lets ADK choose by position: ``chat`` for a sub-agent,
    ``single_turn`` for a workflow node.
    """
    return {"mode": mode} if mode else {}


def researchers(mode: str | None = "single_turn") -> list[Agent]:
    """Build the three researchers, each with one lookup tool.

    Args:
        mode: ADK agent mode, or ``None`` to take the positional default.

    Returns:
        The audience, competitor, and product researchers, in that order.
    """
    kw = _mode_kwargs(mode)
    return [
        Agent(
            name="audience_researcher",
            model=MODEL,
            generate_content_config=RETRY,
            description="Finds the pains and buying triggers of a buyer segment.",
            instruction=(
                "Call lookup_audience for the segment in the brief."
                " Reply with three bullet points and nothing else."
            ),
            tools=[lookup_audience],
            output_key="audience",
            **kw,
        ),
        Agent(
            name="competitor_researcher",
            model=MODEL,
            generate_content_config=RETRY,
            description="Finds competitors and the gap Corvane can claim.",
            instruction=(
                "Call lookup_competitors for the product category in the brief."
                " Reply with three bullet points and nothing else."
            ),
            tools=[lookup_competitors],
            output_key="competitors",
            **kw,
        ),
        Agent(
            name="product_researcher",
            model=MODEL,
            generate_content_config=RETRY,
            description="Returns the approved facts about a Corvane product.",
            instruction=(
                "Call lookup_product for the product in the brief."
                " Reply with the approved facts as bullet points and nothing else."
            ),
            tools=[lookup_product],
            output_key="product",
            **kw,
        ),
    ]


def copywriter(mode: str | None = "single_turn", instruction_extra: str = "") -> Agent:
    """Build the copywriter, which must return a ``Draft``.

    Args:
        mode: ADK agent mode, or ``None`` to take the positional default.
        instruction_extra: Text appended to the instruction, used by builds
            that read research from session state.
    """
    return Agent(
        name="copywriter",
        model=MODEL,
        generate_content_config=RETRY,
        description="Writes the campaign email and LinkedIn post from research.",
        instruction=(
            "You write B2B campaign copy for Corvane Outdoor. Use only the"
            " research you are given. Claim only approved product facts."
            " Plain, direct, no hype. " + instruction_extra
        ),
        output_schema=Draft,
        output_key="draft",
        **_mode_kwargs(mode),
    )


def brand_judge(mode: str | None = "single_turn", instruction_extra: str = "") -> Agent:
    """Build the brand judge, which must return a ``Verdict``.

    Args:
        mode: ADK agent mode, or ``None`` to take the positional default.
        instruction_extra: Text appended to the instruction, used by builds
            that read the draft from session state.
    """
    return Agent(
        name="brand_judge",
        model=MODEL,
        generate_content_config=RETRY,
        description="Scores a draft against the Corvane brand rubric.",
        instruction=(
            "Score the draft against this rubric: (1) every product claim is"
            " an approved fact, (2) speaks to the fleet manager's pains,"
            " (3) one clear call to action, (4) no hype words. Pass at 8 or"
            " above. " + instruction_extra
        ),
        output_schema=Verdict,
        output_key="verdict",
        **_mode_kwargs(mode),
    )
