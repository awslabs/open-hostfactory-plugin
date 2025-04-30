# src/domain/template/value_objects.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import re
from src.domain.core.exceptions import ValidationError

class AWSHandlerType(str, Enum):
    """Supported AWS handler types."""
    EC2_FLEET = "EC2Fleet"
    SPOT_FLEET = "SpotFleet"
    ASG = "ASG"
    RUN_INSTANCES = "RunInstances"
    EC2_FLEET_INSTANT = "EC2FleetInstant"
    EC2_FLEET_MAINTAIN = "EC2FleetMaintain"
    EC2_FLEET_REQUEST = "EC2FleetRequest"
    SPOT_FLEET_REQUEST = "SpotFleetRequest"
    SPOT_FLEET_MAINTAIN = "SpotFleetMaintain"

    @classmethod
    def validate(cls, value: str) -> None:
        if value not in [e.value for e in cls]:
            raise ValidationError(f"Invalid AWS handler type: {value}")

class EC2FleetType(str, Enum):
    """EC2 Fleet type enumeration."""
    INSTANT = "instant"
    REQUEST = "request"
    MAINTAIN = "maintain"

class SpotFleetType(str, Enum):
    """Spot Fleet type enumeration."""
    REQUEST = "request"
    MAINTAIN = "maintain"

@dataclass(frozen=True)
class TemplateId:
    """Template identifier with validation."""
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise ValidationError("Template ID must be a string")
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.value):
            raise ValidationError(f"Invalid template ID format: {self.value}")

    def __str__(self) -> str:
        return self.value

@dataclass(frozen=True)
class TemplateAttributes:
    """Core attributes of a template with validation."""
    type: str
    ncores: int
    ncpus: int
    nram: int
    additional_attributes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.type, str):
            raise ValidationError("Type must be a string")
        if not isinstance(self.ncores, int) or self.ncores <= 0:
            raise ValidationError("Number of cores must be a positive integer")
        if not isinstance(self.ncpus, int) or self.ncpus <= 0:
            raise ValidationError("Number of CPUs must be a positive integer")
        if not isinstance(self.nram, int) or self.nram <= 0:
            raise ValidationError("RAM must be a positive integer")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": ["String", self.type],
            "ncores": ["Numeric", str(self.ncores)],
            "ncpus": ["Numeric", str(self.ncpus)],
            "nram": ["Numeric", str(self.nram)],
            **self.additional_attributes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TemplateAttributes':
        return cls(
            type=data.get("type", [None, None])[1],
            ncores=int(data.get("ncores", [None, "0"])[1]),
            ncpus=int(data.get("ncpus", [None, "0"])[1]),
            nram=int(data.get("nram", [None, "0"])[1]),
            additional_attributes={
                k: v for k, v in data.items() 
                if k not in ["type", "ncores", "ncpus", "nram"]
            }
        )

@dataclass(frozen=True)
class AWSConfiguration:
    """AWS-specific template configuration with validation."""
    image_id: str
    subnet_id: Optional[str] = None
    subnet_ids: Optional[List[str]] = None
    vm_type: Optional[str] = None
    vm_types: Optional[Dict[str, int]] = None
    security_group_ids: List[str] = field(default_factory=list)
    key_name: Optional[str] = None
    fleet_role: Optional[str] = None
    max_spot_price: Optional[float] = None
    allocation_strategy: Optional[str] = None
    instance_tags: Dict[str, str] = field(default_factory=dict)
    user_data: Optional[str] = None

    def __post_init__(self):
        if not self.image_id:
            raise ValidationError("Image ID is required")
        if not (self.subnet_id or self.subnet_ids):
            raise ValidationError("Either subnet_id or subnet_ids must be specified")
        if self.subnet_id and self.subnet_ids:
            raise ValidationError("Cannot specify both subnet_id and subnet_ids")
        if not (self.vm_type or self.vm_types):
            raise ValidationError("Either vm_type or vm_types must be specified")
        if not self.security_group_ids:
            raise ValidationError("At least one security group is required")
        if self.max_spot_price is not None and self.max_spot_price <= 0:
            raise ValidationError("Spot price must be greater than zero")
        if self.vm_types:
            for vm_type, weight in self.vm_types.items():
                if weight <= 0:
                    raise ValidationError(f"Weight for {vm_type} must be greater than zero")

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "imageId": self.image_id,
            "securityGroupIds": self.security_group_ids
        }
        
        if self.subnet_id:
            result["subnetId"] = self.subnet_id
        if self.subnet_ids:
            result["subnetIds"] = self.subnet_ids
        if self.vm_type:
            result["vmType"] = self.vm_type
        if self.vm_types:
            result["vmTypes"] = self.vm_types
        if self.key_name:
            result["keyName"] = self.key_name
        if self.fleet_role:
            result["fleetRole"] = self.fleet_role
        if self.max_spot_price is not None:
            result["maxSpotPrice"] = self.max_spot_price
        if self.allocation_strategy:
            result["allocationStrategy"] = self.allocation_strategy
        if self.instance_tags:
            result["instanceTags"] = self.instance_tags
        if self.user_data:
            result["userData"] = self.user_data
            
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AWSConfiguration':
        return cls(
            image_id=data["imageId"],
            subnet_id=data.get("subnetId"),
            subnet_ids=data.get("subnetIds"),
            vm_type=data.get("vmType"),
            vm_types=data.get("vmTypes"),
            security_group_ids=data.get("securityGroupIds", []),
            key_name=data.get("keyName"),
            fleet_role=data.get("fleetRole"),
            max_spot_price=data.get("maxSpotPrice"),
            allocation_strategy=data.get("allocationStrategy"),
            instance_tags=data.get("instanceTags", {}),
            user_data=data.get("userData")
        )