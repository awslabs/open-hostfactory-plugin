"""AWS-specific template domain extensions."""
from typing import Dict, Any, Optional
from pydantic import model_validator

from src.domain.base.template import Template as CoreTemplate
from src.providers.aws.domain.template.value_objects import (
    ProviderHandlerType,
    AWSFleetType,
    AWSAllocationStrategy,
    AWSConfiguration,
    AWSInstanceType,
    AWSSubnetId,
    AWSSecurityGroupId,
    AWSTags
)

class AWSTemplate(CoreTemplate):
    """AWS-specific template with AWS extensions."""
    
    # AWS-specific fields
    provider_api: ProviderHandlerType
    fleet_type: Optional[AWSFleetType] = None
    fleet_role: Optional[str] = None
    key_name: Optional[str] = None
    user_data: Optional[str] = None
    
    # AWS instance configuration
    root_device_volume_size: Optional[int] = None
    volume_type: Optional[str] = "gp3"  # gp2, gp3, io1, io2, standard
    iops: Optional[int] = None
    instance_profile: Optional[str] = None
    
    # AWS spot configuration
    spot_fleet_request_expiry: Optional[int] = None
    allocation_strategy_on_demand: Optional[AWSAllocationStrategy] = None
    percent_on_demand: Optional[int] = None
    pools_count: Optional[int] = None
    
    # AWS launch template
    launch_template_id: Optional[str] = None
    
    # AWS-specific instance types and priorities
    vm_types: Optional[Dict[str, int]] = None
    vm_types_on_demand: Optional[Dict[str, int]] = None
    vm_types_priority: Optional[Dict[str, int]] = None
    
    def __init__(self, **data):
        # Set provider_type to AWS
        data['provider_type'] = 'aws'
        super().__init__(**data)
    
    @model_validator(mode='after')
    def validate_aws_template(self) -> 'AWSTemplate':
        """AWS-specific template validation."""
        # Validate AWS handler type
        if self.provider_api:
            ProviderHandlerType.validate(self.provider_api.value)
        
        # Validate fleet type for handler
        if self.fleet_type and self.provider_api:
            valid_fleet_types = AWSFleetType.get_valid_types_for_handler(self.provider_api)
            if self.fleet_type.value not in valid_fleet_types:
                raise ValueError(
                    f"Fleet type {self.fleet_type.value} not supported by handler {self.provider_api.value}"
                )
        
        # Validate spot configuration
        if self.percent_on_demand is not None:
            if not (0 <= self.percent_on_demand <= 100):
                raise ValueError("percent_on_demand must be between 0 and 100")
        
        return self
    
    def get_ec2_fleet_allocation_strategy(self) -> str:
        """Get allocation strategy in EC2 Fleet API format."""
        if isinstance(self.allocation_strategy, AWSAllocationStrategy):
            return self.allocation_strategy.to_ec2_fleet_format()
        return AWSAllocationStrategy.LOWEST_PRICE.to_ec2_fleet_format()
    
    def get_spot_fleet_allocation_strategy(self) -> str:
        """Get allocation strategy in Spot Fleet API format."""
        if isinstance(self.allocation_strategy, AWSAllocationStrategy):
            return self.allocation_strategy.to_spot_fleet_format()
        return AWSAllocationStrategy.LOWEST_PRICE.to_spot_fleet_format()
    
    def get_asg_allocation_strategy(self) -> str:
        """Get allocation strategy in Auto Scaling Group API format."""
        if isinstance(self.allocation_strategy, AWSAllocationStrategy):
            return self.allocation_strategy.to_asg_format()
        return AWSAllocationStrategy.LOWEST_PRICE.to_asg_format()
    
    def get_ec2_fleet_on_demand_allocation_strategy(self) -> str:
        """Get on-demand allocation strategy in EC2 Fleet API format."""
        if self.allocation_strategy_on_demand:
            return self.allocation_strategy_on_demand.to_ec2_fleet_format()
        return self.get_ec2_fleet_allocation_strategy()
    
    def to_aws_api_format(self) -> Dict[str, Any]:
        """Convert template to AWS API format."""
        base_format = self.to_provider_format('aws')
        
        # Add AWS-specific fields
        aws_format = {
            **base_format,
            'provider_api': self.provider_api.value,
            'fleet_type': self.fleet_type.value if self.fleet_type else None,
            'fleet_role': self.fleet_role,
            'key_name': self.key_name,
            'user_data': self.user_data,
            'root_device_volume_size': self.root_device_volume_size,
            'volume_type': self.volume_type,
            'iops': self.iops,
            'instance_profile': self.instance_profile,
            'spot_fleet_request_expiry': self.spot_fleet_request_expiry,
            'percent_on_demand': self.percent_on_demand,
            'pools_count': self.pools_count,
            'launch_template_id': self.launch_template_id,
            'vm_types': self.vm_types,
            'vm_types_on_demand': self.vm_types_on_demand,
            'vm_types_priority': self.vm_types_priority
        }
        
        # Add AWS-specific allocation strategies
        if self.allocation_strategy_on_demand:
            aws_format['allocation_strategy_on_demand'] = self.allocation_strategy_on_demand.value
        
        return aws_format
    
    @classmethod
    def from_aws_format(cls, data: Dict[str, Any]) -> 'AWSTemplate':
        """Create AWS template from AWS-specific format."""
        # Convert AWS format to core format first
        core_data = {
            'template_id': data.get('template_id'),
            'name': data.get('name', data.get('template_id')),
            'instance_type': AWSInstanceType(value=data.get('vm_type', data.get('instance_type'))),
            'image_id': data.get('image_id'),
            'max_instances': data.get('max_number', data.get('max_instances', 1)),
            'subnet_ids': data.get('subnet_ids', [data.get('subnet_id')] if data.get('subnet_id') else []),
            'security_group_ids': data.get('security_group_ids', []),
            'tags': AWSTags.from_dict(data.get('tags', data.get('instance_tags', {}))),
        }
        
        # Add AWS-specific fields
        aws_data = {
            **core_data,
            'provider_api': ProviderHandlerType(data.get('provider_api')),
            'fleet_type': AWSFleetType(data.get('fleet_type')) if data.get('fleet_type') else None,
            'fleet_role': data.get('fleet_role'),
            'key_name': data.get('key_name'),
            'user_data': data.get('user_data'),
            'root_device_volume_size': data.get('root_device_volume_size'),
            'volume_type': data.get('volume_type'),
            'iops': data.get('iops'),
            'instance_profile': data.get('instance_profile'),
            'spot_fleet_request_expiry': data.get('spot_fleet_request_expiry'),
            'percent_on_demand': data.get('percent_on_demand'),
            'pools_count': data.get('pools_count'),
            'launch_template_id': data.get('launch_template_id'),
            'vm_types': data.get('vm_types'),
            'vm_types_on_demand': data.get('vm_types_on_demand'),
            'vm_types_priority': data.get('vm_types_priority')
        }
        
        # Handle optional AWS-specific fields
        if 'allocation_strategy' in data:
            aws_data['allocation_strategy'] = AWSAllocationStrategy.from_string(data['allocation_strategy'])
        
        if 'allocation_strategy_on_demand' in data:
            aws_data['allocation_strategy_on_demand'] = AWSAllocationStrategy.from_string(data['allocation_strategy_on_demand'])
        
        if 'price_type' in data:
            from src.domain.base.value_objects import PriceType

            aws_data['price_type'] = PriceType.from_string(data['price_type'])
        
        if 'max_spot_price' in data:
            aws_data['max_price'] = data['max_spot_price']
        
        return cls.model_validate(aws_data)
    
    def get_aws_configuration(self) -> AWSConfiguration:
        """Get AWS configuration object."""
        return AWSConfiguration(
            handler_type=self.provider_api,
            fleet_type=self.fleet_type,
            allocation_strategy=self.allocation_strategy if isinstance(self.allocation_strategy, AWSAllocationStrategy) else None,
            price_type=self.price_type,
            subnet_ids=[AWSSubnetId(value=sid) for sid in self.subnet_ids],
            security_group_ids=[AWSSecurityGroupId(value=sgid) for sgid in self.security_group_ids]
        )
