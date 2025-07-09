"""AWS RunInstances Handler.

This module provides the RunInstances handler implementation for managing
individual EC2 instance launches through the AWS EC2 RunInstances API.

The RunInstances handler provides direct control over individual EC2 instance
provisioning with support for both On-Demand and Spot instances, offering
simplicity and predictability for straightforward deployment scenarios.

Key Features:
    - Direct EC2 instance control
    - On-Demand and Spot instance support
    - Simple configuration and management
    - Immediate instance provisioning
    - Fine-grained instance control

Classes:
    RunInstancesHandler: Main handler for individual instance operations

Usage:
    This handler is used by the AWS provider to manage individual EC2
    instances for simple, predictable workloads that don't require
    advanced fleet management capabilities.

Note:
    RunInstances is ideal for simple deployments, development environments,
    and workloads that require predictable instance provisioning.
"""
from typing import Dict, Any, List
from datetime import datetime
import json
from botocore.exceptions import ClientError
import time

from src.domain.request.aggregate import Request
from src.domain.template.aggregate import Template
from src.providers.aws.infrastructure.handlers.base_handler import AWSHandler
from src.providers.aws.exceptions.aws_exceptions import (
    AWSValidationError, AWSInfrastructureError
)
from src.providers.aws.utilities.aws_operations import AWSOperations
from src.domain.base.ports import LoggingPort
from src.infrastructure.ports.request_adapter_port import RequestAdapterPort
from src.domain.base.dependency_injection import injectable
from src.infrastructure.error.decorators import handle_infrastructure_exceptions

@injectable
class RunInstancesHandler(AWSHandler):
    """Handler for direct EC2 instance operations using RunInstances."""
    
    def __init__(self, aws_client, logger: LoggingPort, aws_ops: AWSOperations, request_adapter: RequestAdapterPort = None):
        """
        Initialize the RunInstances handler.
        
        Args:
            aws_client: AWS client instance
            logger: Logger for logging messages
            aws_ops: AWS operations utility
            request_adapter: Optional request adapter for terminating instances
        """
        # Use enhanced base class initialization - eliminates duplication
        super().__init__(aws_client, logger, aws_ops, None, request_adapter)

    @handle_infrastructure_exceptions(context="run_instances_operation")
    def acquire_hosts(self, request: Request, template: Template) -> str:
        """
        Launch EC2 instances directly using RunInstances.
        Returns the reservation ID.
        """
        return self.aws_ops.execute_with_standard_error_handling(
            operation=lambda: self._run_instances_internal(request, template),
            operation_name="run instances",
            context="RunInstances"
        )

    def _run_instances_internal(self, request: Request, template: Template) -> str:
        """Internal method for RunInstances with pure business logic."""
        # Create launch template directly without additional retry wrapper
        launch_template = self.create_launch_template(template, request)
        
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

        # Launch instances with circuit breaker for critical operation
        response = self._retry_with_backoff(
            self.aws_client.ec2_client.run_instances,
            operation_type="critical",
            **instance_config
        )

        reservation_id = response['ReservationId']
        instance_ids = [instance['InstanceId'] for instance in response['Instances']]
        
        self._logger.info(f"Successfully launched instances. Reservation ID: {reservation_id}, "
                f"Instance IDs: {instance_ids}")

        # Store instance IDs directly in machine_ids set
        # This is the primary location for instance IDs
        for instance_id in instance_ids:
            request.machine_ids.add(instance_id)

        # Return immediately after successful launch
        return reservation_id

    @handle_infrastructure_exceptions(context="run_instances_termination")
    def release_hosts(self, request: Request) -> None:
        """
        Release hosts from a RunInstances request.
        
        Args:
            request: The request containing the instance information
        """
        # Get instance IDs from machine references
        instance_ids = []
        if request.machine_references:
            instance_ids = [m.machine_id for m in request.machine_references]
        else:
            # Fallback to getting all instances for this request
            instances_response = self._retry_with_backoff(
                self.aws_client.ec2_client.describe_instances,
                Filters=[
                    {'Name': 'tag:RequestId', 'Values': [str(request.request_id)]}
                ]
            )
            for reservation in instances_response.get('Reservations', []):
                for instance in reservation['Instances']:
                    instance_ids.append(instance['InstanceId'])

        if instance_ids:
            # Use consolidated AWS operations utility for instance termination
            self.aws_ops.terminate_instances_with_fallback(
                instance_ids,
                self._request_adapter,
                "RunInstances instances"
            )
            self._logger.info(f"Terminated instances: {instance_ids}")
        else:
            self._logger.warning(f"No instances found to terminate for request {request.request_id}")

    def check_hosts_status(self, request: Request) -> List[Dict[str, Any]]:
        """Check the status of launched instances."""
        try:
            # Get instance IDs from machine_ids set (primary source) or machine references
            instance_ids = list(request.machine_ids) if request.machine_ids else []
            
            # Fallback to machine references if machine_ids is empty
            if not instance_ids and request.machine_references:
                instance_ids = [str(machine_ref.machine_id) for machine_ref in request.machine_references]

            if not instance_ids:
                self._logger.info("No instances found to check status")
                return []

            # Get instance details with retry mechanism
            instances = self._get_instance_details(instance_ids)

            # Log instance statuses
            for instance in instances:
                self._logger.debug(f"Instance {instance['InstanceId']}: "
                           f"State={instance.get('State', {}).get('Name')}, "
                           f"Status={instance.get('Status')}")

            return instances

        except ClientError as e:
            error = self._convert_client_error(e)
            self._logger.error(f"Failed to check instance status: {str(error)}")
            raise error
        except Exception as e:
            self._logger.error(f"Unexpected error checking instance status: {str(e)}")
            raise AWSInfrastructureError(f"Failed to check instance status: {str(e)}")

    def _validate_run_instances_prerequisites(self, template: Template) -> None:
        """Validate RunInstances specific prerequisites."""
        errors = []

        # First validate common prerequisites
        try:
            self._validate_prerequisites(template)
        except AWSValidationError as e:
            errors.extend(str(e).split('\n'))

        # Validate instance type
        if not template.vm_type:
            errors.append("Instance type must be specified for RunInstances")

        # Validate maximum instance count
        if template.max_number > 20:  # AWS limit for RunInstances
            errors.append("Maximum instance count exceeded (limit is 20)")

        if errors:
            raise AWSValidationError("\n".join(errors))

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
                'MinCount': max(1, request.machine_count),
                'MaxCount': max(1, request.machine_count),
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

            # Remove SecurityGroupIds from config if it exists
            if 'SecurityGroupIds' in config:
                del config['SecurityGroupIds']

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

            self._logger.debug(f"Created RunInstances configuration: {json.dumps(config, indent=2)}")
            return config

        except Exception as e:
            self._logger.error(f"Failed to create RunInstances configuration: {str(e)}")
            raise AWSInfrastructureError(f"Failed to create RunInstances configuration: {str(e)}")

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
                    self._logger.warning("Timeout waiting for instances to stop")
                    break

                instances = self._get_instance_details(instance_ids)
                all_stopped = all(
                    instance.get('State', {}).get('Name') in ['stopped', 'terminated']
                    for instance in instances
                )

                if all_stopped:
                    break

                self._logger.info("Waiting for instances to stop...")
                time.sleep(10)

        except Exception as e:
            self._logger.warning(f"Error during graceful stop: {str(e)}")
            # Continue with termination even if stop fails
