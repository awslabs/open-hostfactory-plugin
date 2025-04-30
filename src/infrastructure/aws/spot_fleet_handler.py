# src/infrastructure/aws/spot_fleet_handler.py
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json
from botocore.exceptions import ClientError

from src.domain.request.request_aggregate import Request
from src.domain.template.template_aggregate import Template
from src.domain.template.value_objects import SpotFleetType
from src.infrastructure.exceptions import InfrastructureError
from src.infrastructure.aws.base_handler import AWSHandler
from src.infrastructure.aws.exceptions import *

logger = logging.getLogger(__name__)

class SpotFleetHandler(AWSHandler):
    """Handler for Spot Fleet operations."""

    def acquire_hosts(self, request: Request, template: Template) -> str:
        """
        Create a Spot Fleet to acquire hosts.
        Returns the Spot Fleet Request ID.
        """
        try:
            # Validate Spot Fleet specific prerequisites
            self._validate_spot_prerequisites(template)
            
            # Validate fleet type
            if not template.fleet_type:
                raise ValidationError("Fleet type is required for SpotFleet")
            try:
                fleet_type = SpotFleetType(template.fleet_type.lower())
            except ValueError:
                raise ValidationError(f"Invalid Spot fleet type: {template.fleet_type}. "
                                   f"Must be one of: {', '.join(SpotFleetType.__members__.keys())}")

            # Create launch template with retry mechanism
            launch_template = self._retry_with_backoff(
                self.create_launch_template,
                template,
                request
            )
            
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

            # Request spot fleet with retry mechanism
            response = self._retry_with_backoff(
                self.aws_client.ec2_client.request_spot_fleet,
                SpotFleetRequestConfig=fleet_config
            )

            fleet_id = response['SpotFleetRequestId']
            logger.info(f"Successfully created Spot Fleet request: {fleet_id}")

            return fleet_id

        except ClientError as e:
            error = self._convert_client_error(e)
            logger.error(f"Failed to create Spot Fleet: {str(error)}")
            raise error
        except Exception as e:
            logger.error(f"Unexpected error creating Spot Fleet: {str(e)}")
            raise InfrastructureError(f"Failed to create Spot Fleet: {str(e)}")

    def _validate_spot_prerequisites(self, template: Template) -> None:
        """Validate Spot Fleet specific prerequisites."""
        errors = []

        # Log the validation start
        logger.debug(f"Starting Spot Fleet prerequisites validation for template: {template.template_id}")

        # First validate common prerequisites
        try:
            self._validate_prerequisites(template)
        except ValidationError as e:
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
                    self._retry_with_backoff(
                        self.aws_client.iam_client.get_role,
                        RoleName=role_name
                    )
                except Exception as e:
                    errors.append(f"Invalid custom fleet role: {str(e)}")

        # Validate spot price if specified
        if template.max_spot_price is not None:
            try:
                price = float(template.max_spot_price)
                if price <= 0:
                    errors.append("Spot price must be greater than zero")
            except ValueError:
                errors.append("Invalid spot price format")

        if errors:
            logger.error(f"Validation errors found: {errors}")
            raise ValidationError("\n".join(errors))
        else:
            logger.debug("All Spot Fleet prerequisites validation passed")

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
            logger.debug(f"Valid Spot Fleet service-linked role: {role_arn}")
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
            
            # Check permissions
            response = self.aws_client.iam_client.simulate_principal_policy(
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
            'TargetCapacity': request.num_requested,
            'IamFleetRole': fleet_role,
            'AllocationStrategy': template.allocation_strategy or 'lowestPrice',
            'Type': template.fleet_type,
            'TagSpecifications': [{
                'ResourceType': 'spot-fleet-request',
                'Tags': common_tags
            }]
        }

        # Add template tags if any
        if template.tags:
            instance_tags = [{'Key': k, 'Value': v} for k, v in template.tags.items()]
            fleet_config['TagSpecifications'][0]['Tags'].extend(instance_tags)
            fleet_config['TagSpecifications'][1]['Tags'].extend(instance_tags)

        # Add fleet type specific configurations
        if template.fleet_type == SpotFleetType.MAINTAIN.value:
            fleet_config['ReplaceUnhealthyInstances'] = True
            fleet_config['TerminateInstancesWithExpiration'] = True

        # Add spot price if specified
        if template.max_spot_price:
            fleet_config['SpotPrice'] = str(template.max_spot_price)

        # Add instance type overrides if specified
        if template.vm_types:
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
            
            # If we have both instance types and subnets, create all combinations
            if template.vm_types:
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
        logger.debug(f"Spot Fleet configuration: {json.dumps(fleet_config, indent=2)}")

        return fleet_config

    def _monitor_spot_prices(self, template: Template) -> Dict[str, float]:
        """Monitor current spot prices in specified regions/AZs."""
        try:
            prices = {}
            history = self._retry_with_backoff(
                self.aws_client.ec2_client.describe_spot_price_history,
                InstanceTypes=list(template.vm_types.keys()) if template.vm_types else [template.vm_type],
                ProductDescriptions=['Linux/UNIX'],
                MaxResults=100
            )
            
            for price in history['SpotPriceHistory']:
                key = f"{price['InstanceType']}-{price['AvailabilityZone']}"
                prices[key] = float(price['SpotPrice'])
            
            return prices

        except Exception as e:
            logger.warning(f"Failed to monitor spot prices: {str(e)}")
            return {}

    def check_hosts_status(self, request: Request) -> List[Dict[str, Any]]:
        """Check the status of instances in the spot fleet."""
        try:
            if not request.resource_id:
                raise InfrastructureError("No Spot Fleet Request ID found in request")

            # Get fleet information with retry mechanism
            fleet_response = self._retry_with_backoff(
                self.aws_client.ec2_client.describe_spot_fleet_requests,
                SpotFleetRequestIds=[request.resource_id]
            )

            if not fleet_response['SpotFleetRequestConfigs']:
                raise ResourceNotFoundError(f"Spot Fleet Request {request.resource_id} not found")

            fleet = fleet_response['SpotFleetRequestConfigs'][0]
            
            # Log fleet status
            logger.debug(f"Fleet status: {fleet.get('SpotFleetRequestState')}, "
                        f"Target capacity: {fleet.get('SpotFleetRequestConfig', {}).get('TargetCapacity')}, "
                        f"Fulfilled capacity: {fleet.get('ActivityStatus')}")

            # Get instance information with retry mechanism
            instances_response = self._retry_with_backoff(
                self.aws_client.ec2_client.describe_spot_fleet_instances,
                SpotFleetRequestId=request.resource_id
            )

            instance_ids = [
                instance['InstanceId'] 
                for instance in instances_response.get('ActiveInstances', [])
            ]

            if not instance_ids:
                logger.info(f"No active instances found in Spot Fleet {request.resource_id}")
                return []

            # Get detailed instance information
            return self._get_instance_details(instance_ids)

        except ClientError as e:
            error = self._convert_client_error(e)
            logger.error(f"Failed to check Spot Fleet status: {str(error)}")
            raise error
        except Exception as e:
            logger.error(f"Unexpected error checking Spot Fleet status: {str(e)}")
            raise InfrastructureError(f"Failed to check Spot Fleet status: {str(e)}")

    def release_hosts(self, request: Request, machine_names: Optional[List[str]] = None) -> None:
        """
        Release specific hosts or entire Spot Fleet.
        
        Args:
            request: The request containing the fleet and machine information
            machine_names: Optional list of specific machine names to release. If None, releases entire fleet.
        """
        try:
            if not request.resource_id:
                raise InfrastructureError("No Spot Fleet Request ID found in request")

            # Get fleet configuration first
            fleet_response = self._retry_with_backoff(
                self.aws_client.ec2_client.describe_spot_fleet_requests,
                SpotFleetRequestIds=[request.resource_id]
            )

            if not fleet_response['SpotFleetRequestConfigs']:
                raise ResourceNotFoundError(f"Spot Fleet {request.resource_id} not found")

            fleet = fleet_response['SpotFleetRequestConfigs'][0]
            fleet_type = fleet['SpotFleetRequestConfig'].get('Type', 'maintain')

            if machine_names:
                # Get instance IDs for the specified machines
                instances_response = self._retry_with_backoff(
                    self.aws_client.ec2_client.describe_instances,
                    Filters=[
                        {'Name': 'private-dns-name', 'Values': machine_names},
                        {'Name': 'tag:RequestId', 'Values': [str(request.request_id)]}
                    ]
                )

                instance_ids = []
                for reservation in instances_response.get('Reservations', []):
                    for instance in reservation['Instances']:
                        instance_ids.append(instance['InstanceId'])

                if instance_ids:
                    if fleet_type == 'maintain':
                        # For maintain fleets, reduce capacity first
                        current_capacity = fleet['SpotFleetRequestConfig']['TargetCapacity']
                        new_capacity = max(0, current_capacity - len(instance_ids))
                        
                        self._retry_with_backoff(
                            self.aws_client.ec2_client.modify_spot_fleet_request,
                            SpotFleetRequestId=request.resource_id,
                            TargetCapacity=new_capacity
                        )
                        logger.info(f"Reduced maintain fleet {request.resource_id} capacity to {new_capacity}")

                    # Now terminate the instances
                    self._retry_with_backoff(
                        self.aws_client.ec2_client.terminate_instances,
                        InstanceIds=instance_ids
                    )
                    logger.info(f"Terminated instances: {instance_ids}")
                else:
                    logger.warning(f"No instances found matching names: {machine_names}")

            else:
                # Release entire fleet
                self._retry_with_backoff(
                    self.aws_client.ec2_client.cancel_spot_fleet_requests,
                    SpotFleetRequestIds=[request.resource_id],
                    TerminateInstances=True
                )
                logger.info(f"Cancelled entire Spot Fleet request: {request.resource_id}")

        except ClientError as e:
            error = self._convert_client_error(e)
            logger.error(f"Failed to release Spot Fleet resources: {str(error)}")
            raise error