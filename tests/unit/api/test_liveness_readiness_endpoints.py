"""Tests for the /livez and /readyz probe endpoints.

- /livez  : liveness — always 200 while the process is up; never gates
            on any dependency or provider.
- /readyz : readiness — 200 unless a CORE dependency (storage/database)
            is unhealthy; provider connectivity must NOT gate it.
- /health : unchanged full detail + status mapping (back-compat).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

import orb.api.dependencies as deps
from orb.api.server import create_fastapi_app
from orb.config.schemas.server_schema import AuthConfig, ServerConfig


def _make_client(health_port) -> TestClient:
    server_config = ServerConfig(  # type: ignore[call-arg]
        enabled=True,
        auth=AuthConfig(enabled=False, strategy="replace"),  # type: ignore[call-arg]
    )

    def _stub_routes(app):
        app.include_router(APIRouter())

    with patch("orb.api.server._register_routers") as mock_register:
        mock_register.side_effect = _stub_routes
        app = create_fastapi_app(server_config)
    app.dependency_overrides[deps.get_health_check_port] = lambda: health_port
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
@pytest.mark.api
class TestLivez:
    def test_livez_returns_200_when_up(self) -> None:
        health_port = MagicMock()
        client = _make_client(health_port)
        resp = client.get("/livez")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_livez_returns_200_even_when_dependency_unhealthy(self) -> None:
        """Liveness must never gate on dependency health."""
        health_port = MagicMock()
        health_port.get_readiness.return_value = {"status": "unhealthy"}
        health_port.get_status.return_value = {"status": "unhealthy"}
        client = _make_client(health_port)
        resp = client.get("/livez")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"
        # Liveness must not even consult dependency health.
        health_port.get_readiness.assert_not_called()


@pytest.mark.unit
@pytest.mark.api
class TestReadyz:
    def test_readyz_200_when_only_provider_unhealthy(self) -> None:
        """A failing provider-connectivity check must not fail readiness."""
        health_port = MagicMock()
        health_port.get_readiness.return_value = {"status": "healthy"}
        client = _make_client(health_port)
        resp = client.get("/readyz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_readyz_200_when_readiness_unknown(self) -> None:
        health_port = MagicMock()
        health_port.get_readiness.return_value = {"status": "unknown"}
        client = _make_client(health_port)
        resp = client.get("/readyz")
        assert resp.status_code == 200

    def test_readyz_503_when_readiness_degraded(self) -> None:
        """get_readiness only reports 'degraded' when a CORE check is degraded
        (e.g. the sole provider's connectivity, which fails as degraded). A
        degraded core dependency means not-ready → 503."""
        health_port = MagicMock()
        health_port.get_readiness.return_value = {"status": "degraded"}
        client = _make_client(health_port)
        resp = client.get("/readyz")
        assert resp.status_code == 503

    def test_readyz_503_when_core_dependency_unhealthy(self) -> None:
        health_port = MagicMock()
        health_port.get_readiness.return_value = {
            "status": "unhealthy",
            "checks": {"database": {"status": "unhealthy"}},
        }
        client = _make_client(health_port)
        resp = client.get("/readyz")
        assert resp.status_code == 503
        assert resp.json()["status"] == "unhealthy"

    def test_readyz_runs_checks_before_reading_readiness(self) -> None:
        health_port = MagicMock()
        health_port.get_readiness.return_value = {"status": "healthy"}
        client = _make_client(health_port)
        client.get("/readyz")
        health_port.run_all_checks.assert_called_once()


@pytest.mark.unit
@pytest.mark.api
class TestHealthUnchanged:
    def test_health_returns_full_body(self) -> None:
        health_port = MagicMock()
        health_port.get_status.return_value = {
            "status": "healthy",
            "checks": {"database": {"status": "healthy"}},
        }
        client = _make_client(health_port)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "open-resource-broker"
        assert "version" in data
        assert "checks" in data

    def test_health_200_when_provider_degraded(self) -> None:
        """After the provider-degraded change, a degraded provider keeps
        /health at 200 with its full detailed body."""
        health_port = MagicMock()
        health_port.get_status.return_value = {
            "status": "degraded",
            "checks": {"kubernetes_api": {"status": "degraded"}},
        }
        client = _make_client(health_port)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"

    def test_health_503_when_unhealthy(self) -> None:
        """Back-compat: an overall 'unhealthy' status still maps to 503."""
        health_port = MagicMock()
        health_port.get_status.return_value = {"status": "unhealthy"}
        client = _make_client(health_port)
        resp = client.get("/health")
        assert resp.status_code == 503
