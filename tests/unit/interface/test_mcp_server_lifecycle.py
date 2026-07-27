"""Unit tests for the catalog MCP server lifecycle and CLI handlers.

These exercise the transport wiring and CLI-facing handlers of the catalog MCP
server without any real network, stdio, or event-loop-blocking server: the
``serve`` handler's transport dispatch, the stdio and Streamable HTTP runners'
wiring, the telemetry-flush cleanup, and the offline ``validate`` handler. Every
transport boundary is mocked so nothing binds a port or reads a stream.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, sentinel

import mcp.types as mcp_types
import pytest

from orb.application.dto.interface_response import InterfaceResponse
from orb.interface.catalog import OPERATION_CATALOG, Interface
from orb.interface.mcp import catalog_server


def _mcp_tool_names() -> list[str]:
    """Catalog keys exposed on the MCP interface, sorted by key."""
    return [
        key for key, entry in sorted(OPERATION_CATALOG.items()) if Interface.MCP in entry.exposed_on
    ]


# --------------------------------------------------------------------------- #
# handle_mcp_validate                                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_validate_reports_all_catalog_tools_as_valid() -> None:
    """validate returns valid=True with the full MCP tool set and exit 0."""
    response = await catalog_server.handle_mcp_validate(SimpleNamespace())

    assert isinstance(response, InterfaceResponse)
    assert response.exit_code == 0
    assert response.data["valid"] is True
    expected_names = _mcp_tool_names()
    assert response.data["tool_count"] == len(expected_names)
    assert response.data["tools"] == expected_names
    assert "problems" not in response.data


@pytest.mark.asyncio
async def test_validate_flags_non_object_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool whose input schema is not an object schema is reported as a problem."""
    bad_tool = mcp_types.Tool(
        name="bad_tool",
        description="a tool with a non-object input schema",
        inputSchema={"type": "string"},
    )
    monkeypatch.setattr(catalog_server, "list_catalog_tools", lambda: [bad_tool])

    response = await catalog_server.handle_mcp_validate(SimpleNamespace())

    assert response.exit_code == 1
    assert response.data["valid"] is False
    assert response.data["tool_count"] == 1
    assert response.data["problems"]
    assert "bad_tool" in response.data["problems"][0]


@pytest.mark.asyncio
async def test_validate_flags_object_schema_without_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An object schema whose properties are not a mapping is reported as a problem."""
    bad_tool = mcp_types.Tool(
        name="propless_tool",
        description="an object schema with a non-object properties value",
        inputSchema={"type": "object", "properties": []},
    )
    monkeypatch.setattr(catalog_server, "list_catalog_tools", lambda: [bad_tool])

    response = await catalog_server.handle_mcp_validate(SimpleNamespace())

    assert response.exit_code == 1
    assert response.data["valid"] is False
    assert "no properties object" in response.data["problems"][0]


# --------------------------------------------------------------------------- #
# handle_mcp_serve                                                            #
# --------------------------------------------------------------------------- #


def _fake_application(*, initialize_result: bool = True) -> type:
    """A stand-in Application whose initialize is awaitable and container is a sentinel."""

    class FakeApplication:
        def __init__(self) -> None:
            self._container = sentinel.container

        async def initialize(self) -> bool:
            return initialize_result

        def _ensure_container(self) -> None:  # noqa: D401 — mirrors the real seam
            return None

    return FakeApplication


@pytest.fixture
def patched_serve(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch the transport runners, telemetry flush, and Application for serve tests."""
    import orb.bootstrap as bootstrap

    run_stdio = AsyncMock()
    run_streamable_http = Mock()
    flush = Mock()

    monkeypatch.setattr(catalog_server, "run_stdio", run_stdio)
    monkeypatch.setattr(catalog_server, "run_streamable_http", run_streamable_http)
    monkeypatch.setattr(catalog_server, "_flush_telemetry", flush)
    monkeypatch.setattr(bootstrap, "Application", _fake_application())

    return {
        "run_stdio": run_stdio,
        "run_streamable_http": run_streamable_http,
        "flush": flush,
        "bootstrap": bootstrap,
    }


@pytest.mark.asyncio
async def test_serve_default_transport_runs_stdio(patched_serve: dict[str, Any]) -> None:
    """The default transport serves over stdio with the wired container."""
    result = await catalog_server.handle_mcp_serve(SimpleNamespace())

    patched_serve["run_stdio"].assert_awaited_once_with(sentinel.container)
    patched_serve["run_streamable_http"].assert_not_called()
    assert result == {"message": "MCP server stopped (stdio)"}
    patched_serve["flush"].assert_called_once_with()


@pytest.mark.asyncio
async def test_serve_http_transport_runs_streamable_http(patched_serve: dict[str, Any]) -> None:
    """transport=http dispatches to the Streamable HTTP runner with host/port/path."""
    args = SimpleNamespace(transport="http", host="0.0.0.0", port=9001, path="/rpc")

    result = await catalog_server.handle_mcp_serve(args)

    patched_serve["run_streamable_http"].assert_called_once_with(
        sentinel.container, "0.0.0.0", 9001, "/rpc"
    )
    patched_serve["run_stdio"].assert_not_awaited()
    assert result == {"message": "MCP server stopped (0.0.0.0:9001/rpc)"}
    patched_serve["flush"].assert_called_once_with()


