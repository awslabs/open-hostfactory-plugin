from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from src.domain.template.value_objects import TemplateId
from src.domain.template.exceptions import TemplateValidationError
from src.domain.core.common_types import Tags

@dataclass
class Template:
    """Template aggregate root."""
    template_id: str
    aws_handler: str
    max_number: int
    attributes: Dict[str, Any]
    image_id: str
    subnet_id: Optional[str] = None
    subnet_ids: Optional[List[str]] = None
    vm_type: Optional[str] = None
    vm_types: Optional[Dict[str, int]] = None
    key_name: Optional[str] = None
    security_group_ids: List[str] = field(default_factory=list)
    instance_tags: Dict[str, str] = field(default_factory=dict)
    fleet_role: Optional[str] = None
    max_spot_price: Optional[float] = None
    allocation_strategy: Optional[str] = None
    user_data: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    fleet_type: Optional[str] = None

    def __post_init__(self):
        """Post initialization validation."""
        # Initialize tags if not present in instance_tags
        if not self.tags and self.instance_tags:
            self.tags = self.instance_tags.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, Any], validate: bool = False) -> 'Template':
        """Create template from dictionary."""
        template = cls(
            template_id=data["templateId"],
            aws_handler=data["awsHandler"],
            max_number=data["maxNumber"],
            attributes=data["attributes"],
            image_id=data["imageId"],
            subnet_id=data.get("subnetId"),
            subnet_ids=data.get("subnetIds"),
            vm_type=data.get("vmType"),
            vm_types=data.get("vmTypes"),
            key_name=data.get("keyName"),
            security_group_ids=data.get("securityGroupIds", []),
            instance_tags=data.get("instanceTags", {}),
            fleet_role=data.get("fleetRole"),
            max_spot_price=data.get("maxSpotPrice"),
            allocation_strategy=data.get("allocationStrategy"),
            user_data=data.get("userData"),
            tags=data.get("tags", {}),
            fleet_type=data.get("fleetType")
        )
        
        if validate:
            template.validate()
        
        return template

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        result = {
            "templateId": self.template_id,
            "awsHandler": self.aws_handler,
            "maxNumber": self.max_number,
            "attributes": self.attributes,
            "imageId": self.image_id,
            "securityGroupIds": self.security_group_ids,
            "instanceTags": self.instance_tags,
            "fleetRole": self.fleet_role,
            "tags": self.tags
        }

        # Add optional fields only if they have values
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
        if self.user_data:
            result["userData"] = self.user_data
        if self.fleet_type:
            result["fleetType"] = self.fleet_type

        return result

    def update_image_id(self, resolved_image_id: str) -> None:
        """
        Update the image ID with a resolved value.
        
        Args:
            resolved_image_id: The resolved AMI ID to use
            
        Raises:
            ValidationError: If the resolved AMI ID is invalid
        """
        if not resolved_image_id.startswith('ami-'):
            raise ValidationError(f"Invalid resolved AMI ID format: {resolved_image_id}")
        self.image_id = resolved_image_id

    def validate(self) -> None:
        """Validate template configuration."""
        errors: Dict[str, str] = {}

        # Required fields validation
        if not self.aws_handler:
            errors["awsHandler"] = "AWS handler is required"
        elif self.aws_handler not in [
            "EC2Fleet", "SpotFleet", "ASG", "RunInstances",
            "EC2FleetInstant", "EC2FleetMaintain", "EC2FleetRequest",
            "SpotFleetRequest", "SpotFleetMaintain"
        ]:
            errors["awsHandler"] = f"Invalid AWS handler: {self.aws_handler}"

        if self.max_number <= 0:
            errors["maxNumber"] = "Must be greater than zero"
        if not self.image_id:
            errors["imageId"] = "Image ID is required"

        # Subnet validation
        if not (self.subnet_id or self.subnet_ids):
            errors["subnet"] = "Either subnet_id or subnet_ids must be specified"
        if self.subnet_id and self.subnet_ids:
            errors["subnet"] = "Cannot specify both subnet_id and subnet_ids"

        # Security groups validation
        if not self.security_group_ids:
            errors["securityGroups"] = "At least one security group is required"

        # VM type validation
        if not (self.vm_type or self.vm_types):
            errors["vmType"] = "Either vm_type or vm_types must be specified"
        if self.vm_type and self.vm_types:
            errors["vmType"] = "Cannot specify both vm_type and vm_types"

        # Spot Fleet specific validation
        if "SpotFleet" in self.aws_handler:
            if not self.fleet_role:
                errors["fleetRole"] = "Fleet role ARN is required for Spot Fleet templates"
            elif not self.fleet_role.startswith('arn:aws:iam::'):
                errors["fleetRole"] = "Fleet role must be a valid ARN"
            elif ('AWSServiceRoleForEC2SpotFleet' in self.fleet_role and 
                  not self.fleet_role.endswith('/AWSServiceRoleForEC2SpotFleet')):
                errors["fleetRole"] = "Invalid Spot Fleet service-linked role ARN format"
            if self.max_spot_price is not None and self.max_spot_price <= 0:
                errors["maxSpotPrice"] = "Max spot price must be greater than zero"

        # VM types validation
        if self.vm_types:
            for vm_type, weight in self.vm_types.items():
                if weight <= 0:
                    errors["vmTypes"] = f"Weight for {vm_type} must be greater than zero"

        # Attributes validation
        if self.attributes:
            try:
                self._validate_attributes()
            except ValueError as e:
                errors["attributes"] = str(e)

        if errors:
            raise TemplateValidationError(str(self.template_id), errors)

    def _validate_attributes(self) -> None:
        """Validate template attributes."""
        required_attrs = {
            "type": "String",
            "ncores": "Numeric",
            "ncpus": "Numeric",
            "nram": "Numeric"
        }

        for attr, attr_type in required_attrs.items():
            if attr not in self.attributes:
                raise ValueError(f"Missing required attribute: {attr}")
            
            value = self.attributes[attr]
            if not isinstance(value, list) or len(value) != 2:
                raise ValueError(f"Invalid format for attribute {attr}")
            
            if value[0] != attr_type:
                raise ValueError(f"Invalid type for attribute {attr}")
            
            if attr_type == "Numeric":
                try:
                    num_value = int(value[1])
                    if num_value <= 0:
                        raise ValueError(f"Value for {attr} must be positive")
                except ValueError:
                    raise ValueError(f"Invalid numeric value for {attr}")