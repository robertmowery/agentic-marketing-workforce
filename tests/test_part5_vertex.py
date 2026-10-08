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

"""Part 5, the Vertex AI Search run: claims checked without a network or a model."""

from __future__ import annotations

import pytest
from google.adk.tools import VertexAiSearchTool

from workforce.knowledge import answer, library, vertex_search


def _question(key: str) -> answer.Question:
    return next(q for q in answer.QUESTIONS if q.key == key)


def _both_price_lists(query: str) -> list[library.Document]:
    """Stand in for a hosted search: the superseded list first, as Vertex AI Search ranked it."""
    found = [library.get("tl2-pricing-final"), library.get("tl2-fleet-pricing")]
    return [doc for doc in found if doc is not None]


def test_the_agent_is_told_the_same_thing_whichever_search_is_behind_the_tools() -> None:
    local = answer.library_tools(library.search)
    hosted = answer.library_tools(_both_price_lists)
    assert [tool.__name__ for tool in local] == [tool.__name__ for tool in hosted]
    assert [tool.__doc__ for tool in local] == [tool.__doc__ for tool in hosted]


def test_the_undated_tool_leaves_the_date_out_on_any_search() -> None:
    plain, dated = answer.library_tools(_both_price_lists)
    assert all("effective" not in result for result in plain("fleet price"))
    assert [result["effective"] for result in dated("fleet price")] == ["2025-03-01", "2026-07-01"]


def test_both_searches_are_offered_under_one_name_each() -> None:
    assert set(answer.SEARCHES) == {"local", "vertex"}
    assert answer.SEARCHES["vertex"] is vertex_search.search


def test_the_data_store_is_named_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "example-project")
    assert vertex_search.data_store() == (
        "projects/example-project/locations/global/collections/default_collection"
        f"/dataStores/{vertex_search.DATA_STORE_ID}"
    )


def test_the_built_in_build_has_no_search_function_of_ours_and_no_date_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "example-project")
    agent = answer.build(answer.GROUNDED)
    assert len(agent.tools) == 1
    assert isinstance(agent.tools[0], VertexAiSearchTool)
    assert "later effective date" not in str(agent.instruction)
    assert "NOT FOUND" in str(agent.instruction)


def test_a_plain_reply_is_graded_against_the_documents_the_service_cited() -> None:
    graded = answer.grade(
        _question("price"), "The fleet price is $529 per unit.", ["tl2-fleet-pricing"]
    )
    assert graded["outcome"] == "right"
    assert graded["numbers_not_in_sources"] == []


def test_a_plain_reply_that_begins_not_found_counts_as_declined() -> None:
    graded = answer.grade(
        _question("fit"), "NOT FOUND. No document mentions the Ford Transit.", ["install"]
    )
    assert graded["outcome"] == "declined"
