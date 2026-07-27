"""Unit tests for the catalog-driven MCP server.

These tests pin the guarantee the catalog server is built to deliver: the tool
set is exactly the catalog's MCP-exposed operations, each tool's input schema is
derived from that operation's input DTO, and a tool call renders its body through
the same ``Interface.MCP`` renderer every other interface would use for that
operation. The catalog is the single source; the MCP surface follows it.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from orb.application.dto.interface_response import InterfaceResponse
from orb.application.machine.dto import MachineDTO
from orb.application.services.orchestration.dtos import (
    ListMachinesInput,
    ListMachinesOutput,
)
from orb.application.services.orchestration.list_machines import ListMachinesOrchestrator
from orb.infrastructure.di.container import DIContainer
from orb.interface.catalog import OPERATION_CATALOG, Interface
from orb.interface.mcp.catalog_server import (
    build_server,
    schema_from_input_dto,
)
from orb.interface.response_formatting_service import ResponseFormattingService


def _mcp_keys() -> set[str]:
    """Catalog keys exposed on the MCP interface."""
    return {key for key, entry in OPERATION_CATALOG.items() if Interface.MCP in entry.exposed_on}


async def _list_tools(server: Any) -> list[Any]:
    """Invoke the server's registered list_tools handler."""
    handler = server.request_handlers
    import mcp.types as mcp_types

    result = await handler[mcp_types.ListToolsRequest](
        mcp_types.ListToolsRequest(method="tools/list")
    )
    return result.root.tools


@pytest.mark.asyncio
async def test_list_tools_matches_catalog_mcp_entries() -> None:
    """list_tools returns exactly the catalog's MCP-exposed operations."""
    server = build_server(MagicMock(spec=DIContainer))
    tools = await _list_tools(server)

    tool_names = {tool.name for tool in tools}
    assert tool_names == _mcp_keys()


@pytest.mark.asyncio
async def test_each_tool_schema_carries_its_dto_fields() -> None:
    """Every tool's inputSchema exposes exactly its input DTO's fields."""
    server = build_server(MagicMock(spec=DIContainer))
    tools = await _list_tools(server)

    for tool in tools:
        entry = OPERATION_CATALOG[tool.name]
        expected_fields = {f.name for f in dataclasses.fields(entry.input_dto)}
        schema_fields = set(tool.inputSchema["properties"].keys())
        assert schema_fields == expected_fields, (
            f"{tool.name}: schema properties {schema_fields} != DTO fields {expected_fields}"
        )
        assert tool.inputSchema["type"] == "object"


def test_schema_marks_required_fields_without_defaults() -> None:
    """A DTO field with no default is required; fields with defaults are not."""
    # GetMachineInput has a single required field (machine_id) and no defaults.
    from orb.application.services.orchestration.dtos import GetMachineInput

    schema = schema_from_input_dto(GetMachineInput)
    assert schema["required"] == ["machine_id"]
    assert schema["properties"]["machine_id"]["type"] == "string"

    # ListMachinesInput fields all carry defaults, so nothing is required.
    list_schema = schema_from_input_dto(ListMachinesInput)
    assert "required" not in list_schema
    assert list_schema["properties"]["limit"]["type"] == "integer"
    assert list_schema["properties"]["sync"]["type"] == "boolean"
    assert list_schema["properties"]["filter_expressions"]["type"] == "array"


async def _call_tool(server: Any, name: str, arguments: dict[str, Any]) -> Any:
    """Invoke the server's registered call_tool handler and return the result."""
    import mcp.types as mcp_types

    handler = server.request_handlers
    return await handler[mcp_types.CallToolRequest](
        mcp_types.CallToolRequest(
            method="tools/call",
            params=mcp_types.CallToolRequestParams(name=name, arguments=arguments),
        )
    )


@pytest.mark.asyncio
async def test_call_tool_returns_mcp_rendered_body() -> None:
    """call_tool for list_machines returns the Interface.MCP rendered body as JSON."""
    machine = MachineDTO(
        machine_id="machine-001",
        name="test-machine",
        status="running",
        instance_type="t3.medium",
        private_ip="10.0.0.1",
        result="succeed",
    )
    output = ListMachinesOutput(machines=[machine], count=1, next_cursor=None, total_count=1)

    orchestrator = AsyncMock(spec=ListMachinesOrchestrator)
    orchestrator.execute.return_value = output

    # A real ResponseFormattingService over the dependency-free default strategy,
    # so the tool body is the genuine Interface.MCP render rather than a stub.
    from orb.infrastructure.scheduler.default.default_strategy import DefaultSchedulerStrategy

    formatter = ResponseFormattingService(DefaultSchedulerStrategy(logger=MagicMock()))

    container = MagicMock(spec=DIContainer)
    container.get.side_effect = lambda cls: {
        ListMachinesOrchestrator: orchestrator,
        ResponseFormattingService: formatter,
    }.get(cls)

    server = build_server(container)
    result = await _call_tool(server, "list_machines", {"limit": 100})

    tool_result = result.root
    assert tool_result.isError is False
    assert len(tool_result.content) == 1
    parsed = json.loads(tool_result.content[0].text)

    # The parsed tool body must equal the catalog's Interface.MCP render of the
    # same output DTO — the MCP surface renders through the shared seam.
    entry = OPERATION_CATALOG["list_machines"]
    expected: InterfaceResponse = entry.renderer_for(Interface.MCP)(formatter, output)
    assert parsed == expected.data


@pytest.mark.asyncio
async def test_call_tool_unknown_name_is_error_result() -> None:
    """An unknown tool name yields an isError result, not a raised exception."""
    server = build_server(MagicMock(spec=DIContainer))
    result = await _call_tool(server, "does_not_exist", {})

    tool_result = result.root
    assert tool_result.isError is True
    assert "Unknown tool" in tool_result.content[0].text


@pytest.mark.asyncio
async def test_call_tool_execution_failure_is_error_result() -> None:
    """An orchestrator failure is surfaced as an isError result."""
    orchestrator = AsyncMock(spec=ListMachinesOrchestrator)
    orchestrator.execute.side_effect = RuntimeError("boom")

    container = MagicMock(spec=DIContainer)
    container.get.side_effect = lambda cls: {
        ListMachinesOrchestrator: orchestrator,
        ResponseFormattingService: MagicMock(spec=ResponseFormattingService),
    }.get(cls)

    server = build_server(container)
    result = await _call_tool(server, "list_machines", {})

    tool_result = result.root
    assert tool_result.isError is True
    assert "list_machines failed" in tool_result.content[0].text
