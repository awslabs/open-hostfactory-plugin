"""Unit tests for ForwardedProtoMiddleware at the ASGI-scope level.

The HTTP redirect-loop behaviour is covered end-to-end in
tests/security/test_https_enforcement.py.  These tests drive the middleware
directly at the ASGI seam so the branches that a TestClient cannot easily reach
— websocket scheme normalisation, untrusted-peer skip, missing/invalid headers,
and the empty-trusted-proxies no-op — are exercised as real behaviour.
"""

from __future__ import annotations

import pytest

from orb.api.middleware.forwarded_proto_middleware import ForwardedProtoMiddleware


async def _run(middleware: ForwardedProtoMiddleware, scope: dict) -> dict:
    """Invoke the middleware; return the (possibly mutated) scope the app saw."""
    seen: dict = {}

    async def _app(inner_scope, receive, send):
        seen["scope"] = inner_scope

    middleware.app = _app  # type: ignore[assignment]

    async def _receive():  # pragma: no cover - never awaited in these tests
        return {"type": "http.request"}

    async def _send(_message):  # pragma: no cover - app sends nothing
        return None

    await middleware(scope, _receive, _send)
    return seen["scope"]


def _http_scope(*, client_ip: str | None, xfp: bytes | None, scheme: str = "http") -> dict:
    headers: list[tuple[bytes, bytes]] = []
    if xfp is not None:
        headers.append((b"x-forwarded-proto", xfp))
    return {
        "type": "http",
        "scheme": scheme,
        "client": (client_ip, 12345) if client_ip else None,
        "headers": headers,
    }


@pytest.mark.unit
@pytest.mark.api
class TestForwardedProtoScopeRewrite:
    @pytest.mark.asyncio
    async def test_trusted_proxy_https_rewrites_scheme(self):
        mw = ForwardedProtoMiddleware(None, trusted_proxies=["10.0.0.1"])  # type: ignore[arg-type]
        scope = _http_scope(client_ip="10.0.0.1", xfp=b"https")
        result = await _run(mw, scope)
        assert result["scheme"] == "https"

    @pytest.mark.asyncio
    async def test_untrusted_peer_leaves_scheme_untouched(self):
        mw = ForwardedProtoMiddleware(None, trusted_proxies=["10.0.0.1"])  # type: ignore[arg-type]
        # Header says https but the direct peer is not a trusted proxy.
        scope = _http_scope(client_ip="203.0.113.9", xfp=b"https")
        result = await _run(mw, scope)
        assert result["scheme"] == "http"

    @pytest.mark.asyncio
    async def test_no_trusted_proxies_is_noop(self):
        mw = ForwardedProtoMiddleware(None, trusted_proxies=[])  # type: ignore[arg-type]
        scope = _http_scope(client_ip="10.0.0.1", xfp=b"https")
        result = await _run(mw, scope)
        assert result["scheme"] == "http"

    @pytest.mark.asyncio
    async def test_missing_header_leaves_scheme_untouched(self):
        mw = ForwardedProtoMiddleware(None, trusted_proxies=["10.0.0.1"])  # type: ignore[arg-type]
        scope = _http_scope(client_ip="10.0.0.1", xfp=None)
        result = await _run(mw, scope)
        assert result["scheme"] == "http"

    @pytest.mark.asyncio
    async def test_unknown_scheme_value_is_ignored(self):
        mw = ForwardedProtoMiddleware(None, trusted_proxies=["10.0.0.1"])  # type: ignore[arg-type]
        scope = _http_scope(client_ip="10.0.0.1", xfp=b"gopher")
        result = await _run(mw, scope)
        assert result["scheme"] == "http"

    @pytest.mark.asyncio
    async def test_appended_header_uses_rightmost_value(self):
        """A proxy may append; the closest (rightmost) value is authoritative."""
        mw = ForwardedProtoMiddleware(None, trusted_proxies=["10.0.0.1"])  # type: ignore[arg-type]
        scope = _http_scope(client_ip="10.0.0.1", xfp=b"http, https")
        result = await _run(mw, scope)
        assert result["scheme"] == "https"

    @pytest.mark.asyncio
    async def test_missing_client_is_treated_as_untrusted(self):
        mw = ForwardedProtoMiddleware(None, trusted_proxies=["10.0.0.1"])  # type: ignore[arg-type]
        scope = _http_scope(client_ip=None, xfp=b"https")
        result = await _run(mw, scope)
        assert result["scheme"] == "http"


@pytest.mark.unit
@pytest.mark.api
class TestForwardedProtoWebsocketNormalisation:
    @pytest.mark.asyncio
    async def test_websocket_https_normalised_to_wss(self):
        """For a websocket connection the http/https scheme maps to ws/wss."""
        mw = ForwardedProtoMiddleware(None, trusted_proxies=["10.0.0.1"])  # type: ignore[arg-type]
        scope = {
            "type": "websocket",
            "scheme": "ws",
            "client": ("10.0.0.1", 5555),
            "headers": [(b"x-forwarded-proto", b"https")],
        }
        result = await _run(mw, scope)
        assert result["scheme"] == "wss"

    @pytest.mark.asyncio
    async def test_websocket_http_normalised_to_ws(self):
        mw = ForwardedProtoMiddleware(None, trusted_proxies=["10.0.0.1"])  # type: ignore[arg-type]
        scope = {
            "type": "websocket",
            "scheme": "wss",
            "client": ("10.0.0.1", 5555),
            "headers": [(b"x-forwarded-proto", b"http")],
        }
        result = await _run(mw, scope)
        assert result["scheme"] == "ws"

    @pytest.mark.asyncio
    async def test_lifespan_scope_passes_through_untouched(self):
        """Non-http/websocket scopes (e.g. lifespan) are ignored."""
        mw = ForwardedProtoMiddleware(None, trusted_proxies=["10.0.0.1"])  # type: ignore[arg-type]
        scope = {"type": "lifespan"}
        result = await _run(mw, scope)
        assert "scheme" not in result
