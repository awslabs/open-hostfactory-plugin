"""Catalog-driven MCP server for Open Resource Broker.

This module exposes the operation catalog as Model Context Protocol tools.
Every operation the broker declares once in :data:`OPERATION_CATALOG` and marks
as exposed on :attr:`Interface.MCP` becomes an MCP tool automatically: the tool
name is the catalog key, its input schema is derived from the operation's input
DTO, and its result body is the operation output rendered through the shared
:class:`ResponseFormattingService` — the same seam the CLI, REST, and SDK
adapters render through. The tool set therefore never drifts from the catalog,
and a tool's body stays in lockstep with the other interfaces for the same
operation.

The server is built on the low-level MCP SDK server so tool registration is
data-driven rather than a hand-written function per tool. Two thin entrypoints
run it over the standard transports: stdio (for local subprocess clients) and
Streamable HTTP (for networked clients).
"""

from __future__ import annotations

import dataclasses
import json
import typing
from typing import Any, Union, get_args, get_origin

import mcp.types as mcp_types
from mcp.server.lowlevel import Server

from orb._package import PACKAGE_NAME, __version__
from orb.interface.catalog import (
    OPERATION_CATALOG,
    CatalogEntry,
    Interface,
    bind_from_mapping,
)
from orb.interface.response_formatting_service import ResponseFormattingService

# JSON-schema type name for each Python scalar/collection the input DTOs use.
# Anything not in this map falls back to a permissive (unconstrained) property.
_JSON_TYPE_BY_PYTHON: dict[type, str] = {
    str: "string",
    bool: "boolean",  # checked before int: bool is a subclass of int
    int: "integer",
    float: "number",
    list: "array",
    dict: "object",
}


def _unwrap_optional(annotation: Any) -> Any:
    """Return ``T`` for an ``Optional[T]`` / ``T | None`` annotation, else the input.

    Only single-``None`` unions are unwrapped; a wider union is left untouched so
    it falls through to the permissive schema branch.
    """
    if get_origin(annotation) is Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _json_type_for(annotation: Any) -> str | None:
    """Map a (possibly Optional/generic) annotation to a JSON-schema type name.

    Returns ``None`` when no simple mapping applies, in which case the property is
    emitted without a ``type`` constraint (permissive).
    """
    annotation = _unwrap_optional(annotation)
    origin = get_origin(annotation)
    base = origin if origin is not None else annotation
    if not isinstance(base, type):
        return None
    # bool must be tested before int (bool is a subclass of int).
    if base is bool:
        return "boolean"
    for python_type, json_name in _JSON_TYPE_BY_PYTHON.items():
        if base is python_type:
            return json_name
    if issubclass(base, bool):
        return "boolean"
    if issubclass(base, int):
        return "integer"
    if issubclass(base, str):
        return "string"
    return None


def schema_from_input_dto(input_dto: type) -> dict[str, Any]:
    """Build a JSON-schema object describing an input DTO's constructor fields.

    Each dataclass field becomes a property; its type is mapped from the field
    annotation (Optional unwrapped, basic scalars and collections recognised).
    Fields with neither a default nor a default factory are marked required.
    ``additionalProperties`` stays permissive so a caller may pass extra keys —
    :func:`bind_from_mapping` drops any that do not name a field.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    # Resolve string annotations (the catalog DTOs use ``from __future__ import
    # annotations``) to real types where possible; fall back to raw field types.
    try:
        hints = typing.get_type_hints(input_dto)
    except Exception:
        hints = {}

    for field in dataclasses.fields(input_dto):
        annotation = hints.get(field.name, field.type)
        json_type = _json_type_for(annotation)
        prop: dict[str, Any] = {}
        if json_type is not None:
            prop["type"] = json_type
            if json_type == "array":
                prop["items"] = {"type": "string"}
        properties[field.name] = prop

        has_default = field.default is not dataclasses.MISSING
        has_default_factory = field.default_factory is not dataclasses.MISSING
        if not has_default and not has_default_factory:
            required.append(field.name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": True,
    }
    if required:
        schema["required"] = required
    return schema


def _mcp_entries() -> list[CatalogEntry[Any, Any]]:
    """Catalog entries exposed on the MCP interface, ordered by key."""
    return [
        entry for _, entry in sorted(OPERATION_CATALOG.items()) if Interface.MCP in entry.exposed_on
    ]


def _tool_for(entry: CatalogEntry[Any, Any]) -> mcp_types.Tool:
    """Build the MCP tool definition for a catalog entry."""
    orchestrator_name = entry.orchestrator.__name__
    description = (
        f"{entry.key} — dispatched through {orchestrator_name}. "
        f"Returns the operation result rendered as the broker's canonical body."
    )
    return mcp_types.Tool(
        name=entry.key,
        description=description,
        inputSchema=schema_from_input_dto(entry.input_dto),
    )


def _error_result(message: str) -> mcp_types.CallToolResult:
    """A tool-level error result (isError=True), not a protocol error."""
    return mcp_types.CallToolResult(
        content=[mcp_types.TextContent(type="text", text=message)],
        isError=True,
    )


def build_server(container: Any) -> Server:
    """Build a low-level MCP :class:`Server` wired to the operation catalog.

    ``container`` is the DI container from which each tool call resolves its
    orchestrator and the shared :class:`ResponseFormattingService`. Tools are
    registered data-driven from :data:`OPERATION_CATALOG`; adding an MCP-exposed
    operation to the catalog adds a tool here with no further change.
    """
    server: Server = Server(PACKAGE_NAME, version=__version__)

    @server.list_tools()
    async def list_tools() -> list[mcp_types.Tool]:
        return [_tool_for(entry) for entry in _mcp_entries()]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[mcp_types.TextContent] | mcp_types.CallToolResult:
        entry = OPERATION_CATALOG.get(name)
        if entry is None or Interface.MCP not in entry.exposed_on:
            return _error_result(f"Unknown tool: {name}")

        try:
            dto = bind_from_mapping(entry, arguments or {})
            orchestrator = container.get(entry.orchestrator)
            formatter = container.get(ResponseFormattingService)
            result = await orchestrator.execute(dto)
            body = entry.renderer_for(Interface.MCP)(formatter, result).data
        except Exception as exc:  # noqa: BLE001 — surfaced to the client as isError
            return _error_result(f"{name} failed: {exc}")

        text = json.dumps(body, default=str)
        return [mcp_types.TextContent(type="text", text=text)]

    return server


async def run_stdio(container: Any) -> None:
    """Serve the catalog MCP server over stdio until the client disconnects."""
    from mcp.server.stdio import stdio_server

    server = build_server(container)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run_streamable_http(container: Any, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Serve the catalog MCP server over Streamable HTTP.

    Wraps the SDK's :class:`StreamableHTTPSessionManager` in a minimal Starlette
    app mounted at ``/mcp`` and runs it under uvicorn. Blocks until the server
    is stopped.
    """
    import contextlib
    from collections.abc import AsyncIterator

    import uvicorn
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from starlette.types import Receive, Scope, Send

    server = build_server(container)
    session_manager = StreamableHTTPSessionManager(app=server)

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    app = Starlette(
        routes=[Mount("/mcp", app=handle_mcp)],
        lifespan=lifespan,
    )
    uvicorn.run(app, host=host, port=port)
