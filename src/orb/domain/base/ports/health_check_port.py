"""Port interface for health check monitoring."""

from abc import ABC, abstractmethod
from typing import Any


class HealthCheckPort(ABC):
    """Abstract port for health check monitoring."""

    @abstractmethod
    def register_check(
        self, name: str, check_fn: Any, *, force: bool = False, kind: str = "system"
    ) -> None:
        """Register a named health check function.

        ``force=True`` overwrites an existing registration. Without it,
        re-registering the same name is a no-op.

        ``kind`` classifies the check for readiness gating:

        * ``"core"``     — a core dependency (storage/database) whose failure
          means the service cannot serve requests. Gates ``get_readiness``.
        * ``"provider"`` — provider-API connectivity (aws, ec2, kubernetes_api).
          Surfaced in the full status but does NOT gate readiness, so an
          unreachable optional provider cannot take the service out of rotation.
        * ``"system"``   — host-level signals (cpu/disk); the default.
        """
        pass

    @abstractmethod
    def run_check(self, name: str) -> dict[str, Any]:
        """Run a specific health check by name and return its result."""
        pass

    @abstractmethod
    def run_all_checks(self) -> dict[str, Any]:
        """Run all registered health checks and return results."""
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Get the current health status summary."""
        pass

    @abstractmethod
    def get_readiness(self) -> dict[str, Any]:
        """Get the readiness status derived from core-dependency checks only.

        Provider-connectivity checks are excluded so an unreachable optional
        provider does not make the service report as not-ready.
        """
        pass