@pytest.mark.asyncio
async def test_serve_streamable_http_alias_normalizes_to_http(
    patched_serve: dict[str, Any],
) -> None:
    """The 'streamable-http' transport alias is normalized to the http path."""
    args = SimpleNamespace(transport="streamable-http")

    result = await catalog_server.handle_mcp_serve(args)

    patched_serve["run_streamable_http"].assert_called_once_with(
        sentinel.container, "127.0.0.1", 8000, "/mcp"
    )
    assert result == {"message": "MCP server stopped (127.0.0.1:8000/mcp)"}


@pytest.mark.asyncio
async def test_serve_raises_when_initialization_fails(
    monkeypatch: pytest.MonkeyPatch, patched_serve: dict[str, Any]
) -> None:
    """A failed application initialize raises RuntimeError and never serves."""
    monkeypatch.setattr(
        patched_serve["bootstrap"], "Application", _fake_application(initialize_result=False)
    )

    with pytest.raises(RuntimeError, match="Failed to initialize"):
        await catalog_server.handle_mcp_serve(SimpleNamespace())

    patched_serve["run_stdio"].assert_not_awaited()
    patched_serve["run_streamable_http"].assert_not_called()
    # The initialize guard raises before the serve try/finally is entered, so no
    # telemetry flush runs — there is nothing yet to clean up.
    patched_serve["flush"].assert_not_called()


# --------------------------------------------------------------------------- #
# run_stdio                                                                   #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_run_stdio_wires_streams_into_server_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_stdio hands the stdio read/write streams and init options to server.run."""
    import mcp.server.stdio as stdio_module

    server = MagicMock()
    server.run = AsyncMock()
    server.create_initialization_options.return_value = sentinel.init_options
    monkeypatch.setattr(catalog_server, "build_server", Mock(return_value=server))

    class FakeStdioServer:
        async def __aenter__(self) -> tuple[Any, Any]:
            return sentinel.read_stream, sentinel.write_stream

        async def __aexit__(self, *exc: Any) -> bool:
            return False

    monkeypatch.setattr(stdio_module, "stdio_server", Mock(return_value=FakeStdioServer()))

    await catalog_server.run_stdio(sentinel.container)

    server.run.assert_awaited_once_with(
        sentinel.read_stream, sentinel.write_stream, sentinel.init_options
    )


# --------------------------------------------------------------------------- #
# run_streamable_http                                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_run_streamable_http_serves_starlette_app_under_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_streamable_http mounts a Starlette app and runs it under uvicorn (no port bind).

    Also drives the app's lifespan and mounted ASGI handler so the session
    manager's run/handle_request wiring is exercised without a real request.
    """
    import contextlib

    import uvicorn
    from mcp.server import streamable_http_manager
    from starlette.applications import Starlette

    session_manager = MagicMock()
    session_manager.handle_request = AsyncMock()

    @contextlib.asynccontextmanager
    async def _run() -> Any:
        yield

    session_manager.run = Mock(side_effect=_run)
    monkeypatch.setattr(
        streamable_http_manager,
        "StreamableHTTPSessionManager",
        Mock(return_value=session_manager),
    )

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        uvicorn,
        "run",
        Mock(side_effect=lambda app, **kwargs: captured.update(app=app, kwargs=kwargs)),
    )

    catalog_server.run_streamable_http(sentinel.container, host="0.0.0.0", port=9002, path="/mcp")

    app = captured["app"]
    assert isinstance(app, Starlette)
    assert captured["kwargs"]["host"] == "0.0.0.0"
    assert captured["kwargs"]["port"] == 9002

    # Drive the lifespan so session_manager.run() is entered and exited.
    async with app.router.lifespan_context(app):
        session_manager.run.assert_called_once_with()

    # Drive the mounted ASGI handler so it delegates to handle_request.
    mount = app.routes[0]
    await mount.app(sentinel.scope, sentinel.receive, sentinel.send)
    session_manager.handle_request.assert_awaited_once_with(
        sentinel.scope, sentinel.receive, sentinel.send
    )


# --------------------------------------------------------------------------- #
# _flush_telemetry                                                            #
# --------------------------------------------------------------------------- #


def test_flush_telemetry_invokes_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    """_flush_telemetry calls the telemetry shutdown hook."""
    import orb.bootstrap.telemetry as telemetry

    shutdown = Mock()
    monkeypatch.setattr(telemetry, "shutdown_telemetry", shutdown)

    catalog_server._flush_telemetry()

    shutdown.assert_called_once_with()


def test_flush_telemetry_swallows_shutdown_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failure in the telemetry shutdown hook must not propagate out of cleanup."""
    import orb.bootstrap.telemetry as telemetry

    monkeypatch.setattr(
        telemetry, "shutdown_telemetry", Mock(side_effect=RuntimeError("otel down"))
    )

    # Must not raise.
    catalog_server._flush_telemetry()
