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

"""Part 4 claims that can be checked without a model.

These start the DesignDesk MCP server as a subprocess and ask it for its
tools, exactly as an agent's connection would. No model is called.
"""

from __future__ import annotations

import asyncio
from typing import Any

from workforce.tools import access, design_server


async def _tools(access_level: str, poison: str = "") -> list[Any]:
    """Return every tool the given connection would hand to an agent."""
    found: list[Any] = []
    for toolset in access.toolset(access_level, poison):
        try:
            found.extend(await toolset.get_tools())
        finally:
            await toolset.close()
    return found


def _names(tools: list[Any]) -> set[str]:
    return {tool.name for tool in tools}


def _description(tools: list[Any], name: str) -> str:
    tool = next(tool for tool in tools if tool.name == name)
    return str(tool._get_declaration().description)


def test_a_default_connection_hands_over_every_tool() -> None:
    tools = asyncio.run(_tools("everything"))
    assert _names(tools) == set(design_server.ALL_TOOLS)
    assert set(design_server.DANGEROUS_TOOLS) <= _names(tools)


def test_a_tool_filter_leaves_only_the_tools_named() -> None:
    tools = asyncio.run(_tools("least"))
    assert _names(tools) == set(design_server.BANNER_TOOLS)
    assert not set(design_server.DANGEROUS_TOOLS) & _names(tools)


def test_confirmation_is_set_per_connection_not_per_tool() -> None:
    tools = asyncio.run(_tools("confirmed"))
    assert _names(tools) == set(design_server.ALL_TOOLS)
    needs_a_person = {tool.name for tool in tools if tool._require_confirmation}
    assert needs_a_person == set(design_server.DANGEROUS_TOOLS)


def test_a_tool_description_reaches_the_model_exactly_as_the_server_wrote_it() -> None:
    clean = asyncio.run(_tools("everything"))
    poisoned = asyncio.run(_tools("everything", poison="description"))
    assert design_server.INJECTION not in _description(clean, "export_design")
    # Nothing between the server and the model reads, trims or flags this text.
    assert design_server.INJECTION in _description(poisoned, "export_design")


def test_the_banner_job_needs_a_third_of_what_the_server_offers() -> None:
    assert len(design_server.ALL_TOOLS) == 12
    assert len(design_server.BANNER_TOOLS) == 4
    assert set(design_server.BANNER_TOOLS) <= set(design_server.ALL_TOOLS)
