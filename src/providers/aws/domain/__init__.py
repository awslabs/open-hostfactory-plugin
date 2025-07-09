"""AWS-specific domain extensions."""

# Import AWS-specific value objects from their respective modules
from .template.value_objects import (
    AWSImageId,
    AWSSubnetId, 
    AWSSecurityGroupId,
    AWSFleetId,
    AWSLaunchTemplateId,
)

__all__ = [
    'AWSImageId',
    'AWSSubnetId',
    'AWSSecurityGroupId', 
    'AWSFleetId',
    'AWSLaunchTemplateId',
]
