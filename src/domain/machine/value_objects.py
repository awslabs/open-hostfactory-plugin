"""Machine-specific value objects orchestrator.

This module provides a unified interface to all machine value objects organized by category:
- Machine status (MachineStatus)
- Machine identifiers and core types (MachineId, MachineType)
- Machine metadata and configuration (PriceType, MachineConfiguration, MachineEvent, HealthCheck, etc.)
"""

# Import all value objects from specialized modules
from .machine_status import MachineStatus

from .machine_identifiers import MachineId, MachineType

from .machine_metadata import (
    PriceType,
    MachineConfiguration,
    MachineEvent,
    HealthCheck,
    IPAddressRange,
    MachineMetadata,
    HealthCheckResult,
    ResourceTag,
)

# Export all value objects
__all__ = [
    # Machine status
    "MachineStatus",
    # Machine identifiers and core types
    "MachineId",
    "MachineType",
    # Machine metadata and configuration
    "PriceType",
    "MachineConfiguration",
    "MachineEvent",
    "HealthCheck",
    "IPAddressRange",
    "MachineMetadata",
    "HealthCheckResult",
    "ResourceTag",
]
