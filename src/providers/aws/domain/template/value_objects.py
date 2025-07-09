"""AWS-specific value objects and domain extensions."""
from typing import Any, Dict, ClassVar, List, Optional
import re
from enum import Enum
from pydantic import field_validator, model_validator, ConfigDict

# Import core domain primitives
from src.domain.base.value_objects import (
    ValueObject, 
    ResourceId, 
    InstanceType, 
    Tags, 
    ARN, 
    AllocationStrategy,
    PriceType
)

# Import domain protocols
from src.domain.template.value_objects import FleetTypePort, ProviderHandlerTypePort

class ResourceId(ResourceId):
    """Base class for AWS resource IDs with AWS-specific validation."""
    pattern_key: ClassVar[str] = ""
    
    @field_validator('value')
    @classmethod
    def validate_format(cls, v: str) -> str:
        # Get pattern from AWS configuration
        from src.providers.aws.configuration.config import get_aws_config_manager
        from src.providers.aws.configuration.validator import AWSNamingConfig
        
        config = get_aws_config_manager().get_typed(AWSNamingConfig)
        pattern = config.patterns.get(cls.pattern_key)
        
        # Fall back to class pattern if not in config
        if not pattern:
            raise ValueError(f"Pattern for {cls.resource_type} not found in AWS configuration")
            
        if not re.match(pattern, v):
            raise ValueError(f"Invalid AWS {cls.resource_type} ID format: {v}")
        return v

class AWSSubnetId(ResourceId):
    """AWS Subnet ID value object."""
    resource_type: ClassVar[str] = "Subnet"
    pattern_key: ClassVar[str] = "subnet"

class AWSSecurityGroupId(ResourceId):
    """AWS Security Group ID value object."""
    resource_type: ClassVar[str] = "Security Group"
    pattern_key: ClassVar[str] = "security_group"

class InstanceId(ResourceId):
    """AWS Instance ID value object."""
    resource_type: ClassVar[str] = "Instance"
    pattern_key: ClassVar[str] = "ec2_instance"
    
    def to_aws_format(self) -> str:
        """Convert to AWS API format."""
        return self.value

class AWSImageId(ResourceId):
    """AWS AMI ID value object."""
    resource_type: ClassVar[str] = "AMI"
    pattern_key: ClassVar[str] = "ami"
    
    def to_aws_format(self) -> str:
        """Convert to AWS API format."""
        return self.value

class AWSFleetId(ResourceId):
    """AWS Fleet ID value object."""
    resource_type: ClassVar[str] = "Fleet"
    pattern_key: ClassVar[str] = "ec2_fleet"

class AWSLaunchTemplateId(ResourceId):
    """AWS Launch Template ID value object."""
    resource_type: ClassVar[str] = "Launch Template"
    pattern_key: ClassVar[str] = "launch_template"

class AWSInstanceType(InstanceType):
    """AWS Instance Type value object with AWS-specific validation."""
    
    @field_validator('value')
    @classmethod
    def validate_instance_type(cls, v: str) -> str:
        # Get pattern from AWS configuration
        from src.providers.aws.configuration.config import get_aws_config_manager
        from src.providers.aws.configuration.validator import AWSNamingConfig
        
        config = get_aws_config_manager().get_typed(AWSNamingConfig)
        pattern = config.patterns["instance_type"]
        
        if not re.match(pattern, v):
            raise ValueError(f"Invalid AWS instance type format: {v}")
        return v
    
    @property
    def family(self) -> str:
        """Get the AWS instance family (e.g., t2, m5)."""
        return self.value.split('.')[0]
    
    @property
    def size(self) -> str:
        """Get the AWS instance size (e.g., micro, large)."""
        return self.value.split('.')[1]

class AWSTags(Tags):
    """AWS resource tags with AWS-specific validation."""
    
    @field_validator('tags')
    @classmethod
    def validate_aws_tags(cls, v: Dict[str, str]) -> Dict[str, str]:
        # Get AWS tag validation rules from configuration
        from src.providers.aws.configuration.config import get_aws_config_manager
        from src.providers.aws.configuration.validator import AWSNamingConfig
        
        config = get_aws_config_manager().get_typed(AWSNamingConfig)
        
        for key, value in v.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("AWS tags must be strings")
            
            # Use AWS limits from configuration
            if len(key) > config.limits.tag_key_length:
                raise ValueError(f"AWS tag key length exceeds limit of {config.limits.tag_key_length}")
            if len(value) > config.limits.tag_value_length:
                raise ValueError(f"AWS tag value length exceeds limit of {config.limits.tag_value_length}")
            
            # Use AWS pattern from configuration
            if not re.match(config.patterns["tag_key"], key):
                raise ValueError(f"Invalid AWS tag key format: {key}")
        return v
    
    def to_aws_format(self) -> List[Dict[str, str]]:
        """Convert to AWS API format."""
        return [{"Key": k, "Value": v} for k, v in self.values.items()]

