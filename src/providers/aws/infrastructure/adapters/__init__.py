"""
AWS Adapters Package

This package contains AWS-specific adapters that implement domain ports.
All adapters follow the naming convention: AWS[Purpose]Adapter
"""

from .resource_manager_adapter import AWSResourceManagerAdapter
from .provisioning_adapter import AWSProvisioningAdapter
from .request_adapter import AWSRequestAdapter
from .machine_adapter import AWSMachineAdapter
from .template_adapter import AWSTemplateAdapter

__all__ = [
    "AWSResourceManagerAdapter",
    "AWSProvisioningAdapter",
    "AWSRequestAdapter",
    "AWSMachineAdapter",
    "AWSTemplateAdapter",
]
