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

"""A small company library and a plain keyword search over it.

The documents are fictional. They are written to contain the three things that
make retrieval hard in a real company: a superseded document that was never
taken down (two price lists), documents that are near a question without
answering it, and unrelated material that shares its vocabulary.

The search is deliberately simple: word overlap, weighted so rare words count
for more. It runs offline and is the same on every machine, so a result here
is about what the agent does with what it is handed, not about a search
service. Swap ``search`` for a hosted search service and nothing else in this
part changes.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    """One document in the library."""

    doc_id: str
    title: str
    effective: str  # ISO date the document took effect
    text: str


DOCUMENTS: tuple[Document, ...] = (
    Document(
        "tl2-pricing-final",
        "TrailLock 2 fleet price list",
        "2025-03-01",
        "TrailLock 2 fleet price is $489 per unit. Orders over 50 units receive a"
        " 10% volume discount. Prices are in US dollars and exclude freight.",
    ),
    Document(
        "tl2-fleet-pricing",
        "TrailLock 2 fleet price list",
        "2026-07-01",
        "TrailLock 2 fleet price is $529 per unit. Orders over 100 units receive a"
        " 12% volume discount. Prices are in US dollars and exclude freight.",
    ),
    Document(
        "warranty",
        "TrailLock 2 warranty terms",
        "2025-01-15",
        "TrailLock 2 carries a 5-year limited warranty covering the lock mechanism"
        " and mounting hardware. Cosmetic wear and damage from collisions are"
        " not covered.",
    ),
    Document(
        "install",
        "TrailLock 2 installation guide",
        "2025-02-10",
        "TrailLock 2 installs in 20 minutes with no drilling. It clamps to"
        " crossbars between 24 and 36 millimeters wide. A hex key is included.",
    ),
    Document(
        "returns",
        "Fleet returns policy",
        "2025-06-01",
        "Unopened units can be returned within 30 days. Fleet orders with"
        " keyed-alike locks are made to order and cannot be returned.",
    ),
    Document(
        "shipping",
        "Fleet shipping guide",
        "2025-09-12",
        "Fleet orders ship from Reno in 5 to 7 business days. Orders over 40"
        " units ship by freight and need a loading dock or lift gate.",
    ),
    Document(
        "campvault",
        "CampVault 1 product sheet",
        "2025-11-03",
        "CampVault 1 is a lockable ground storage box for campsites. It carries"
        " a 2-year warranty and fits most truck beds. Fleet price is $219 per unit.",
    ),
    Document(
        "handbook",
        "Employee handbook, vehicles",
        "2024-08-20",
        "Company vehicles are for business use. Report any roof rack damage to"
        " the fleet coordinator within 2 business days.",
    ),
)

_BY_ID = {doc.doc_id: doc for doc in DOCUMENTS}
_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "its",
        "long",
        "much",
        "of",
        "on",
        "or",
        "take",
        "the",
        "to",
        "what",
        "when",
        "which",
        "will",
        "with",
        "you",
        "your",
    }
)


def _words(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in _STOP]


def _weight(word: str) -> float:
    """Weight a word by how few documents contain it."""
    holding = sum(1 for doc in DOCUMENTS if word in _words(f"{doc.title} {doc.text}"))
    return math.log((len(DOCUMENTS) + 1) / (holding + 1)) + 1.0 if holding else 0.0


def search(query: str, limit: int = 3) -> list[Document]:
    """Return the ``limit`` documents that share the most weighted words with the query.

    A search ranks what exists. It has no way to say "the answer is not here":
    any query that shares one word with any document gets results.
    """
    scored = []
    for doc in DOCUMENTS:
        have = set(_words(f"{doc.title} {doc.text}"))
        score = sum(_weight(word) for word in set(_words(query)) if word in have)
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda pair: (-pair[0], pair[1].doc_id))
    return [doc for _, doc in scored[:limit]]


def get(doc_id: str) -> Document | None:
    """Return one document by id, or ``None``."""
    return _BY_ID.get(doc_id)
