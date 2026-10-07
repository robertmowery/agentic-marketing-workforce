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

"""Part 5: one question-answering agent, built three ways.

``no_library``  no documents at all. The agent has only what the model knows.
``library``     a search tool that returns document text.
``dated``       the same search, but each result carries the date it took
                effect, and the agent is told what to do with it.

Every build replies in the same JSON shape, so one code check can read all of
them. JSON is requested in the instruction and validated here, with no
response schema (see Part 3 and failures/structured_output_stall.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from google.adk.agents import Agent
from pydantic import BaseModel

from workforce import cast
from workforce.knowledge import library
from workforce.review.loop import JSON_REPLY, parse_reply

BUILDS = ("no_library", "library", "dated")


class Answer(BaseModel):  # noqa: D101 - a docstring here would leak into the contract
    answer: str
    sources: list[str]
    found: bool


ANSWER_FORMAT = (
    "Reply with only a JSON object with the keys answer (one or two sentences),"
    " sources (a list of the document ids you relied on, empty if none) and"
    " found (true if you can answer, false if you cannot)."
)
ROLE = "You answer sales questions about Corvane Outdoor products for the fleet sales team."
USE_LIBRARY = " Search the company library before you answer."
GROUNDING_RULES = (
    " Answer only from documents the search returns. When two documents"
    " disagree, the one with the later effective date wins. If the documents"
    " do not answer the question, set found to false and say what is missing."
    " Do not fill gaps from general knowledge."
)


@dataclass(frozen=True)
class Question:
    """A question with what a right, a stale and a guessed answer look like."""

    key: str
    text: str
    answerable: bool
    right: tuple[str, ...] = ()  # every one of these must appear in a right answer
    stale: tuple[str, ...] = ()  # any of these marks an answer from a superseded document


QUESTIONS: tuple[Question, ...] = (
    Question("install", "How long does TrailLock 2 take to install?", True, ("20",)),
    Question(
        "price",
        "What is the fleet price per unit for TrailLock 2?",
        True,
        ("529",),
        ("489",),
    ),
    Question(
        "discount",
        "What volume discount does a fleet order of TrailLock 2 get, and at how many units?",
        True,
        ("12%", "100"),
        ("10%",),
    ),
    Question(
        "fit",
        "Does TrailLock 2 fit the factory roof rails on a 2026 Ford Transit high roof?",
        False,
    ),
)


def search_library(query: str) -> list[dict[str, str]]:
    """Search the company library and return the best-matching documents."""
    return [{"id": d.doc_id, "title": d.title, "text": d.text} for d in library.search(query)]


def search_library_dated(query: str) -> list[dict[str, str]]:
    """Search the company library and return the best-matching documents with their dates."""
    return [
        {"id": d.doc_id, "title": d.title, "effective": d.effective, "text": d.text}
        for d in library.search(query)
    ]


def build(name: str) -> Agent:
    """Build one of the three answering agents."""
    if name == "no_library":
        tools: list[Any] = []
        instruction = ROLE
    elif name == "library":
        instruction, tools = ROLE + USE_LIBRARY, [search_library]
    elif name == "dated":
        instruction, tools = ROLE + USE_LIBRARY + GROUNDING_RULES, [search_library_dated]
    else:
        raise ValueError(f"unknown build: {name}")
    return Agent(
        name="sales_desk",
        model=cast.MODEL,
        generate_content_config=JSON_REPLY,
        description="Answers fleet sales questions.",
        instruction=f"{instruction} {ANSWER_FORMAT}",
        tools=tools,
    )


def numbers(text: str) -> set[str]:
    """Return every number in a piece of text, without separators, signs or leading zeros.

    Dropping leading zeros lets "July 1" in an answer match "07-01" in a date.
    """
    found = re.findall(r"\d[\d,]*", text)
    return {match.replace(",", "").lstrip("0") or "0" for match in found}


def unsupported_numbers(answer: str, sources: list[str]) -> set[str]:
    """Return the numbers an answer states that none of its cited documents contain.

    This needs no model. It cannot tell whether an answer is right, only
    whether its figures can be traced to the documents it names.
    """
    docs = [doc for doc in map(library.get, sources) if doc is not None]
    cited = " ".join(f"{doc.doc_id} {doc.title} {doc.effective} {doc.text}" for doc in docs)
    return numbers(answer) - numbers(cited)


def grade(question: Question, reply: str) -> dict[str, Any]:
    """Grade one reply in code against what the library actually says."""
    parsed = parse_reply(reply, Answer)
    if parsed is None:
        return {"valid": False, "outcome": "invalid reply"}
    text = parsed["answer"]
    known = [s for s in parsed["sources"] if library.get(s) is not None]
    loose = sorted(unsupported_numbers(text, known)) if parsed["found"] else []
    has_stale = any(mark in text for mark in question.stale)
    has_right = bool(question.right) and all(mark in text for mark in question.right)
    if not parsed["found"]:
        outcome = "declined"
    elif not question.answerable:
        outcome = "answered what the documents do not say"
    elif has_stale and has_right:
        outcome = "gave both"
    elif has_stale:
        outcome = "stale"
    elif has_right:
        outcome = "right"
    else:
        outcome = "wrong"
    return {
        "valid": True,
        "outcome": outcome,
        "found": parsed["found"],
        "answer": text,
        "sources": parsed["sources"],
        "sources_not_in_library": [s for s in parsed["sources"] if s not in known],
        "numbers_not_in_sources": loose,
    }
