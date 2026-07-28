"""Provider Handler interface for CQRS pattern consistency.

The canonical definition now lives in the domain layer
(:mod:`orb.domain.base.provider_handler_base`) so that provider
implementations can depend on it without importing upward into the
application layer.  It is re-exported here for backward compatibility.
"""

from orb.domain.base.provider_handler_base import ProviderHandler

__all__ = ["ProviderHandler"]
