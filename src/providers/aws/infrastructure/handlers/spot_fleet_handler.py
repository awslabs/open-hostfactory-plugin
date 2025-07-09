"""AWS Spot Fleet Handler.

This module provides the Spot Fleet handler implementation for managing
AWS Spot Fleet requests through the AWS EC2 Spot Fleet API.

The Spot Fleet handler enables cost-effective provisioning of EC2 instances
using Spot pricing with automatic diversification across instance types
and availability zones to maximize availability and minimize costs.

Key Features:
    - Spot instance cost optimization
    - Multiple instance type support
    - Automatic diversification strategies
    - Fault tolerance across AZs
    - Flexible capacity management

Classes:
    SpotFleetHandler: Main handler for Spot Fleet operations

Usage:
    This handler is used by the AWS provider to manage Spot Fleet requests
    for cost-sensitive workloads that can tolerate interruptions.

Note:
    Spot Fleet is ideal for batch processing, CI/CD, and other workloads
    that can benefit from significant cost savings through Spot pricing.
"""
from typing import Dict, Any, List
from datetime import datetime
import json
from botocore.exceptions import ClientError

from src.domain.request.aggregate import Request
from src.domain.template.aggregate import Template
from src.providers.aws.domain.template.value_objects import ProviderHandlerType, AWSFleetType
from src.providers.aws.infrastructure.handlers.base_handler import AWSHandler
from src.providers.aws.exceptions.aws_exceptions import (
    AWSValidationError, AWSEntityNotFoundError, AWSInfrastructureError,
    IAMError
)
from src.providers.aws.utilities.aws_operations import AWSOperations
from src.domain.base.ports import LoggingPort
from src.infrastructure.template.sync_configuration_store import SyncTemplateConfigurationStore
from src.infrastructure.ports.request_adapter_port import RequestAdapterPort
from src.domain.base.dependency_injection import injectable
from src.infrastructure.error.decorators import handle_infrastructure_exceptions

