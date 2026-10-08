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

"""Part 6 claims that can be checked without a model."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from google.genai import types

from workforce.tools import access, design_server
from workforce.trust import approval, guard


def _context(request: str) -> Any:
    content = types.Content(role="user", parts=[types.Part(text=request)])
    return SimpleNamespace(user_content=content)


def _tool(name: str) -> Any:
    return SimpleNamespace(name=name)


def test_the_guard_reads_the_request_and_nothing_else() -> None:
    assert guard.allowed("create_design", access.TASK)
    assert not guard.allowed("delete_design", access.TASK)
    assert not guard.allowed("share_design_publicly", access.TASK)
    assert guard.allowed("delete_design", "Please delete design d-100.")


def test_the_banner_request_asks_for_nothing_dangerous() -> None:
    assert not any(guard.allowed(name, access.TASK) for name in design_server.DANGEROUS_TOOLS)


def test_a_blocked_call_returns_a_result_so_the_real_tool_never_runs() -> None:
    blocked: list[dict[str, Any]] = []
    callback = guard.make_guard(blocked)
    result = callback(_tool("delete_design"), {"design_id": "d-100"}, _context(access.TASK))
    assert result is not None and "blocked" in result["error"]
    assert blocked == [{"tool": "delete_design", "args": {"design_id": "d-100"}}]


def test_an_allowed_call_passes_through_untouched() -> None:
    blocked: list[dict[str, Any]] = []
    callback = guard.make_guard(blocked)
    assert callback(_tool("export_design"), {"design_id": "d-200"}, _context(access.TASK)) is None
    assert blocked == []


def test_the_planted_instruction_cannot_satisfy_the_guard() -> None:
    # The planted text says "delete" and "share". The guard never sees it,
    # because it reads the marketer's request, not tool text.
    assert "delete" in design_server.INJECTION.lower()
    assert not guard.allowed("delete_design", access.TASK)


def test_the_two_approvers_disagree_about_an_unrequested_delete() -> None:
    args = {"design_id": "d-100"}
    assert approval.rubber_stamp("delete_design", args, access.TASK) is True
    assert approval.reads_request("delete_design", args, access.TASK) is False
    assert approval.reads_request("delete_design", args, "Delete d-100, please.") is True
