from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from botocore.exceptions import ClientError

from src.domain.request.request_aggregate import Request
from src.domain.template.template_aggregate import Template
from src.domain.template.value_objects import EC2FleetType
from src.infrastructure.exceptions import InfrastructureError
from src.infrastructure.aws.base_handler import AWSHandler
from src.infrastructure.aws.exceptions import *

logger = logging.getLogger(__name__)

class EC2FleetHandler(AWSHandler):
    """Handler for EC2 Fleet operations."""

    def acquire_hosts(self, request: Request, template: Template) -> str:
        """
        Create an EC2 Fleet to acquire hosts.
        Returns the Fleet ID.
        """
        try:
            # Validate prerequisites
            self._validate_prerequisites(template)
            
            # Validate fleet type
            if not template.fleet_type:
                raise ValidationError("Fleet type is required for EC2Fleet")
            try:
                fleet_type = EC2FleetType(template.fleet_type.lower())
            except ValueError:
                raise ValidationError(f"Invalid EC2 fleet type: {template.fleet_type}. "
                                   f"Must be one of: {', '.join(EC2FleetType.__members__.keys())}")

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

            # Create fleet configuration
            fleet_config = self._create_fleet_config(
                template=template,
                request=request,
                launch_template_id=launch_template['LaunchTemplateId'],
                launch_template_version=launch_template['Version']
            )

            # Create the fleet with retry mechanism
            response = self._retry_with_backoff(
                self.aws_client.ec2_client.create_fleet,
                **fleet_config
            )

            fleet_id = response['FleetId']
            logger.info(f"Successfully created EC2 Fleet: {fleet_id}")

            # For instant fleets, store instance IDs in request metadata
            if fleet_type == EC2FleetType.INSTANT:
                instance_ids = []
                for instance_set in response.get('Instances', []):
                    instance_ids.extend([inst['InstanceId'] for inst in instance_set['Instances']])
                request.metadata['instance_ids'] = instance_ids
                logger.debug(f"Stored instance IDs in request metadata: {instance_ids}")

            return fleet_id

        except ClientError as e:
            error = self._convert_client_error(e)
            logger.error(f"Failed to create EC2 Fleet: {str(error)}")
            raise error
        except Exception as e:
            logger.error(f"Unexpected error creating EC2 Fleet: {str(e)}")
            raise InfrastructureError(f"Failed to create EC2 Fleet: {str(e)}")

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
                'TotalTargetCapacity': request.num_requested,
                'DefaultTargetCapacityType': 'on-demand'
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
        if template.fleet_type == EC2FleetType.MAINTAIN.value:
            fleet_config['ReplaceUnhealthyInstances'] = True
            fleet_config['ExcessCapacityTerminationPolicy'] = 'termination'

        # Add overrides if multiple instance types are specified
        if template.vm_types:
            fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = [
                {'InstanceType': instance_type}
                for instance_type in template.vm_types.keys()
            ]

        # Add subnet configuration
        if template.subnet_ids:
            if 'Overrides' not in fleet_config['LaunchTemplateConfigs'][0]:
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = []
            
            # If we have both instance types and subnets, create all combinations
            if template.vm_types:
                overrides = []
                for subnet_id in template.subnet_ids:
                    for instance_type in template.vm_types.keys():
                        overrides.append({
                            'SubnetId': subnet_id,
                            'InstanceType': instance_type
                        })
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = overrides
            else:
                fleet_config['LaunchTemplateConfigs'][0]['Overrides'] = [
                    {'SubnetId': subnet_id} for subnet_id in template.subnet_ids
                ]

        return fleet_config

    def check_hosts_status(self, request: Request) -> List[Dict[str, Any]]:
        """Check the status of instances in the fleet."""
        try:
            if not request.resource_id:
                raise InfrastructureError("No Fleet ID found in request")

            # Get template to determine fleet type
            template = self._template_service.get_template(str(request.template_id))
            fleet_type = EC2FleetType(template.fleet_type.lower())

            # Get fleet information with retry mechanism
            fleet_response = self._retry_with_backoff(
                self.aws_client.ec2_client.describe_fleets,
                FleetIds=[request.resource_id]
            )

            if not fleet_response['Fleets']:
                raise ResourceNotFoundError(f"Fleet {request.resource_id} not found")

            fleet = fleet_response['Fleets'][0]
            
            # Log fleet status
            logger.debug(f"Fleet status: {fleet.get('Status')}, "
                        f"Target capacity: {fleet.get('TargetCapacitySpecification', {}).get('TotalTargetCapacity')}, "
                        f"Fulfilled capacity: {fleet.get('FulfilledCapacity', 0)}")

            # Get instance IDs based on fleet type
            instance_ids = []
            if fleet_type == EC2FleetType.INSTANT:
                # For instant fleets, get instance IDs from metadata
                instance_ids = request.metadata.get('instance_ids', [])
            else:
                # For request/maintain fleets, describe fleet instances
                instances_response = self._retry_with_backoff(
                    self.aws_client.ec2_client.describe_fleet_instances,
                    FleetId=request.resource_id
                )
                instance_ids = [
                    instance['InstanceId'] 
                    for instance in instances_response.get('ActiveInstances', [])
                ]

            if not instance_ids:
                logger.info(f"No active instances found in fleet {request.resource_id}")
                return []

            # Get detailed instance information
            return self._get_instance_details(instance_ids)

        except ClientError as e:
            error = self._convert_client_error(e)
            logger.error(f"Failed to check EC2 Fleet status: {str(error)}")
            raise error
        except Exception as e:
            logger.error(f"Unexpected error checking EC2 Fleet status: {str(e)}")
            raise InfrastructureError(f"Failed to check EC2 Fleet status: {str(e)}")

    def release_hosts(self, request: Request, machine_names: Optional[List[str]] = None) -> None:
        """
        Release specific hosts or entire EC2 Fleet.
        
        Args:
            request: The request containing the fleet and machine information
            machine_names: Optional list of specific machine names to release. If None, releases entire fleet.
        """
        try:
            if not request.resource_id:
                raise InfrastructureError("No EC2 Fleet ID found in request")

            # Get fleet configuration first
            fleet_response = self._retry_with_backoff(
                self.aws_client.ec2_client.describe_fleets,
                FleetIds=[request.resource_id]
            )

            if not fleet_response['Fleets']:
                raise ResourceNotFoundError(f"EC2 Fleet {request.resource_id} not found")

            fleet = fleet_response['Fleets'][0]
            fleet_type = fleet.get('Type', 'maintain')

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
                        # For maintain fleets, reduce target capacity first
                        current_capacity = fleet['TargetCapacitySpecification']['TotalTargetCapacity']
                        new_capacity = max(0, current_capacity - len(instance_ids))
                        
                        self._retry_with_backoff(
                            self.aws_client.ec2_client.modify_fleet,
                            FleetId=request.resource_id,
                            TargetCapacitySpecification={
                                'TotalTargetCapacity': new_capacity
                            }
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
                # Delete entire fleet
                self._retry_with_backoff(
                    self.aws_client.ec2_client.delete_fleets,
                    FleetIds=[request.resource_id],
                    TerminateInstances=True
                )
                logger.info(f"Deleted EC2 Fleet: {request.resource_id}")

        except ClientError as e:
            error = self._convert_client_error(e)
            logger.error(f"Failed to release EC2 Fleet resources: {str(error)}")
            raise error