class AWSARN(ARN):
    """AWS ARN value object with AWS-specific parsing."""
    partition: Optional[str] = None
    service: Optional[str] = None
    region: Optional[str] = None
    account_id: Optional[str] = None
    resource: Optional[str] = None
    
    @field_validator('value')
    @classmethod
    def validate_arn(cls, v: str) -> str:
        # Get pattern from AWS configuration
        from src.providers.aws.configuration.config import get_aws_config_manager
        from src.providers.aws.configuration.validator import AWSNamingConfig
        
        config = get_aws_config_manager().get_typed(AWSNamingConfig)
        pattern = config.patterns["arn"]
        
        if not re.match(pattern, v):
            raise ValueError(f"Invalid AWS ARN format: {v}")
        return v
    
    def model_post_init(self, __context: Any) -> None:
        """Parse AWS ARN components after initialization."""
        parts = self.value.split(':')
        if len(parts) >= 6:
            object.__setattr__(self, 'partition', parts[1])
            object.__setattr__(self, 'service', parts[2])
            object.__setattr__(self, 'region', parts[3])
            object.__setattr__(self, 'account_id', parts[4])
            object.__setattr__(self, 'resource', ':'.join(parts[5:]))

class ProviderHandlerType(str, Enum):
    """AWS-specific handler types implementing ProviderHandlerTypePort."""
    EC2_FLEET = "EC2Fleet"
    SPOT_FLEET = "SpotFleet"
    ASG = "ASG"
    RUN_INSTANCES = "RunInstances"
    
    def validate(self, value: str) -> bool:
        """Validate handler type against AWS configuration."""
        from src.providers.aws.configuration.validator import get_aws_config_manager, AWSProviderConfig
        
        config = get_aws_config_manager().get_typed(AWSProviderConfig)
        valid_types = list(config.handlers.types.values())
        
        return value in valid_types
    
    def get_supported_types(self) -> List[str]:
        """Get all supported AWS handler type values from configuration."""
        from src.providers.aws.configuration.validator import get_aws_config_manager, AWSProviderConfig
        
        config = get_aws_config_manager().get_typed(AWSProviderConfig)
        return list(config.handlers.types.values())
    
    @classmethod
    def validate_value(cls, value: str) -> None:
        """Class method for validation (backward compatibility)."""
        from src.providers.aws.configuration.config import get_aws_config_manager
        from src.providers.aws.configuration.validator import AWSProviderConfig
        
        config = get_aws_config_manager().get_typed(AWSProviderConfig)
        valid_types = list(config.handlers.types.values())
        
        if value not in valid_types:
            raise ValueError(f"Invalid AWS handler type: {value}. Valid types are: {', '.join(valid_types)}")

class AWSFleetType(str, Enum):
    """AWS Fleet type implementing FleetTypePort with configuration-driven behavior."""
    INSTANT = "instant"  # EC2 Fleet only
    REQUEST = "request"  # Both EC2 Fleet and Spot Fleet
    MAINTAIN = "maintain"  # Both EC2 Fleet and Spot Fleet
    
    def get_valid_types_for_handler(self, handler_type: ProviderHandlerType) -> List[str]:
        """Get valid fleet types for a specific AWS handler type from config."""
        from src.providers.aws.configuration.validator import get_aws_config_manager, AWSProviderConfig
        
        config = get_aws_config_manager().get_typed(AWSProviderConfig)
        handler_capabilities = config.handlers.capabilities.get(handler_type.value, {})
        supported_types = handler_capabilities.supported_fleet_types or []
        
        # If no supported types are defined in config, fall back to hardcoded values
        if not supported_types:
            if handler_type == ProviderHandlerType.EC2_FLEET:
                return [self.INSTANT.value, self.REQUEST.value, self.MAINTAIN.value]
            elif handler_type == ProviderHandlerType.SPOT_FLEET:
                return [self.REQUEST.value, self.MAINTAIN.value]
            else:
                return []
                
        return supported_types
    
    def get_default_for_handler(self, handler_type: ProviderHandlerType) -> str:
        """Get default fleet type for a handler type from AWS config."""
        from src.providers.aws.configuration.validator import get_aws_config_manager, AWSProviderConfig

        config = get_aws_config_manager().get_typed(AWSProviderConfig)
        handler_capabilities = config.handlers.capabilities.get(handler_type.value, {})
        
        if handler_capabilities and handler_capabilities.default_fleet_type:
            return handler_capabilities.default_fleet_type
        
        # Fallback defaults
        if handler_type == ProviderHandlerType.EC2_FLEET:
            return self.INSTANT.value
        elif handler_type == ProviderHandlerType.SPOT_FLEET:
            return self.REQUEST.value
        else:
            return self.REQUEST.value
    
    def validate_for_handler(self, handler_type: ProviderHandlerType) -> bool:
        """Validate if this fleet type is supported by the handler type."""
        valid_types = self.get_valid_types_for_handler(handler_type)
        return self.value in valid_types
        handler_capabilities = config.handlers.capabilities.get(handler_type.value, {})
        
        if handler_capabilities and handler_capabilities.default_fleet_type:
            return cls(handler_capabilities.default_fleet_type)
        
        # Fall back to AWS defaults
        if handler_type == ProviderHandlerType.EC2_FLEET:
            return cls(config.handlers.defaults.ec2_fleet_type)
        elif handler_type == ProviderHandlerType.SPOT_FLEET:
            return cls(config.handlers.defaults.spot_fleet_type)
        else:
            return cls.REQUEST

