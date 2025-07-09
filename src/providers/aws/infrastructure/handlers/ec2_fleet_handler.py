"""AWS EC2 Fleet Handler.

This module provides the EC2 Fleet handler implementation for managing
AWS EC2 Fleet requests through the AWS EC2 Fleet API.

The EC2 Fleet handler supports both On-Demand and Spot instance provisioning
with advanced fleet management capabilities including multiple instance types,
availability zones, and capacity optimization strategies.

Key Features:
    - Mixed instance type support
    - On-Demand and Spot instance combinations
    - Capacity optimization strategies
    - Multi-AZ deployment support
    - Advanced fleet configuration

Classes:
    EC2FleetHandler: Main handler for EC2 Fleet operations

Usage:
    This handler is used by the AWS provider to manage EC2 Fleet requests
    for complex deployment scenarios requiring advanced fleet management.

Note:
    EC2 Fleet provides more advanced capabilities than individual instance
    launches and is suitable for large-scale, complex deployments.
"""
from typing import Dict, Any, List
from datetime import datetime
from botocore.exceptions import ClientError

from src.domain.request.aggregate import Request
from src.domain.template.aggregate import Template
from src.providers.aws.domain.template.value_objects import ProviderHandlerType, AWSFleetType
from src.providers.aws.infrastructure.handlers.base_handler import AWSHandler
from src.providers.aws.exceptions.aws_exceptions import (
    AWSValidationError, AWSEntityNotFoundError, AWSInfrastructureError
)
from src.infrastructure.resilience import CircuitBreakerOpenError
from src.providers.aws.utilities.aws_operations import AWSOperations
from src.domain.base.ports import LoggingPort
from src.infrastructure.ports.request_adapter_port import RequestAdapterPort
from src.infrastructure.template.sync_configuration_store import SyncTemplateConfigurationStore
from src.domain.base.dependency_injection import injectable
from src.infrastructure.error.decorators import handle_infrastructure_exceptions

