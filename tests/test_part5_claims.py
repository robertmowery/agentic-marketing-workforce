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

"""Part 5 claims that can be checked without a model."""

from __future__ import annotations

import json

from workforce.knowledge import answer, library


def _ids(query: str) -> list[str]:
    return [doc.doc_id for doc in library.search(query)]


def _question(key: str) -> answer.Question:
    return next(q for q in answer.QUESTIONS if q.key == key)


def _reply(text: str, sources: list[str], found: bool = True) -> str:
    return json.dumps({"answer": text, "sources": sources, "found": found})


def test_search_finds_the_document_that_answers_a_plain_question() -> None:
    assert _ids(_question("install").text)[0] == "install"


def test_search_returns_the_superseded_price_list_beside_the_current_one() -> None:
    found = _ids(_question("price").text)
    # Nobody removed the old list, and to a search the two are equally good matches.
    assert {"tl2-pricing-final", "tl2-fleet-pricing"} <= set(found)


def test_search_returns_documents_for_a_question_none_of_them_answer() -> None:
    found = _ids(_question("fit").text)
    assert found
    assert not any("Transit" in doc.text for doc in library.DOCUMENTS)


def test_only_the_dated_tool_tells_the_agent_which_document_is_newer() -> None:
    query = _question("price").text
    assert all("effective" not in hit for hit in answer.search_library(query))
    assert all("effective" in hit for hit in answer.search_library_dated(query))


def test_a_number_missing_from_the_cited_documents_is_caught_in_code() -> None:
    assert answer.unsupported_numbers("It costs $529 per unit.", ["tl2-fleet-pricing"]) == set()
    assert answer.unsupported_numbers("It costs $499 per unit.", ["tl2-fleet-pricing"]) == {"499"}
    assert answer.unsupported_numbers("It costs $529 per unit.", []) == {"529"}


def test_grading_tells_right_from_stale_from_hedged_from_invented() -> None:
    price, fit = _question("price"), _question("fit")
    assert (
        answer.grade(price, _reply("$529 per unit.", ["tl2-fleet-pricing"]))["outcome"] == "right"
    )
    assert (
        answer.grade(price, _reply("$489 per unit.", ["tl2-pricing-final"]))["outcome"] == "stale"
    )
    both = _reply("$489 on one list and $529 on the other.", ["tl2-pricing-final"])
    assert answer.grade(price, both)["outcome"] == "gave both"
    assert answer.grade(fit, _reply("Not covered.", [], found=False))["outcome"] == "declined"
    invented = answer.grade(fit, _reply("Yes, it fits.", ["install"]))
    assert invented["outcome"] == "answered what the documents do not say"