class AWSAllocationStrategy:
    """AWS-specific allocation strategy wrapper with AWS API formatting."""
    
    def __init__(self, strategy: AllocationStrategy):
        self._strategy = strategy
    
    @property
    def value(self) -> str:
        return self._strategy.value
    
    @classmethod
    def from_core(cls, strategy: AllocationStrategy) -> 'AWSAllocationStrategy':
        """Create from core allocation strategy."""
        return cls(strategy)
    
    def to_ec2_fleet_format(self) -> str:
        """Convert to EC2 Fleet API format."""
        mapping = {
            AllocationStrategy.CAPACITY_OPTIMIZED: "capacity-optimized",
            AllocationStrategy.DIVERSIFIED: "diversified",
            AllocationStrategy.LOWEST_PRICE: "lowest-price",
            AllocationStrategy.PRICE_CAPACITY_OPTIMIZED: "price-capacity-optimized"
        }
        return mapping.get(self._strategy, "lowest-price")
    
    def to_spot_fleet_format(self) -> str:
        """Convert to Spot Fleet API format."""
        mapping = {
            AllocationStrategy.CAPACITY_OPTIMIZED: "capacityOptimized",
            AllocationStrategy.DIVERSIFIED: "diversified",
            AllocationStrategy.LOWEST_PRICE: "lowestPrice",
            AllocationStrategy.PRICE_CAPACITY_OPTIMIZED: "priceCapacityOptimized"
        }
        return mapping.get(self._strategy, "lowestPrice")
    
    def to_asg_format(self) -> str:
        """Convert to Auto Scaling Group API format."""
        mapping = {
            AllocationStrategy.CAPACITY_OPTIMIZED: "capacity-optimized",
            AllocationStrategy.DIVERSIFIED: "diversified",
            AllocationStrategy.LOWEST_PRICE: "lowest-price",
            AllocationStrategy.PRICE_CAPACITY_OPTIMIZED: "price-capacity-optimized"
        }
        return mapping.get(self._strategy, "lowest-price")

class AWSConfiguration(ValueObject):
    """AWS-specific configuration value object."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    handler_type: ProviderHandlerType
    fleet_type: Optional[AWSFleetType] = None
    allocation_strategy: Optional[AllocationStrategy] = None  # Use core enum, not wrapper
    price_type: Optional[PriceType] = None
    subnet_ids: List[AWSSubnetId] = []
    security_group_ids: List[AWSSecurityGroupId] = []
    
    @model_validator(mode='after')
    def validate_aws_configuration(self) -> 'AWSConfiguration':
        """Validate AWS-specific configuration."""
        # Set default fleet type if not provided
        if not self.fleet_type:
            # Create a temporary instance to get the default
            temp_fleet = AWSFleetType.REQUEST  # Default instance
            default_fleet_type = temp_fleet.get_default_for_handler(self.handler_type)
            object.__setattr__(self, 'fleet_type', AWSFleetType(default_fleet_type))
        
        # Set default allocation strategy if not provided
        if not self.allocation_strategy:
            object.__setattr__(self, 'allocation_strategy', AllocationStrategy.LOWEST_PRICE)
        
        # Set default price type if not provided
        if not self.price_type:
            object.__setattr__(self, 'price_type', PriceType.ONDEMAND)
        
        # Validate fleet type is supported by handler
        valid_fleet_types = self.fleet_type.get_valid_types_for_handler(self.handler_type)
        if self.fleet_type.value not in valid_fleet_types:
            raise ValueError(
                f"Fleet type {self.fleet_type.value} not supported by handler {self.handler_type.value}. "
                f"Valid types: {', '.join(valid_fleet_types)}"
            )
        
        return self
    
    def to_aws_api_format(self) -> Dict[str, Any]:
        """Convert to AWS API format."""
        return {
            "handler_type": self.handler_type.value,
            "fleet_type": self.fleet_type.value if self.fleet_type else None,
            "allocation_strategy": self.allocation_strategy.value if self.allocation_strategy else None,
            "price_type": self.price_type.value if self.price_type else None,
            "subnet_ids": [subnet.value for subnet in self.subnet_ids],
            "security_group_ids": [sg.value for sg in self.security_group_ids]
        }
