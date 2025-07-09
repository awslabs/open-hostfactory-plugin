"""AWS-specific machine value objects."""

from src.domain.machine.value_objects import *
from src.providers.aws.domain.template.value_objects import (
    AWSInstanceType,
    AWSTags,
    AWSImageId,
    AWSSubnetId,
    AWSSecurityGroupId
)

# Re-export all base machine value objects with AWS extensions
__all__ = [
    # Base machine value objects
    'MachineId',
    'MachineStatus', 
    'MachineHealth',
    'InstanceType',
    'PrivateIpAddress',
    'PublicIpAddress',
    'Tags',
    
    # AWS-specific extensions
    'AWSInstanceType',
    'AWSTags',
    'AWSImageId', 
    'AWSSubnetId',
    'AWSSecurityGroupId'
]