@injectable
class SpotFleetHandler(AWSHandler):
    """Handler for Spot Fleet operations."""
    
    def __init__(self, aws_client, logger: LoggingPort, aws_ops: AWSOperations, 
                 template_config_store: SyncTemplateConfigurationStore, request_adapter: RequestAdapterPort = None):
        """
        Initialize the Spot Fleet handler.
        
        Args:
            aws_client: AWS client instance
            logger: Logger for logging messages
            aws_ops: AWS operations utility
            template_config_store: Template configuration store for retrieving templates
            request_adapter: Optional request adapter for terminating instances
        """
        # Use enhanced base class initialization - eliminates duplication
        super().__init__(aws_client, logger, aws_ops, template_config_store, request_adapter)

    @handle_infrastructure_exceptions(context="spot_fleet_creation")
    def acquire_hosts(self, request: Request, template: Template) -> str:
        """
        Create a Spot Fleet to acquire hosts.
        Returns the Spot Fleet Request ID.
        """
        return self.aws_ops.execute_with_standard_error_handling(
            operation=lambda: self._create_spot_fleet_internal(request, template),
            operation_name="create Spot Fleet",
            context="SpotFleet"
        )

    def _create_spot_fleet_internal(self, request: Request, template: Template) -> str:
        """Internal method for Spot Fleet creation with pure business logic."""
        # Validate Spot Fleet specific prerequisites
        self._validate_spot_prerequisites(template)
        
        # Validate fleet type
        if not template.fleet_type:
            raise AWSValidationError("Fleet type is required for SpotFleet")
            
        # Validate fleet type using configuration-driven logic  
        temp_fleet = AWSFleetType.REQUEST  # Temporary instance for validation
        valid_types = temp_fleet.get_valid_types_for_handler(ProviderHandlerType.SPOT_FLEET)
        try:
            fleet_type = AWSFleetType(template.fleet_type.lower())
            if fleet_type.value not in valid_types:
                raise ValueError  # Will be caught by the except block below
        except ValueError:
            raise AWSValidationError(f"Invalid Spot fleet type: {template.fleet_type}. "
                               f"Must be one of: {', '.join(valid_types)}")

        # Create launch template directly without additional retry wrapper
        launch_template = self.create_launch_template(template, request)
        
        # Store launch template info in request
        request.set_launch_template_info(
            launch_template['LaunchTemplateId'],
            launch_template['Version']
        )

        # Create spot fleet configuration
        fleet_config = self._create_spot_fleet_config(
            template=template,
            request=request,
            launch_template_id=launch_template['LaunchTemplateId'],
            launch_template_version=launch_template['Version']
        )

        # Request spot fleet with circuit breaker for critical operation
        response = self._retry_with_backoff(
            self.aws_client.ec2_client.request_spot_fleet,
            operation_type="critical",
            SpotFleetRequestConfig=fleet_config
        )

        fleet_id = response['SpotFleetRequestId']
        self._logger.info(f"Successfully created Spot Fleet request: {fleet_id}")

        return fleet_id

    def _validate_spot_prerequisites(self, template: Template) -> None:
        """Validate Spot Fleet specific prerequisites."""
        errors = []

        # Log the validation start
        self._logger.debug(f"Starting Spot Fleet prerequisites validation for template: {template.template_id}")

        # First validate common prerequisites
        try:
            self._validate_prerequisites(template)
        except AWSValidationError as e:
            errors.extend(str(e).split('\n'))

        # Validate Spot Fleet specific requirements
        if not template.fleet_role:
            errors.append("Fleet role ARN is required for Spot Fleet")
        else:
            # For service-linked roles, we only validate the format
            if 'AWSServiceRoleForEC2SpotFleet' in template.fleet_role:
                if template.fleet_role != 'AWSServiceRoleForEC2SpotFleet':
                    errors.append(f"Invalid Spot Fleet service-linked role format: {template.fleet_role}")
            else:
                # For custom roles, validate with IAM
                try:
                    role_name = template.fleet_role.split('/')[-1]
                    # Create IAM client directly from session
                    iam_client = self.aws_client.session.client('iam', config=self.aws_client.boto_config)
                    self._retry_with_backoff(
                        iam_client.get_role,
                        RoleName=role_name
                    )
                except Exception as e:
                    errors.append(f"Invalid custom fleet role: {str(e)}")

        # Validate price type if specified
        if template.price_type:
            valid_options = ["spot", "ondemand", "heterogeneous"]
            if template.price_type not in valid_options:
                errors.append(f"Invalid price type: {template.price_type}. "
                             f"Must be one of: {', '.join(valid_options)}")
        
        # For heterogeneous price type, validate percent_on_demand
        if template.price_type == "heterogeneous" and template.percent_on_demand is None:
            errors.append("percent_on_demand is required for heterogeneous price type")
            
        # For heterogeneous price type with vm_types_on_demand, validate the configuration
        if template.price_type == "heterogeneous" and template.vm_types_on_demand:
            # Validate that vm_types is also specified
            if not template.vm_types:
                errors.append("vm_types must be specified when using vm_types_on_demand")
                
            # Validate that vm_types_on_demand has valid instance types
            for instance_type, weight in template.vm_types_on_demand.items():
                if not isinstance(weight, int) or weight <= 0:
                    errors.append(f"Weight for on-demand instance type {instance_type} must be a positive integer")

        # Validate spot price if specified
        if template.max_spot_price is not None:
            try:
                price = float(template.max_spot_price)
                if price <= 0:
                    errors.append("Spot price must be greater than zero")
            except ValueError:
                errors.append("Invalid spot price format")

        if errors:
            self._logger.error(f"Validation errors found: {errors}")
            raise AWSValidationError("\n".join(errors))
        else:
            self._logger.debug("All Spot Fleet prerequisites validation passed")

    def _is_valid_spot_fleet_service_role(self, role_arn: str) -> bool:
        """
        Validate if the provided ARN matches the Spot Fleet service-linked role pattern.
        
        Args:
            role_arn: The role ARN to validate
            
        Returns:
            bool: True if the ARN matches the expected pattern
        """
        import re

        pattern = (
            r'^arn:aws:iam::\d{12}:role/aws-service-role/'
            r'spotfleet\.amazonaws\.com/AWSServiceRoleForEC2SpotFleet$'
        )
        
        if re.match(pattern, role_arn):
            self._logger.debug(f"Valid Spot Fleet service-linked role: {role_arn}")
            return True
        return False

    def _check_iam_permissions(self, role_arn: str) -> None:
        """
        Check if current credentials have necessary IAM permissions.
        
        Args:
            role_arn: The role ARN to validate permissions for
            
        Raises:
            IAMError: If permissions are insufficient
        """
        try:
            # Get current identity
            identity = self.aws_client.sts_client.get_caller_identity()
            
            # Check permissions - create IAM client directly from session
            iam_client = self.aws_client.session.client('iam', config=self.aws_client.boto_config)
            response = iam_client.simulate_principal_policy(
                PolicySourceArn=identity['Arn'],
                ActionNames=[
                    'ec2:RequestSpotFleet',
                    'ec2:ModifySpotFleetRequest',
                    'ec2:CancelSpotFleetRequests',
                    'ec2:DescribeSpotFleetRequests',
                    'ec2:DescribeSpotFleetInstances',
                    'iam:PassRole'
                ],
                ResourceArns=[role_arn]
            )
            
            # Check evaluation results
            for result in response['EvaluationResults']:
                if result['EvalDecision'] != 'allowed':
                    raise IAMError(f"Missing permission: {result['EvalActionName']}")
                    
        except Exception as e:
            raise IAMError(f"Failed to validate IAM permissions: {str(e)}")

    def _create_spot_fleet_config(self,
                                template: Template,
                                request: Request,
                                launch_template_id: str,
                                launch_template_version: str) -> Dict[str, Any]:
        """Create Spot Fleet configuration with enhanced options."""
        # Strip the full ARN for service-linked role
        fleet_role = template.fleet_role
        if fleet_role == 'AWSServiceRoleForEC2SpotFleet':
            account_id = self.aws_client.sts_client.get_caller_identity()['Account']
            fleet_role = (
                f"arn:aws:iam::{account_id}:role/aws-service-role/"
                f"spotfleet.amazonaws.com/AWSServiceRoleForEC2SpotFleet"
            )

        # Common tags for both fleet and instances
        common_tags = [
            {'Key': 'Name', 'Value': f"hf-{request.request_id}"},
            {'Key': 'RequestId', 'Value': str(request.request_id)},
            {'Key': 'TemplateId', 'Value': str(template.template_id)},
            {'Key': 'CreatedBy', 'Value': 'HostFactory'},
            {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()}
        ]

        fleet_config = {
            'LaunchTemplateConfigs': [{
                'LaunchTemplateSpecification': {
                    'LaunchTemplateId': launch_template_id,
                    'Version': launch_template_version
                }
            }],
            'TargetCapacity': request.machine_count,
            'IamFleetRole': fleet_role,
            'AllocationStrategy': self._get_allocation_strategy(template.allocation_strategy),
            'Type': template.fleet_type,
            'TagSpecifications': [{
                'ResourceType': 'spot-fleet-request',
                'Tags': common_tags
            }]
        }
        
        # Configure based on price type
        price_type = template.price_type or "spot"  # Default to spot for SpotFleet
        
        if price_type == "ondemand":
            # For ondemand, set all capacity as on-demand
            fleet_config['OnDemandTargetCapacity'] = request.machine_count
            fleet_config['SpotTargetCapacity'] = 0
            fleet_config['DefaultTargetCapacity'] = "onDemand"
            
        elif price_type == "heterogeneous":
            # For heterogeneous, split capacity based on percent_on_demand
            percent_on_demand = template.percent_on_demand or 0
            on_demand_count = int(request.machine_count * percent_on_demand / 100)
            spot_count = request.machine_count - on_demand_count
            
            fleet_config['OnDemandTargetCapacity'] = on_demand_count
            fleet_config['SpotTargetCapacity'] = spot_count
            fleet_config['DefaultTargetCapacity'] = "spot"
            
        else:  # "spot" (default)
            # For spot, set all capacity as spot
            fleet_config['OnDemandTargetCapacity'] = 0
            fleet_config['SpotTargetCapacity'] = request.machine_count
            fleet_config['DefaultTargetCapacity'] = "spot"

        # Add template tags if any
        if template.tags:
            instance_tags = [{'Key': k, 'Value': v} for k, v in template.tags.items()]
            fleet_config['TagSpecifications'][0]['Tags'].extend(instance_tags)

        # Add fleet type specific configurations
        if template.fleet_type == AWSFleetType.MAINTAIN.value:
            fleet_config['ReplaceUnhealthyInstances'] = True
            fleet_config['TerminateInstancesWithExpiration'] = True

        # Add spot price if specified
        if template.max_spot_price:
            fleet_config['SpotPrice'] = str(template.max_spot_price)

        # Add instance type overrides if specified
        if template.vm_types:
            # For heterogeneous price type with on-demand instances
            if template.price_type == "heterogeneous" and template.vm_types_on_demand:
                # Create spot instance overrides
                spot_overrides = [
                    {
                        'InstanceType': instance_type,
                        'WeightedCapacity': weight,
                        'Priority': idx + 1,
                        'SpotPrice': str(template.max_spot_price) if template.max_spot_price else None
                    }
                    for idx, (instance_type, weight) in enumerate(template.vm_types.items())
                ]
                
                # Create on-demand instance overrides
                ondemand_overrides = [
                    {
                        'InstanceType': instance_type,
                        'WeightedCapacity': weight,
                        'Priority': idx + len(template.vm_types) + 1,
                        # Force this to be on-demand by not specifying SpotPrice
                    }
                    for idx, (instance_type, weight) in enumerate(template.vm_types_on_demand.items())
                ]
                
                # Combine both types of overrides
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = spot_overrides + ondemand_overrides
                
                # Log the combined overrides
                self._logger.debug(f"Created combined overrides for heterogeneous fleet: "
                            f"{len(spot_overrides)} spot instance types, "
                            f"{len(ondemand_overrides)} on-demand instance types")
            else:
                # Standard spot instance overrides
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = [
                    {
                        'InstanceType': instance_type,
                        'WeightedCapacity': weight,
                        'Priority': idx + 1,
                        'SpotPrice': str(template.max_spot_price) if template.max_spot_price else None
                    }
                    for idx, (instance_type, weight) in enumerate(template.vm_types.items())
                ]

        # Add subnet configuration
        if template.subnet_ids:
            if 'Overrides' not in fleet_config['LaunchTemplateConfigs'][0]:
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = []
            
            # For heterogeneous price type with on-demand instances
            if template.price_type == "heterogeneous" and template.vm_types_on_demand and template.vm_types:
                # Create spot instance overrides with subnets
                spot_overrides = []
                for subnet_id in template.subnet_ids:
                    for idx, (instance_type, weight) in enumerate(template.vm_types.items()):
                        override = {
                            'SubnetId': subnet_id,
                            'InstanceType': instance_type,
                            'WeightedCapacity': weight,
                            'Priority': idx + 1,
                            'SpotPrice': str(template.max_spot_price) if template.max_spot_price else None
                        }
                        spot_overrides.append(override)
                
                # Create on-demand instance overrides with subnets
                ondemand_overrides = []
                for subnet_id in template.subnet_ids:
                    for idx, (instance_type, weight) in enumerate(template.vm_types_on_demand.items()):
                        override = {
                            'SubnetId': subnet_id,
                            'InstanceType': instance_type,
                            'WeightedCapacity': weight,
                            'Priority': idx + len(template.vm_types) + 1
                            # No SpotPrice for on-demand instances
                        }
                        ondemand_overrides.append(override)
                
                # Combine both types of overrides
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = spot_overrides + ondemand_overrides
                
                # Log the combined overrides
                self._logger.debug(f"Created combined overrides with subnets for heterogeneous fleet: "
                            f"{len(spot_overrides)} spot instance overrides, "
                            f"{len(ondemand_overrides)} on-demand instance overrides")
            # If we have both instance types and subnets, create all combinations
            elif template.vm_types:
                overrides = []
                for subnet_id in template.subnet_ids:
                    for idx, (instance_type, weight) in enumerate(template.vm_types.items()):
                        override = {
                            'SubnetId': subnet_id,
                            'InstanceType': instance_type,
                            'WeightedCapacity': weight,
                            'Priority': idx + 1
                        }
                        if template.max_spot_price:
                            override['SpotPrice'] = str(template.max_spot_price)
                        overrides.append(override)
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = overrides
            else:
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = [
                    {'SubnetId': subnet_id} for subnet_id in template.subnet_ids
                ]

        # Log the final configuration
        self._logger.debug(f"Spot Fleet configuration: {json.dumps(fleet_config, indent=2)}")

        return fleet_config

    def _get_allocation_strategy(self, strategy: str) -> str:
        """Convert Symphony allocation strategy to Spot Fleet allocation strategy."""
        if not strategy:
            return "lowestPrice"
            
        strategy_map = {
            "capacityOptimized": "capacityOptimized",
            "capacityOptimizedPrioritized": "capacityOptimizedPrioritized",
            "diversified": "diversified",
            "lowestPrice": "lowestPrice",
            "priceCapacityOptimized": "priceCapacityOptimized"
        }
        
        return strategy_map.get(strategy, "lowestPrice")
        
    def _monitor_spot_prices(self, template: Template) -> Dict[str, float]:
        """Monitor current spot prices in specified regions/AZs."""
        try:
            prices = {}
            price_history = self._retry_with_backoff(
                lambda: self._paginate(
                    self.aws_client.ec2_client.describe_spot_price_history,
                    'SpotPriceHistory',
                    InstanceTypes=list(template.vm_types.keys()) if template.vm_types else [template.vm_type],
                    ProductDescriptions=['Linux/UNIX']
                )
            )
            
            for price in price_history:
                key = f"{price['InstanceType']}-{price['AvailabilityZone']}"
                prices[key] = float(price['SpotPrice'])
            
            return prices

        except Exception as e:
            self._logger.warning(f"Failed to monitor spot prices: {str(e)}")
            return {}

    def check_hosts_status(self, request: Request) -> List[Dict[str, Any]]:
        """Check the status of instances in the spot fleet."""
        try:
            if not request.resource_id:
                raise AWSInfrastructureError("No Spot Fleet Request ID found in request")

            # Get fleet information with pagination and retry
            fleet_list = self._retry_with_backoff(
                lambda: self._paginate(
                    self.aws_client.ec2_client.describe_spot_fleet_requests,
                    'SpotFleetRequestConfigs',
                    SpotFleetRequestIds=[request.resource_id]
                )
            )

            if not fleet_list:
                raise AWSEntityNotFoundError(f"Spot Fleet Request {request.resource_id} not found")

            fleet = fleet_list[0]
            
            # Log fleet status
            self._logger.debug(f"Fleet status: {fleet.get('SpotFleetRequestState')}, "
                        f"Target capacity: {fleet.get('SpotFleetRequestConfig', {}).get('TargetCapacity')}, "
                        f"Fulfilled capacity: {fleet.get('ActivityStatus')}")

            # Get instance information with pagination and retry
            active_instances = self._retry_with_backoff(
                lambda: self._paginate(
                    self.aws_client.ec2_client.describe_spot_fleet_instances,
                    'ActiveInstances',
                    SpotFleetRequestId=request.resource_id
                )
            )

            instance_ids = [
                instance['InstanceId'] 
                for instance in active_instances
            ]

            if not instance_ids:
                self._logger.info(f"No active instances found in Spot Fleet {request.resource_id}")
                return []

            # Get detailed instance information
            return self._get_instance_details(instance_ids)

        except ClientError as e:
            error = self._convert_client_error(e)
            self._logger.error(f"Failed to check Spot Fleet status: {str(error)}")
            raise error
        except Exception as e:
            self._logger.error(f"Unexpected error checking Spot Fleet status: {str(e)}")
            raise AWSInfrastructureError(f"Failed to check Spot Fleet status: {str(e)}")

    def release_hosts(self, request: Request) -> None:
        """
        Release specific hosts or entire Spot Fleet.
        
        Args:
            request: The request containing the fleet and machine information
        """
        try:
            if not request.resource_id:
                raise AWSInfrastructureError("No Spot Fleet Request ID found in request")

            # Get fleet configuration with pagination and retry
            fleet_list = self._retry_with_backoff(
                lambda: self._paginate(
                    self.aws_client.ec2_client.describe_spot_fleet_requests,
                    'SpotFleetRequestConfigs',
                    SpotFleetRequestIds=[request.resource_id]
                )
            )

            if not fleet_list:
                raise AWSEntityNotFoundError(f"Spot Fleet {request.resource_id} not found")

            fleet = fleet_list[0]
            fleet_type = fleet['SpotFleetRequestConfig'].get('Type', 'maintain')

            # Get instance IDs from machine references
            instance_ids = []
            if request.machine_references:
                instance_ids = [m.machine_id for m in request.machine_references]

            if instance_ids:
                if fleet_type == 'maintain':
                    # For maintain fleets, reduce capacity first
                    current_capacity = fleet['SpotFleetRequestConfig']['TargetCapacity']
                    new_capacity = max(0, current_capacity - len(instance_ids))
                    
                    self._retry_with_backoff(
                        self.aws_client.ec2_client.modify_spot_fleet_request,
                        operation_type="critical",
                        SpotFleetRequestId=request.resource_id,
                        TargetCapacity=new_capacity
                    )
                    self._logger.info(f"Reduced maintain fleet {request.resource_id} capacity to {new_capacity}")

                # Use consolidated AWS operations utility for instance termination
                self.aws_ops.terminate_instances_with_fallback(
                    instance_ids,
                    self._request_adapter,
                    "Spot Fleet instances"
                )
                self._logger.info(f"Terminated instances: {instance_ids}")
            else:
                # Release entire fleet
                self._retry_with_backoff(
                    self.aws_client.ec2_client.cancel_spot_fleet_requests,
                    operation_type="critical",
                    SpotFleetRequestIds=[request.resource_id],
                    TerminateInstances=True
                )
                self._logger.info(f"Cancelled entire Spot Fleet request: {request.resource_id}")

        except ClientError as e:
            error = self._convert_client_error(e)
            self._logger.error(f"Failed to release Spot Fleet resources: {str(error)}")
            raise error
