"""Base Provider Handlers for CQRS Architecture Consistency.

The canonical definition of :class:`BaseProviderHandler` now lives in the
domain layer (:mod:`orb.domain.base.provider_handler_base`) so that provider
implementations can inherit from it without importing upward into the
application layer.  It is re-exported here for backward compatibility.
"""

from orb.domain.base.provider_handler_base import BaseProviderHandler

__all__ = ["BaseProviderHandler"]
