"""End-to-end RBAC enforcement tests over the full FastAPI application.

Where ``tests/unit/api/test_role_enforcement.py`` exercises ``require_role`` in
isolation by mounting a single router and overriding ``get_current_user``, this
module drives the *whole* authorization chain against an app built by
``create_fastapi_app`` with authentication enabled:

    minted JWT
      → AuthMiddleware.authenticate (real strategy)
        → request.state.user_roles / auth_result
          → get_current_user  (role resolution)
            → require_role(min_role)  (403 / pass)

Coverage:

- A role x resource allow/deny matrix across the four caller states the role
  model can produce (anonymous, viewer, operator, admin), verified through a
  real Authorization: Bearer header rather than a dependency override.
- The same matrix run against both JWT authentication strategies that populate
  ``AuthResult.roles`` (``bearer_token`` and ``bearer_token_enhanced``), so the
  claim-extraction → role-resolution → enforcement path is proven identical
  regardless of which strategy validated the token.
- The public/private boundary: ``/health`` must stay reachable without
  authentication, while ``/info`` sits behind the auth middleware when auth is
  enabled and is only public when auth is disabled.

No network and no real AWS: allow-path resources whose handlers would call an
orchestrator are stubbed via ``dependency_overrides`` so the assertion isolates
the authorization decision (allowed vs. 403) rather than downstream behaviour.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orb.api.dependencies as deps
from orb.api.server import create_fastapi_app
from orb.application.services.orchestration.dtos import (
    AcquireMachinesOutput,
    CancelRequestOutput,
    ReturnMachinesOutput,
)
from orb.config.schemas.server_schema import AuthConfig, CORSConfig, ServerConfig
from orb.interface.response_formatting_service import ResponseFormattingService

# A 32+ byte secret satisfies the strategy's minimum-strength check.
_SECRET = "test-secret-key-minimum-32-bytes-long!!"
_API = "/api/v1"

# The two JWT strategies that read canonical roles/permissions claims.  Both
# route claim reads through extract_authz_claims, so RBAC must behave
# identically for either.  Parametrising here proves that invariant.
_STRATEGIES = ["bearer_token", "bearer_token_enhanced"]


# ---------------------------------------------------------------------------
# Token minting
#
# Both strategies verify HS256-signed JWTs with the canonical claim shape
# ({"sub", "roles", "permissions", "type", "iat", "exp", "iss"}).  Minting the
# token directly (rather than via a strategy instance) keeps the enhanced
# strategy's denylist/rate-limiter construction out of the test and produces a
# token accepted by whichever strategy the app was built with.
# ---------------------------------------------------------------------------


def _mint(roles: list[str], permissions: list[str] | None = None) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "test-user",
            "roles": roles,
            "permissions": permissions or [],
            "type": "access",
            "iat": now,
            "exp": now + 3600,
            "iss": "open-resource-broker",
        },
        _SECRET,
        algorithm="HS256",
    )


def _auth_header(roles: list[str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {_mint(roles)}"}


# ---------------------------------------------------------------------------
# App construction
# ---------------------------------------------------------------------------


def _build_app(strategy: str) -> FastAPI:
    """Build the full app with auth enabled for the given JWT strategy."""
    server_config = ServerConfig(  # type: ignore[call-arg]
        enabled=True,
        auth=AuthConfig(  # type: ignore[call-arg]
            enabled=True,
            strategy=strategy,
            bearer_token={"secret_key": _SECRET, "algorithm": "HS256"},
        ),
        cors=CORSConfig(origins=["*"]),  # type: ignore[call-arg]
    )
    return create_fastapi_app(server_config)


def _stub_formatter() -> ResponseFormattingService:
    """A ResponseFormattingService whose scheduler returns empty envelopes.

    Allow-path handlers render their output through the formatter's scheduler;
    stubbing every format_* method to a benign shape lets the request reach a
    2xx without exercising a real scheduler.
    """
    scheduler = MagicMock()
    scheduler.format_request_response.return_value = {}
    scheduler.format_request_status_response.return_value = {"requests": []}
    scheduler.format_machine_status_response.return_value = {"machines": []}
    scheduler.format_templates_response.return_value = {"templates": []}
    scheduler.format_template_mutation_response.return_value = {}
    scheduler.get_exit_code_for_status.return_value = 0
    return ResponseFormattingService(scheduler)


def _install_allow_path_stubs(app: FastAPI) -> None:
    """Override orchestrators/formatter so allow-path routes return non-403.

    Only the dependencies needed by the routes under test are stubbed.  The
    role gate runs *before* these dependencies resolve for a denied caller, so
    denied cases never touch them; they exist purely so an authorised caller
    reaches a success/near-success response instead of a DI-resolution 500.
    """
    acquire = AsyncMock()
    acquire.execute = AsyncMock(
        return_value=AcquireMachinesOutput(request_id="req-1", status="pending", machine_ids=[])
    )
    ret = AsyncMock()
    ret.execute = AsyncMock(return_value=ReturnMachinesOutput(request_id="req-2", status="pending"))
    cancel = AsyncMock()
    cancel.execute = AsyncMock(
        return_value=CancelRequestOutput(request_id="req-3", status="cancelled")
    )
    refresh = AsyncMock()
    refresh.execute = AsyncMock(return_value=MagicMock(templates=[]))

    app.dependency_overrides[deps.get_acquire_machines_orchestrator] = lambda: acquire
    app.dependency_overrides[deps.get_return_machines_orchestrator] = lambda: ret
    app.dependency_overrides[deps.get_cancel_request_orchestrator] = lambda: cancel
    app.dependency_overrides[deps.get_refresh_templates_orchestrator] = lambda: refresh
    app.dependency_overrides[deps.get_request_formatter] = _stub_formatter


# ---------------------------------------------------------------------------
# Role x resource allow/deny matrix
#
# Each entry: (label, method, path, json body, minimum role required).
# The path is the *live* mounted path including the /api/v1 prefix.
# ---------------------------------------------------------------------------

# (label, method, path, body, required_role)
_MATRIX: list[tuple[str, str, str, dict | None, str]] = [
    ("machines.list", "GET", f"{_API}/machines/", None, "viewer"),
    ("templates.list", "GET", f"{_API}/templates/", None, "viewer"),
    ("system.dashboard", "GET", f"{_API}/system/dashboard", None, "viewer"),
    (
        "machines.request",
        "POST",
        f"{_API}/machines/request",
        {"template_id": "t-1", "count": 1},
        "operator",
    ),
    (
        "machines.return",
        "POST",
        f"{_API}/machines/return",
        {"machine_ids": ["m-1"]},
        "operator",
    ),
    ("requests.cancel", "DELETE", f"{_API}/requests/req-1", None, "operator"),
    ("templates.refresh", "POST", f"{_API}/templates/refresh", None, "admin"),
    ("machines.purge", "DELETE", f"{_API}/machines/m-1", None, "admin"),
]

# The four caller states the role model produces, ordered by rank.  "anonymous"
# means *no* Authorization header (the middleware rejects it before any route
# dependency runs); the rest are authenticated callers carrying that role claim.
_CALLERS = ["anonymous", "viewer", "operator", "admin"]

_RANK = {"viewer": 1, "operator": 2, "admin": 3}


def _rank_of(caller: str) -> int:
    """Effective rank of a caller state (anonymous is below viewer)."""
    return _RANK.get(caller, 0)


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.security
class TestRBACMatrixEndToEnd:
    """Allow/deny for every (caller, resource) pair, over both JWT strategies."""

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    @pytest.mark.parametrize(
        "label,method,path,body,required_role",
        [pytest.param(lbl, m, p, b, rr, id=f"{lbl}:needs-{rr}") for lbl, m, p, b, rr in _MATRIX],
    )
    @pytest.mark.parametrize("caller", _CALLERS)
    def test_role_resource_matrix(
        self,
        strategy: str,
        caller: str,
        label: str,
        method: str,
        path: str,
        body: dict | None,
        required_role: str,
    ) -> None:
        """A caller reaches a resource iff its rank meets the resource minimum.

        Below-minimum callers (including anonymous, with no token) must be
        blocked — 401 when unauthenticated, 403 when authenticated but
        under-privileged.  At-or-above callers must not be blocked with 403.
        """
        app = _build_app(strategy)
        _install_allow_path_stubs(app)
        client = TestClient(app, raise_server_exceptions=False)

        headers = {} if caller == "anonymous" else _auth_header([caller])
        # Build the request with the caller's header applied.
        if method == "GET":
            resp = client.get(path, headers=headers)
        elif method == "POST":
            resp = client.post(path, json=body or {}, headers=headers)
        elif method == "DELETE":
            resp = client.delete(path, headers=headers)
        else:
            resp = client.request(method, path, json=body, headers=headers)

        allowed = _rank_of(caller) >= _RANK[required_role]

        if allowed:
            assert resp.status_code != 403, (
                f"[{strategy}] {caller} should be allowed on {label} "
                f"(needs {required_role}) but got 403"
            )
            assert resp.status_code != 401, (
                f"[{strategy}] {caller} presented a valid token for {label} but got 401"
            )
        elif caller == "anonymous":
            # No credentials → the auth middleware rejects before the route.
            assert resp.status_code == 401, (
                f"[{strategy}] anonymous caller must get 401 on {label}, got {resp.status_code}"
            )
        else:
            # Authenticated but under-privileged → the role gate returns 403.
            assert resp.status_code == 403, (
                f"[{strategy}] {caller} (needs {required_role}) must get 403 "
                f"on {label}, got {resp.status_code}"
            )


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.security
class TestRBACIdentityIntrospection:
    """GET /me reflects the role derived from the token, per strategy."""

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    @pytest.mark.parametrize(
        "roles_claim,expected_role",
        [
            (["viewer"], "viewer"),
            (["operator"], "operator"),
            (["admin"], "admin"),
            (["orb-admin"], "admin"),
            (["orb-operator"], "operator"),
            # Unknown claim resolves to least privilege, never elevated.
            (["something-unmapped"], "viewer"),
            # No role claim at all → least privilege.
            ([], "viewer"),
        ],
    )
    def test_me_reports_resolved_role(
        self, strategy: str, roles_claim: list[str], expected_role: str
    ) -> None:
        app = _build_app(strategy)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"{_API}/me/", headers=_auth_header(roles_claim))
        assert resp.status_code == 200, (
            f"[{strategy}] /me should return 200 for roles={roles_claim}, got {resp.status_code}"
        )
        assert resp.json()["role"] == expected_role

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_me_requires_authentication(self, strategy: str) -> None:
        """Unauthenticated /me is rejected by the middleware (401)."""
        app = _build_app(strategy)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"{_API}/me/")
        assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.security
class TestRBACPublicEndpoints:
    """Endpoints that must stay reachable without authentication."""

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_health_is_public(self, strategy: str) -> None:
        app = _build_app(strategy)
        # /health resolves a health-check port; stub it so we get a clean 200.
        health_port = MagicMock()
        health_port.get_status.return_value = {"status": "healthy"}
        app.dependency_overrides[deps.get_health_check_port] = lambda: health_port
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.status_code != 401

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_info_requires_auth_when_enabled(self, strategy: str) -> None:
        """/info is NOT public when auth is enabled — only /health is.

        This pins the public/private boundary: /health is an unauthenticated
        liveness probe, but /info (which could disclose service metadata) sits
        behind the auth middleware and returns 401 without a token.
        """
        app = _build_app(strategy)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/info")
        assert resp.status_code == 401

    def test_info_is_public_when_auth_disabled(self) -> None:
        """With auth disabled, /info is reachable without credentials."""
        server_config = ServerConfig(  # type: ignore[call-arg]
            enabled=True,
            auth=AuthConfig(enabled=False),  # type: ignore[call-arg]
        )
        app = create_fastapi_app(server_config)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/info")
        assert resp.status_code == 200


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.security
class TestRBACInvalidCredentials:
    """A malformed or unsigned token is rejected before the role gate."""

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_garbage_token_is_401_not_403(self, strategy: str) -> None:
        """An invalid token yields 401 (authn failure), never a role 403.

        This proves authentication runs ahead of authorization: a caller who
        never authenticated cannot reach the role gate at all.
        """
        app = _build_app(strategy)
        _install_allow_path_stubs(app)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            f"{_API}/machines/",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert resp.status_code == 401

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_token_signed_with_wrong_secret_is_401(self, strategy: str) -> None:
        """A well-formed JWT signed with the wrong key is rejected (401)."""
        now = int(time.time())
        forged = jwt.encode(
            {
                "sub": "attacker",
                "roles": ["admin"],
                "permissions": [],
                "type": "access",
                "iat": now,
                "exp": now + 3600,
                "iss": "open-resource-broker",
            },
            "a-completely-different-secret-key-32bytes!!",
            algorithm="HS256",
        )
        app = _build_app(strategy)
        _install_allow_path_stubs(app)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"{_API}/templates/refresh",
            headers={"Authorization": f"Bearer {forged}"},
        )
        # Forged admin claim must not grant admin access — signature check fails.
        assert resp.status_code == 401