@injectable
class EC2FleetHandler(AWSHandler):
    """Handler for EC2 Fleet operations."""
    
    def __init__(self, aws_client, logger: LoggingPort, aws_ops: AWSOperations, 
                 template_config_store: SyncTemplateConfigurationStore, request_adapter: RequestAdapterPort = None):
        """
        Initialize the EC2 Fleet handler.
        
        Args:
            aws_client: AWS client instance
            logger: Logger for logging messages
            aws_ops: AWS operations utility
            template_config_store: Template configuration store for retrieving templates
            request_adapter: Optional request adapter for terminating instances
        """
        # Use enhanced base class initialization - eliminates duplication
        super().__init__(aws_client, logger, aws_ops, template_config_store, request_adapter)

    @handle_infrastructure_exceptions(context="ec2_fleet_creation")
    def acquire_hosts(self, request: Request, template: Template) -> str:
        """
        Create an EC2 Fleet to acquire hosts.
        Returns the Fleet ID.
        """
        return self.aws_ops.execute_with_standard_error_handling(
            operation=lambda: self._create_fleet_internal(request, template),
            operation_name="create EC2 fleet",
            context="EC2Fleet"
        )

    def _create_fleet_internal(self, request: Request, template: Template) -> str:
        """Internal method for EC2 Fleet creation with pure business logic."""
        # Validate prerequisites
        self._validate_prerequisites(template)
        
        # Validate fleet type
        if not template.fleet_type:
            raise AWSValidationError("Fleet type is required for EC2Fleet")
            
        # Validate fleet type using configuration-driven logic
        temp_fleet = AWSFleetType.REQUEST  # Temporary instance for validation
        valid_types = temp_fleet.get_valid_types_for_handler(ProviderHandlerType.EC2_FLEET)
        try:
            fleet_type = AWSFleetType(template.fleet_type.lower())
            if fleet_type.value not in valid_types:
                raise ValueError  # Will be caught by the except block below
        except ValueError:
            raise AWSValidationError(f"Invalid EC2 fleet type: {template.fleet_type}. "
                               f"Must be one of: {', '.join(valid_types)}")

        # Create launch template directly without additional retry wrapper
        launch_template = self.create_launch_template(template, request)
        
        # Store launch template info in request
        request.set_launch_template_info(
            launch_template['LaunchTemplateId'],
            launch_template['Version']
        )

        # Create fleet configuration
        fleet_config = self._create_fleet_config(
            template=template,
            request=request,
            launch_template_id=launch_template['LaunchTemplateId'],
            launch_template_version=launch_template['Version']
        )

        # Create the fleet with circuit breaker for critical operation
        try:
            response = self._retry_with_backoff(
                self.aws_client.ec2_client.create_fleet,
                operation_type="critical",
                **fleet_config
            )
        except CircuitBreakerOpenError as e:
            self._logger.error(f"Circuit breaker OPEN for EC2 Fleet creation: {str(e)}")
            # Re-raise to allow upper layers to handle graceful degradation
            raise e

        fleet_id = response['FleetId']
        self._logger.info(f"Successfully created EC2 Fleet: {fleet_id}")

        # For instant fleets, store instance IDs in request metadata
        if fleet_type == AWSFleetType.INSTANT:
            instance_ids = []
            # The correct field for instant fleets is 'fleetInstanceSet'
            for instance in response.get('fleetInstanceSet', []):
                if 'InstanceId' in instance:
                    instance_ids.append(instance['InstanceId'])
            
            # Log the response structure at debug level if no instances were found
            if not instance_ids:
                self._logger.debug(f"No instance IDs found in response. Response structure: {response}")
            
            request.metadata['instance_ids'] = instance_ids
            self._logger.debug(f"Stored instance IDs in request metadata: {instance_ids}")

        return fleet_id

    def _create_fleet_config(self,
                           template: Template,
                           request: Request,
                           launch_template_id: str,
                           launch_template_version: str) -> Dict[str, Any]:
        """Create EC2 Fleet configuration with enhanced options."""
        fleet_config = {
            'LaunchTemplateConfigs': [{
                'LaunchTemplateSpecification': {
                    'LaunchTemplateId': launch_template_id,
                    'Version': launch_template_version
                }
            }],
            'TargetCapacitySpecification': {
                'TotalTargetCapacity': request.machine_count
            },
            'Type': template.fleet_type,
            'TagSpecifications': [{
                'ResourceType': 'fleet',
                'Tags': [
                    {'Key': 'Name', 'Value': f"hf-fleet-{request.request_id}"},
                    {'Key': 'RequestId', 'Value': str(request.request_id)},
                    {'Key': 'TemplateId', 'Value': str(template.template_id)},
                    {'Key': 'CreatedBy', 'Value': 'HostFactory'},
                    {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()}
                ]
            }, {
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': f"hf-{request.request_id}"},
                    {'Key': 'RequestId', 'Value': str(request.request_id)},
                    {'Key': 'TemplateId', 'Value': str(template.template_id)},
                    {'Key': 'CreatedBy', 'Value': 'HostFactory'},
                    {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()}
                ]
            }]
        }

        # Add template tags if any
        if template.tags:
            instance_tags = [{'Key': k, 'Value': v} for k, v in template.tags.items()]
            fleet_config['TagSpecifications'][0]['Tags'].extend(instance_tags)
            fleet_config['TagSpecifications'][1]['Tags'].extend(instance_tags)

        # Add fleet type specific configurations
        if template.fleet_type == AWSFleetType.MAINTAIN.value:
            fleet_config['ReplaceUnhealthyInstances'] = True
            fleet_config['ExcessCapacityTerminationPolicy'] = 'termination'

        # Configure pricing type
        price_type = template.price_type or "ondemand"
        if price_type == "ondemand":
            fleet_config['TargetCapacitySpecification']['DefaultTargetCapacityType'] = 'on-demand'
        elif price_type == "spot":
            fleet_config['TargetCapacitySpecification']['DefaultTargetCapacityType'] = 'spot'
            
            # Add allocation strategy if specified
            if template.allocation_strategy:
                fleet_config['SpotOptions'] = {
                    'AllocationStrategy': self._get_allocation_strategy(template.allocation_strategy)
                }
                
            # Add max spot price if specified
            if template.max_spot_price is not None:
                if 'SpotOptions' not in fleet_config:
                    fleet_config['SpotOptions'] = {}
                fleet_config['SpotOptions']['MaxTotalPrice'] = str(template.max_spot_price)
        elif price_type == "heterogeneous":
            # For heterogeneous fleets, we need to specify both on-demand and spot capacities
            percent_on_demand = template.percent_on_demand or 0
            on_demand_count = int(request.machine_count * percent_on_demand / 100)
            spot_count = request.machine_count - on_demand_count
            
            fleet_config['TargetCapacitySpecification']['OnDemandTargetCapacity'] = on_demand_count
            fleet_config['TargetCapacitySpecification']['SpotTargetCapacity'] = spot_count
            fleet_config['TargetCapacitySpecification']['DefaultTargetCapacityType'] = 'on-demand'
            
            # Add allocation strategies if specified
            if template.allocation_strategy:
                fleet_config['SpotOptions'] = {
                    'AllocationStrategy': self._get_allocation_strategy(template.allocation_strategy)
                }
            
            if template.allocation_strategy_on_demand:
                fleet_config['OnDemandOptions'] = {
                    'AllocationStrategy': self._get_allocation_strategy_on_demand(template.allocation_strategy_on_demand)
                }
                
            # Add max spot price if specified
            if template.max_spot_price is not None:
                if 'SpotOptions' not in fleet_config:
                    fleet_config['SpotOptions'] = {}
                fleet_config['SpotOptions']['MaxTotalPrice'] = str(template.max_spot_price)

        # Add overrides with weighted capacity if multiple instance types are specified
        if template.vm_types:
            overrides = []
            for instance_type, weight in template.vm_types.items():
                override = {
                    'InstanceType': instance_type,
                    'WeightedCapacity': weight
                }
                overrides.append(override)
            fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = overrides
            
            # Add on-demand instance types for heterogeneous fleets
            if price_type == "heterogeneous" and template.vm_types_on_demand:
                on_demand_overrides = []
                for instance_type, weight in template.vm_types_on_demand.items():
                    override = {
                        'InstanceType': instance_type,
                        'WeightedCapacity': weight
                    }
                    on_demand_overrides.append(override)
                
                # Add on-demand overrides to the existing overrides
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'].extend(on_demand_overrides)

        # Add subnet configuration
        if template.subnet_ids:
            if 'Overrides' not in fleet_config['LaunchTemplateConfigs'][0]:
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = []
            
            # If we have both instance types and subnets, create all combinations
            if template.vm_types:
                overrides = []
                for subnet_id in template.subnet_ids:
                    for instance_type, weight in template.vm_types.items():
                        override = {
                            'SubnetId': subnet_id,
                            'InstanceType': instance_type,
                            'WeightedCapacity': weight
                        }
                        overrides.append(override)
                        
                    # Add on-demand instance types for heterogeneous fleets
                    if price_type == "heterogeneous" and template.vm_types_on_demand:
                        for instance_type, weight in template.vm_types_on_demand.items():
                            override = {
                                'SubnetId': subnet_id,
                                'InstanceType': instance_type,
                                'WeightedCapacity': weight
                            }
                            overrides.append(override)
                            
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = overrides
            else:
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = [
                    {'SubnetId': subnet_id} for subnet_id in template.subnet_ids
                ]

        return fleet_config
        
    def _get_allocation_strategy(self, strategy: str) -> str:
        """Convert Symphony allocation strategy to EC2 Fleet allocation strategy."""
        strategy_map = {
            "capacityOptimized": "capacity-optimized",
            "capacityOptimizedPrioritized": "capacity-optimized-prioritized",
            "diversified": "diversified",
            "lowestPrice": "lowest-price",
            "priceCapacityOptimized": "price-capacity-optimized"
        }
        
        return strategy_map.get(strategy, "lowest-price")
        
    def _get_allocation_strategy_on_demand(self, strategy: str) -> str:
        """Convert Symphony on-demand allocation strategy to EC2 Fleet allocation strategy."""
        strategy_map = {
            "lowestPrice": "lowest-price",
            "prioritized": "prioritized"
        }
        
        return strategy_map.get(strategy, "lowest-price")

    def check_hosts_status(self, request: Request) -> List[Dict[str, Any]]:
        """Check the status of instances in the fleet."""
        try:
            if not request.resource_id:
                raise AWSInfrastructureError("No Fleet ID found in request")

            # Get template to determine fleet type
            # Get template from configuration store
            template_dto = self._template_config_store.get_template_by_id(str(request.template_id))
            if not template_dto:
                raise AWSEntityNotFoundError(f"Template {request.template_id} not found")
            
            # Convert DTO to domain object
            from src.infrastructure.template.mappers import TemplateMapper
            template = TemplateMapper.from_dto(template_dto)
            
            # Ensure fleet_type is not None
            fleet_type_value = template.metadata.get('aws', {}).get('fleet_type', 'instant')
            if not fleet_type_value:
                raise AWSValidationError("Fleet type is required")
                
            fleet_type = FleetType(fleet_type_value.lower())

            # Get fleet information with pagination and retry
            fleet_list = self._retry_with_backoff(
                lambda: self._paginate(
                    self.aws_client.ec2_client.describe_fleets,
                    'Fleets',
                    FleetIds=[request.resource_id]
                ),
                operation_type="read_only"
            )

            if not fleet_list:
                raise AWSEntityNotFoundError(f"Fleet {request.resource_id} not found")

            fleet = fleet_list[0]
            
            # Log fleet status
            self._logger.debug(f"Fleet status: {fleet.get('Status')}, "
                        f"Target capacity: {fleet.get('TargetCapacitySpecification', {}).get('TotalTargetCapacity')}, "
                        f"Fulfilled capacity: {fleet.get('FulfilledCapacity', 0)}")

            # Get instance IDs based on fleet type
            instance_ids = []
            if fleet_type == FleetType.INSTANT:
                # For instant fleets, get instance IDs from metadata
                instance_ids = request.metadata.get('instance_ids', [])
            else:
                # For request/maintain fleets, describe fleet instances with pagination and retry
                active_instances = self._retry_with_backoff(
                    lambda: self._paginate(
                        self.aws_client.ec2_client.describe_fleet_instances,
                        'ActiveInstances',
                        FleetId=request.resource_id
                    ),
                    operation_type="read_only"
                )
                instance_ids = [
                    instance['InstanceId'] 
                    for instance in active_instances
                ]

            if not instance_ids:
                self._logger.info(f"No active instances found in fleet {request.resource_id}")
                return []

            # Get detailed instance information
            return self._get_instance_details(instance_ids)

        except ClientError as e:
            error = self._convert_client_error(e)
            self._logger.error(f"Failed to check EC2 Fleet status: {str(error)}")
            raise error
        except Exception as e:
            self._logger.error(f"Unexpected error checking EC2 Fleet status: {str(e)}")
            raise AWSInfrastructureError(f"Failed to check EC2 Fleet status: {str(e)}")

    def release_hosts(self, request: Request) -> None:
        """
        Release specific hosts or entire EC2 Fleet.
        
        Args:
            request: The request containing the fleet and machine information
        """
        try:
            if not request.resource_id:
                raise AWSInfrastructureError("No EC2 Fleet ID found in request")

            # Get fleet configuration with pagination and retry
            fleet_list = self._retry_with_backoff(
                lambda: self._paginate(
                    self.aws_client.ec2_client.describe_fleets,
                    'Fleets',
                    FleetIds=[request.resource_id]
                ),
                operation_type="read_only"
            )

            if not fleet_list:
                raise AWSEntityNotFoundError(f"EC2 Fleet {request.resource_id} not found")

            fleet = fleet_list[0]
            fleet_type = fleet.get('Type', 'maintain')

            # Get instance IDs from machine references
            instance_ids = []
            if request.machine_references:
                instance_ids = [m.machine_id for m in request.machine_references]

            if instance_ids:
                if fleet_type == 'maintain':
                    # For maintain fleets, reduce target capacity first
                    current_capacity = fleet['TargetCapacitySpecification']['TotalTargetCapacity']
                    new_capacity = max(0, current_capacity - len(instance_ids))
                    
                    self._retry_with_backoff(
                        self.aws_client.ec2_client.modify_fleet,
                        operation_type="critical",
                        FleetId=request.resource_id,
                        TargetCapacitySpecification={
                            'TotalTargetCapacity': new_capacity
                        }
                    )
                    self._logger.info(f"Reduced maintain fleet {request.resource_id} capacity to {new_capacity}")

                # Use consolidated AWS operations utility for instance termination
                self.aws_ops.terminate_instances_with_fallback(
                    instance_ids,
                    self._request_adapter,
                    "EC2 Fleet instances"
                )
            else:
                # Delete entire fleet
                self._retry_with_backoff(
                    self.aws_client.ec2_client.delete_fleets,
                    operation_type="critical",
                    FleetIds=[request.resource_id],
                    TerminateInstances=True
                )
                self._logger.info(f"Deleted EC2 Fleet: {request.resource_id}")

        except ClientError as e:
            error = self._convert_client_error(e)
            self._logger.error(f"Failed to release EC2 Fleet resources: {str(error)}")
            raise error
