"""Unit tests for the provider resource-discovery endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orb.api.dependencies import get_current_user
from orb.api.routers import providers as providers_module
from orb.api.routers.providers import router as providers_router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(*, role: str = "operator") -> FastAPI:
    from fastapi.responses import JSONResponse

    from orb.api.dependencies import CurrentUser
    from orb.infrastructure.error.exception_handler import get_exception_handler

    app = FastAPI()
    app.include_router(providers_router)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        username="test-user", role=role
    )
    exception_handler = get_exception_handler()

    @app.exception_handler(Exception)
    async def global_exception_handler(__request, exc):
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            raise exc
        error_response = exception_handler.handle_error_for_http(exc)
        return JSONResponse(
            status_code=error_response.http_status or 500,
            content={"detail": error_response.message},
        )

    return app


@pytest.fixture(autouse=True)
def _clear_discovery_cache():
    """Each test starts with an empty discovery cache."""
    providers_module._discovery_cache.clear()
    yield
    providers_module._discovery_cache.clear()


def _patch_registry(strategy):
    """Patch get_provider_registry so the endpoint resolves *strategy*."""
    registry = MagicMock()
    registry.ensure_provider_type_registered.return_value = True
    registry.get_or_create_strategy.return_value = strategy
    return patch(
        "orb.providers.registry.provider_registry.get_provider_registry",
        return_value=registry,
    )


# ---------------------------------------------------------------------------
# Auth guard — discovery requires operator role
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.api
class TestDiscoverAuthGuard:
    def test_viewer_is_forbidden(self):
        app = _make_app(role="viewer")
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/providers/discover/aws/vpcs")
        assert resp.status_code == 403

    def test_operator_allowed(self):
        strategy = MagicMock()
        strategy.list_resources.return_value = []
        app = _make_app(role="operator")
        with _patch_registry(strategy):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/providers/discover/aws/vpcs")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.api
class TestDiscoverHappyPath:
    def test_vpcs_returns_resources(self):
        strategy = MagicMock()
        strategy.list_resources.return_value = [
            {"id": "vpc-1", "name": "main", "cidr_block": "10.0.0.0/16", "is_default": True}
        ]
        app = _make_app()
        with _patch_registry(strategy):
            client = TestClient(app, raise_server_exceptions=False)
            body = client.get("/providers/discover/aws/vpcs").json()

        assert body["resource_type"] == "vpcs"
        assert body["provider_api"] == "aws"
        assert body["resources"][0]["id"] == "vpc-1"
        assert body["cached"] is False
        strategy.list_resources.assert_called_once_with("vpcs", None)

    def test_subnets_passes_vpc_id(self):
        strategy = MagicMock()
        strategy.list_resources.return_value = [{"id": "subnet-1"}]
        app = _make_app()
        with _patch_registry(strategy):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/providers/discover/aws/subnets?vpc_id=vpc-1")
        assert resp.status_code == 200
        strategy.list_resources.assert_called_once_with("subnets", "vpc-1")

    def test_security_groups_alias_normalised(self):
        strategy = MagicMock()
        strategy.list_resources.return_value = []
        app = _make_app()
        with _patch_registry(strategy):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/providers/discover/AWS/SECURITY_GROUPS?vpc_id=vpc-1")
        assert resp.status_code == 200
        assert resp.json()["resource_type"] == "security_groups"
        assert resp.json()["provider_api"] == "aws"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.api
class TestDiscoverValidation:
    def test_unsupported_resource_type_returns_400(self):
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/providers/discover/aws/gateways")
        assert resp.status_code == 400

    def test_subnets_without_vpc_id_returns_400(self):
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/providers/discover/aws/subnets")
        assert resp.status_code == 400

    def test_security_groups_without_vpc_id_returns_400(self):
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/providers/discover/aws/security_groups")
        assert resp.status_code == 400

    def test_unknown_provider_returns_404(self):
        registry = MagicMock()
        registry.ensure_provider_type_registered.return_value = False
        app = _make_app()
        with patch(
            "orb.providers.registry.provider_registry.get_provider_registry",
            return_value=registry,
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/providers/discover/nope/vpcs")
        assert resp.status_code == 404

    def test_provider_without_discovery_returns_404(self):
        strategy = MagicMock(spec=[])  # no list_resources attribute
        app = _make_app()
        with _patch_registry(strategy):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/providers/discover/aws/vpcs")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Caching (5-minute TTL)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.api
class TestDiscoverCaching:
    def test_second_call_is_served_from_cache(self):
        strategy = MagicMock()
        strategy.list_resources.return_value = [{"id": "vpc-1"}]
        app = _make_app()
        with _patch_registry(strategy):
            client = TestClient(app, raise_server_exceptions=False)
            first = client.get("/providers/discover/aws/vpcs").json()
            second = client.get("/providers/discover/aws/vpcs").json()

        assert first["cached"] is False
        assert second["cached"] is True
        # Underlying strategy only hit once — the second response is cached.
        strategy.list_resources.assert_called_once()

    def test_different_vpc_id_is_a_separate_cache_key(self):
        strategy = MagicMock()
        strategy.list_resources.return_value = [{"id": "subnet-1"}]
        app = _make_app()
        with _patch_registry(strategy):
            client = TestClient(app, raise_server_exceptions=False)
            client.get("/providers/discover/aws/subnets?vpc_id=vpc-1")
            client.get("/providers/discover/aws/subnets?vpc_id=vpc-2")

        assert strategy.list_resources.call_count == 2

    def test_expired_entry_triggers_refresh(self):
        strategy = MagicMock()
        strategy.list_resources.return_value = [{"id": "vpc-1"}]
        app = _make_app()
        with _patch_registry(strategy):
            client = TestClient(app, raise_server_exceptions=False)
            client.get("/providers/discover/aws/vpcs")
            # Force expiry by rewinding the stored timestamp beyond the TTL.
            key = ("aws", "vpcs", "")
            _, value = providers_module._discovery_cache[key]
            providers_module._discovery_cache[key] = (
                0.0,
                value,
            )
            body = client.get("/providers/discover/aws/vpcs").json()

        assert body["cached"] is False
        assert strategy.list_resources.call_count == 2

    def test_genuinely_empty_account_is_cached(self):
        # An account that legitimately has no resources returns [] with no error.
        # That empty result is a real success and should be cached for the TTL.
        strategy = MagicMock()
        strategy.list_resources.return_value = []
        app = _make_app()
        with _patch_registry(strategy):
            client = TestClient(app, raise_server_exceptions=False)
            first = client.get("/providers/discover/aws/vpcs").json()
            second = client.get("/providers/discover/aws/vpcs").json()

        assert first["resources"] == []
        assert first["cached"] is False
        assert second["cached"] is True
        strategy.list_resources.assert_called_once()

    def test_error_empty_is_not_cached_and_next_call_retries(self):
        # A swallowed AWS error must NOT be served as a cached empty result:
        # the first call errors (503), nothing is cached, and a subsequent call
        # re-attempts discovery rather than returning a stale empty answer.
        strategy = MagicMock()
        strategy.list_resources.side_effect = [
            RuntimeError("throttled: Rate exceeded"),
            [{"id": "vpc-1"}],
        ]
        app = _make_app()
        with _patch_registry(strategy):
            client = TestClient(app, raise_server_exceptions=False)
            first = client.get("/providers/discover/aws/vpcs")
            # The error must not have been cached as an empty success.
            assert ("aws", "vpcs", "") not in providers_module._discovery_cache
            second = client.get("/providers/discover/aws/vpcs")

        assert first.status_code >= 500
        assert second.status_code == 200
        body = second.json()
        assert body["resources"] == [{"id": "vpc-1"}]
        assert body["cached"] is False
        assert strategy.list_resources.call_count == 2
