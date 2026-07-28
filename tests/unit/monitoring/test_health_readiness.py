"""Unit tests for readiness classification of health checks.

Readiness (``/readyz``) must gate only on CORE dependency checks
(storage / database).  Provider-connectivity checks (aws, ec2,
kubernetes_api) must NOT gate readiness, so an unreachable optional
provider cannot take the whole service out of rotation.

The classification is explicit: ``register_check`` accepts a ``kind``
argument (``"core"`` | ``"provider"`` | ``"system"``) and
``get_readiness`` derives its status from the ``core`` checks only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orb.monitoring.health import HealthCheck, HealthCheckConfig, HealthStatus


def _config(tmp_path: Path) -> HealthCheckConfig:
    return HealthCheckConfig(health_dir=tmp_path / "health")


def _make_health_check(tmp_path: Path) -> HealthCheck:
    return HealthCheck(config=_config(tmp_path))


@pytest.mark.unit
class TestReadinessClassification:
    def test_register_check_accepts_kind(self, tmp_path) -> None:
        hc = _make_health_check(tmp_path)
        hc.register_check(
            "myprovider",
            lambda: HealthStatus("myprovider", "healthy", {}),
            kind="provider",
        )
        assert "myprovider" in hc.checks

    def test_provider_failure_does_not_affect_readiness(self, tmp_path) -> None:
        """An unhealthy provider-connectivity check leaves readiness healthy."""
        hc = _make_health_check(tmp_path)
        hc.register_check(
            "database",
            lambda: HealthStatus("database", "healthy", {}),
            kind="core",
            force=True,
        )
        hc.register_check(
            "kubernetes_api",
            lambda: HealthStatus("kubernetes_api", "unhealthy", {"error": "unreachable"}),
            kind="provider",
        )
        hc.run_check("database")
        hc.run_check("kubernetes_api")

        readiness = hc.get_readiness()
        assert readiness["status"] == "healthy"

    def test_core_dependency_failure_makes_readiness_unhealthy(self, tmp_path) -> None:
        """An unhealthy CORE (database) check makes readiness unhealthy."""
        hc = _make_health_check(tmp_path)
        hc.register_check(
            "database",
            lambda: HealthStatus("database", "unhealthy", {"error": "conn lost"}),
            kind="core",
            force=True,
        )
        hc.register_check(
            "aws",
            lambda: HealthStatus("aws", "healthy", {}),
            kind="provider",
        )
        hc.run_check("database")
        hc.run_check("aws")

        readiness = hc.get_readiness()
        assert readiness["status"] == "unhealthy"

    def test_degraded_provider_does_not_affect_readiness(self, tmp_path) -> None:
        hc = _make_health_check(tmp_path)
        hc.register_check(
            "database",
            lambda: HealthStatus("database", "healthy", {}),
            kind="core",
            force=True,
        )
        hc.register_check(
            "aws",
            lambda: HealthStatus("aws", "degraded", {"error": "unreachable"}),
            kind="provider",
        )
        hc.run_check("database")
        hc.run_check("aws")

        readiness = hc.get_readiness()
        assert readiness["status"] == "healthy"

    def test_readiness_unknown_when_no_core_checks_run(self, tmp_path) -> None:
        """With no core-check history, readiness derives to 'unknown'
        rather than being dragged down by provider checks."""
        hc = _make_health_check(tmp_path)
        hc.register_check(
            "aws",
            lambda: HealthStatus("aws", "unhealthy", {}),
            kind="provider",
        )
        hc.run_check("aws")

        readiness = hc.get_readiness()
        assert readiness["status"] == "unknown"

    def test_get_status_still_reflects_all_checks(self, tmp_path) -> None:
        """get_status (backing /health) is unchanged: any unhealthy check —
        including a provider one — still surfaces in the overall status."""
        hc = _make_health_check(tmp_path)
        hc.register_check(
            "database",
            lambda: HealthStatus("database", "healthy", {}),
            kind="core",
            force=True,
        )
        hc.register_check(
            "aws",
            lambda: HealthStatus("aws", "degraded", {}),
            kind="provider",
        )
        hc.run_check("database")
        hc.run_check("aws")

        status = hc.get_status()
        # Provider degraded still surfaces in the full /health body.
        assert status["status"] == "degraded"
        assert "aws" in status["checks"]
        assert "database" in status["checks"]


@pytest.mark.unit
class TestSoleProviderReadinessGating:
    """Sole enabled provider gates readiness (kind='core'); multi-provider does not.

    A connectivity failure surfaces as 'degraded'. When the provider is the sole
    enabled instance its check is registered kind='core', so a degraded sole
    provider makes readiness 'degraded' (which /readyz maps to 503). With
    multiple providers the connectivity check is kind='provider' and does not
    gate readiness.
    """

    def test_sole_provider_unreachable_makes_readiness_not_ready(self, tmp_path) -> None:
        hc = _make_health_check(tmp_path)
        hc.register_check(
            "database",
            lambda: HealthStatus("database", "healthy", {}),
            kind="core",
            force=True,
        )
        # Sole provider → its connectivity is core; unreachable = degraded.
        hc.register_check(
            "aws",
            lambda: HealthStatus("aws", "degraded", {"error": "unreachable"}),
            kind="core",
        )
        hc.run_check("database")
        hc.run_check("aws")

        readiness = hc.get_readiness()
        # 'degraded' core dependency → /readyz maps this to 503 (not-ready).
        assert readiness["status"] == "degraded"

    def test_multi_provider_secondary_unreachable_stays_ready(self, tmp_path) -> None:
        hc = _make_health_check(tmp_path)
        hc.register_check(
            "database",
            lambda: HealthStatus("database", "healthy", {}),
            kind="core",
            force=True,
        )
        # Multiple providers: default healthy (core-not; provider), secondary
        # unreachable (provider). Neither provider check gates readiness.
        hc.register_check(
            "aws",
            lambda: HealthStatus("aws", "healthy", {}),
            kind="provider",
        )
        hc.register_check(
            "kubernetes_api",
            lambda: HealthStatus("kubernetes_api", "degraded", {"error": "unreachable"}),
            kind="provider",
        )
        hc.run_check("database")
        hc.run_check("aws")
        hc.run_check("kubernetes_api")

        readiness = hc.get_readiness()
        assert readiness["status"] == "healthy"

    def test_multi_provider_default_unreachable_stays_ready(self, tmp_path) -> None:
        """Intended: with multiple providers even the DEFAULT provider's
        connectivity is non-core, so a degraded default does NOT gate readiness.
        Only a sole-provider deployment gates on provider connectivity."""
        hc = _make_health_check(tmp_path)
        hc.register_check(
            "database",
            lambda: HealthStatus("database", "healthy", {}),
            kind="core",
            force=True,
        )
        # Default provider connectivity registered kind='provider' (multi mode).
        hc.register_check(
            "aws",
            lambda: HealthStatus("aws", "degraded", {"error": "unreachable"}),
            kind="provider",
        )
        hc.run_check("database")
        hc.run_check("aws")

        readiness = hc.get_readiness()
        assert readiness["status"] == "healthy"
