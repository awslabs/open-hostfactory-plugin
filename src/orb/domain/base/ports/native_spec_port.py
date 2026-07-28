"""Port for the provider-neutral native-spec rendering service.

This port lets provider implementations resolve the generic native-spec
service from the DI container without importing the concrete application
service (``orb.application.services.native_spec_service.NativeSpecService``),
which would create a providers→application dependency.

The application service is registered against this port during DI bootstrap;
provider code depends only on the port.
"""

from abc import ABC, abstractmethod
from typing import Any


class NativeSpecPort(ABC):
    """Provider-neutral contract for native-spec rendering."""

    spec_renderer: Any
    logger: Any

    @abstractmethod
    def is_native_spec_enabled(self) -> bool:
        """Return whether native spec processing is enabled."""

    @abstractmethod
    def render_spec(self, spec: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Render ``spec`` with the supplied ``context``."""


__all__ = ["NativeSpecPort"]
