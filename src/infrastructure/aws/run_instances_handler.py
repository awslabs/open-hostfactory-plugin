# src/infrastructure/aws/run_instances_handler.py
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json
from botocore.exceptions import ClientError
import time

from src.domain.request.request_aggregate import Request
from src.domain.template.template_aggregate import Template
from src.infrastructure.exceptions import InfrastructureError
from src.infrastructure.aws.base_handler import AWSHandler
from src.infrastructure.aws.exceptions import *

logger = logging.getLogger(__name__)

class RunInstancesHandler(AWSHandler):
    """Handler for direct EC2 instance operations using RunInstances."""

    def acquire_hosts(self, request: Request, template: Template) -> str:
        """
        Launch EC2 instances directly using RunInstances.
        Returns the reservation ID.
        """
        try:
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

            # Prepare run instances configuration
            instance_config = self._create_run_instances_config(
                template=template,
                request=request,
                launch_template_id=launch_template['LaunchTemplateId'],
                launch_template_version=launch_template['Version']
            )

            # Launch instances with retry mechanism
            response = self._retry_with_backoff(
                self.aws_client.ec2_client.run_instances,
                **instance_config
            )

            reservation_id = response['ReservationId']
            instance_ids = [instance['InstanceId'] for instance in response['Instances']]
            
            logger.info(f"Successfully launched instances. Reservation ID: {reservation_id}, "
                    f"Instance IDs: {instance_ids}")

            # Store instance IDs in request metadata
            request.metadata['instance_ids'] = instance_ids

            # Return immediately after successful launch
            return reservation_id

        except ClientError as e:
            error = self._convert_client_error(e)
            logger.error(f"Failed to launch EC2 instances: {str(error)}")
            raise error
        except Exception as e:
            logger.error(f"Unexpected error launching EC2 instances: {str(e)}")
            raise InfrastructureError(f"Failed to launch EC2 instances: {str(e)}")

    def release_hosts(self, request: Request, machine_names: Optional[List[str]] = None) -> None:
        """
        Release specific hosts from a RunInstances request.
        
        Args:
            request: The request containing the instance information
            machine_names: Optional list of specific machine names to release. If None, releases all instances.
        """
        try:
            if machine_names:
                # Get instance IDs for the specified machines
                instances_response = self._retry_with_backoff(
                    self.aws_client.ec2_client.describe_instances,
                    Filters=[
                        {'Name': 'private-dns-name', 'Values': machine_names},
                        {'Name': 'tag:RequestId', 'Values': [str(request.request_id)]}
                    ]
                )
            else:
                # Get all instances for this request
                instances_response = self._retry_with_backoff(
                    self.aws_client.ec2_client.describe_instances,
                    Filters=[
                        {'Name': 'tag:RequestId', 'Values': [str(request.request_id)]}
                    ]
                )

            instance_ids = []
            for reservation in instances_response.get('Reservations', []):
                for instance in reservation['Instances']:
                    instance_ids.append(instance['InstanceId'])

            if instance_ids:
                # Terminate the instances
                self._retry_with_backoff(
                    self.aws_client.ec2_client.terminate_instances,
                    InstanceIds=instance_ids
                )
                logger.info(f"Terminated instances: {instance_ids}")
            else:
                logger.warning(f"No instances found to terminate for request {request.request_id}")

        except ClientError as e:
            error = self._convert_client_error(e)
            logger.error(f"Failed to release instances: {str(error)}")
            raise error

    def check_hosts_status(self, request: Request) -> List[Dict[str, Any]]:
        """Check the status of launched instances."""
        try:
            # Get instance IDs from request metadata or machines
            instance_ids = request.metadata.get('instance_ids', [])
            if not instance_ids:
                instance_ids = [str(machine.machine_id) for machine in request.machines]

            if not instance_ids:
                logger.info("No instances found to check status")
                return []

            # Get instance details with retry mechanism
            instances = self._get_instance_details(instance_ids)

            # Log instance statuses
            for instance in instances:
                logger.debug(f"Instance {instance['InstanceId']}: "
                           f"State={instance.get('State', {}).get('Name')}, "
                           f"Status={instance.get('Status')}")

            return instances

        except ClientError as e:
            error = self._convert_client_error(e)
            logger.error(f"Failed to check instance status: {str(error)}")
            raise error
        except Exception as e:
            logger.error(f"Unexpected error checking instance status: {str(e)}")
            raise InfrastructureError(f"Failed to check instance status: {str(e)}")

    def _validate_run_instances_prerequisites(self, template: Template) -> None:
        """Validate RunInstances specific prerequisites."""
        errors = []

        # First validate common prerequisites
        try:
            self._validate_prerequisites(template)
        except ValidationError as e:
            errors.extend(str(e).split('\n'))

        # Validate instance type
        if not template.vm_type:
            errors.append("Instance type must be specified for RunInstances")

        # Validate maximum instance count
        if template.max_number > 20:  # AWS limit for RunInstances
            errors.append("Maximum instance count exceeded (limit is 20)")

        if errors:
            raise ValidationError("\n".join(errors))

    def _create_run_instances_config(self,
                                template: Template,
                                request: Request,
                                launch_template_id: str,
                                launch_template_version: str) -> Dict[str, Any]:
        """
        Create RunInstances configuration with enhanced options.
        
        Args:
            template: Template configuration
            request: Request instance
            launch_template_id: ID of the created launch template
            launch_template_version: Version of the launch template
            
        Returns:
            Dict containing RunInstances configuration
            
        Raises:
            InfrastructureError: If configuration creation fails
        """
        try:
            config = {
                'LaunchTemplate': {
                    'LaunchTemplateId': launch_template_id,
                    'Version': launch_template_version
                },
                'MinCount': request.num_requested,
                'MaxCount': request.num_requested,
                'TagSpecifications': [{
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Name', 'Value': f"hf-{request.request_id}"},
                        {'Key': 'RequestId', 'Value': str(request.request_id)},
                        {'Key': 'TemplateId', 'Value': str(template.template_id)},
                        {'Key': 'CreatedBy', 'Value': 'HostFactory'},
                        {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()}
                    ]
                }],
                'InstanceInitiatedShutdownBehavior': 'terminate',  # Ensure instances terminate on shutdown
                'Monitoring': {'Enabled': True}
            }

            # Add network configuration in a single place
            network_interface = {
                'DeviceIndex': 0,
                'AssociatePublicIpAddress': True,
                'Groups': template.security_group_ids
            }

            # Add subnet configuration
            if template.subnet_id:
                network_interface['SubnetId'] = template.subnet_id
            elif template.subnet_ids:
                network_interface['SubnetId'] = template.subnet_ids[0]

            # Add any additional network interface options
            if hasattr(template, 'network_interface_options'):
                network_interface.update(template.network_interface_options)

            config['NetworkInterfaces'] = [network_interface]

            # Add placement group if specified
            if hasattr(template, 'placement_group'):
                config['Placement'] = {
                    'GroupName': template.placement_group
                }

            # Add capacity reservation if specified
            if hasattr(template, 'capacity_reservation'):
                config['CapacityReservationSpecification'] = template.capacity_reservation

            # Add any additional instance tags from template
            if template.tags:
                config['TagSpecifications'][0]['Tags'].extend(
                    [{'Key': k, 'Value': v} for k, v in template.tags.items()]
                )

            # Add any client token for idempotency
            config['ClientToken'] = f"{request.request_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

            # Add any additional instance attributes
            if hasattr(template, 'instance_attributes'):
                config.update(template.instance_attributes)

            # Add any hibernation options
            if hasattr(template, 'hibernation_options'):
                config['HibernationOptions'] = template.hibernation_options

            # Add any license specifications
            if hasattr(template, 'license_specifications'):
                config['LicenseSpecifications'] = template.license_specifications

            logger.debug(f"Created RunInstances configuration: {json.dumps(config, indent=2)}")
            return config

        except Exception as e:
            logger.error(f"Failed to create RunInstances configuration: {str(e)}")
            raise InfrastructureError(f"Failed to create RunInstances configuration: {str(e)}")

    def _stop_instances_gracefully(self, instance_ids: List[str], timeout: int = 300) -> None:
        """Stop instances gracefully before termination."""
        try:
            # Send stop signal
            self._retry_with_backoff(
                self.aws_client.ec2_client.stop_instances,
                InstanceIds=instance_ids
            )

            # Wait for instances to stop
            start_time = time.time()
            while True:
                if time.time() - start_time > timeout:
                    logger.warning("Timeout waiting for instances to stop")
                    break

                instances = self._get_instance_details(instance_ids)
                all_stopped = all(
                    instance.get('State', {}).get('Name') in ['stopped', 'terminated']
                    for instance in instances
                )

                if all_stopped:
                    break

                logger.info("Waiting for instances to stop...")
                time.sleep(10)

        except Exception as e:
            logger.warning(f"Error during graceful stop: {str(e)}")
            # Continue with termination even if stop fails
