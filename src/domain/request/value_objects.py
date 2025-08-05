"""Request-specific value objects orchestrator.

This module provides a unified interface to all request value objects organized by category:
- Request types and statuses (RequestType, RequestStatus, MachineResult)
- Request identifiers (RequestId, MachineReference, ResourceIdentifier)
- Request metadata and configuration (RequestTimeout, MachineCount, RequestTag, etc.)
"""

from .request_identifiers import MachineReference, RequestId, ResourceIdentifier
from .request_metadata import (
    LaunchTemplateInfo,
    MachineCount,
    RequestConfiguration,
    RequestTag,
    RequestTimeout,
)

# Import all value objects from specialized modules
from .request_types import MachineResult, RequestStatus, RequestType

# Export all value objects
__all__ = [
    # Request types and statuses
    "RequestType",
    "RequestStatus",
    "MachineResult",
    # Request identifiers
    "RequestId",
    "MachineReference",
    "ResourceIdentifier",
    # Request metadata and configuration
    "RequestTimeout",
    "MachineCount",
    "RequestTag",
    "RequestConfiguration",
    "LaunchTemplateInfo",
    "RequestEvent",
]
