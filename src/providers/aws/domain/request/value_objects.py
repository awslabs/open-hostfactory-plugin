"""AWS-specific request value objects."""

from src.domain.request.value_objects import *
from src.providers.aws.domain.template.value_objects import (
    AWSFleetId,
    AWSImageId,
    AWSInstanceType,
    AWSLaunchTemplateId,
    AWSSecurityGroupId,
    AWSSubnetId,
    AWSTags,
)

# Re-export all base request value objects with AWS extensions
__all__ = [
    # Base request value objects
    "RequestId",
    "RequestStatus",
    "RequestType",
    "Priority",
    "ResourceId",
    "InstanceId",
    "Tags",
    # AWS-specific extensions
    "AWSInstanceType",
    "AWSTags",
    "AWSImageId",
    "AWSSubnetId",
    "AWSSecurityGroupId",
    "AWSFleetId",
    "AWSLaunchTemplateId",
]
