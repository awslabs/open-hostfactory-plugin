"""Resolve the request scheme from ``X-Forwarded-Proto`` behind a trusted proxy.

When ORB runs behind a reverse proxy / load balancer that terminates TLS and
forwards plain HTTP to the application, the ASGI ``scope["scheme"]`` seen by the
app is ``"http"`` even though the client spoke HTTPS to the proxy.  With
``require_https=True`` the ``HTTPSRedirectMiddleware`` would then issue a 307
redirect to ``https://``, the proxy would forward the follow-up request as
plain HTTP again, and the client would be trapped in an infinite redirect loop.

This middleware fixes the loop at its source: when the *direct* peer is a
configured trusted proxy, it rewrites ``scope["scheme"]`` from the
``X-Forwarded-Proto`` header before downstream middleware (including the HTTPS
redirect) inspect it.  Requests from untrusted peers are left untouched, so a
client cannot spoof the scheme to bypass HTTPS enforcement.

The trust model deliberately mirrors ``get_real_client_ip`` /
``trusted_proxies`` used by the auth and rate-limit middleware: the forwarded
header is only honoured when the connection originates from a known proxy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

_FORWARDABLE_SCHEMES = {"http", "https", "ws", "wss"}


class ForwardedProtoMiddleware:
    """Rewrite ``scope["scheme"]`` from ``X-Forwarded-Proto`` for trusted proxies.

    Args:
        app: The wrapped ASGI application.
        trusted_proxies: IP addresses of reverse proxies that are trusted to set
            the ``X-Forwarded-Proto`` header.  When empty the middleware is a
            no-op — the forwarded header is never honoured, so no client can
            influence the resolved scheme.
    """

    def __init__(self, app: ASGIApp, trusted_proxies: list[str] | None = None) -> None:
        self.app = app
        self._trusted_proxies: frozenset[str] = frozenset(trusted_proxies or [])

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] in ("http", "websocket")
            and self._trusted_proxies
            and self._direct_peer_is_trusted(scope)
        ):
            forwarded_proto = self._forwarded_proto(scope)
            if forwarded_proto in _FORWARDABLE_SCHEMES:
                # Normalise http/https to ws/wss for websocket connections so the
                # scheme stays consistent with the connection type.
                if scope["type"] == "websocket":
                    forwarded_proto = forwarded_proto.replace("http", "ws")
                scope["scheme"] = forwarded_proto
        await self.app(scope, receive, send)

    def _direct_peer_is_trusted(self, scope: Scope) -> bool:
        """Return True when the immediate connection peer is a trusted proxy."""
        client = scope.get("client")
        direct_ip = client[0] if client else None
        return bool(direct_ip and direct_ip in self._trusted_proxies)

    @staticmethod
    def _forwarded_proto(scope: Scope) -> str | None:
        """Return the last ``X-Forwarded-Proto`` value (lower-cased) or None."""
        value: str | None = None
        for name, raw in scope.get("headers", []):
            if name == b"x-forwarded-proto":
                # A proxy may append; the closest (rightmost/last) proxy's value
                # is the most reliable, matching the XFF right-to-left model.
                value = raw.decode("latin1").split(",")[-1].strip().lower()
        return value
