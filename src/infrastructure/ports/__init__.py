"""
Domain Ports Package

This package contains interfaces (ports) that define the boundaries between
the domain layer and the infrastructure layer, following the Port-Adapter pattern
from Hexagonal Architecture.

Ports define what the domain needs from the outside world without specifying
how those needs are fulfilled. This allows the domain to remain independent
of infrastructure concerns.
"""

from .resource_provisioning_port import ResourceProvisioningPort
from .cloud_resource_manager_port import CloudResourceManagerPort
from .request_adapter_port import RequestAdapterPort
from .logger_port import LoggerPort

__all__ = [
    "ResourceProvisioningPort",
    "CloudResourceManagerPort",
    "RequestAdapterPort",
    "LoggerPort",
]
