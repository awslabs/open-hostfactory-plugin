"""
AWS Machine Adapter

This module provides an adapter for AWS-specific machine operations.
It extracts AWS-specific logic from the domain layer.
"""

from typing import Any, Dict

from src.domain.base.dependency_injection import injectable
from src.domain.base.ports import LoggingPort
from src.domain.base.value_objects import InstanceType
from src.domain.machine.aggregate import Machine
from src.domain.machine.value_objects import MachineStatus, PriceType
from src.providers.aws.domain.template.value_objects import ProviderApi
from src.providers.aws.exceptions.aws_exceptions import (
    AWSError,
    EC2InstanceNotFoundError,
    NetworkError,
    RateLimitError,
    ResourceCleanupError,
)
from src.providers.aws.infrastructure.aws_client import AWSClient


@injectable
class AWSMachineAdapter:
    """Adapter for AWS-specific machine operations."""

    def __init__(self, aws_client: AWSClient, logger: LoggingPort):
        """
        Initialize the adapter.

        Args:
            aws_client: AWS client instance
            logger: Logger for logging messages
        """
        self._aws_client = aws_client
        self._logger = logger

    def create_machine_from_aws_instance(
        self,
        aws_instance_data: Dict[str, Any],
        request_id: str,
        provider_api: str,
        resource_id: str,
    ) -> Dict[str, Any]:
        """
        Convert AWS instance data to machine domain data.

        Args:
            aws_instance_data: Raw AWS instance data
            request_id: Associated request ID
            provider_api: Provider API type used
            resource_id: Resource ID (e.g., fleet ID)

        Returns:
            Dictionary with machine data in domain format

        Raises:
            AWSError: If there's an issue processing the AWS instance data
        """
        self._logger.debug(
            f"Creating machine from AWS instance: {aws_instance_data.get('InstanceId')}"
        )

        try:
            # Validate required fields
            required_fields = [
                "InstanceId",
                "State",
                "InstanceType",
                "PrivateIpAddress",
                "Placement",
                "SubnetId",
                "VpcId",
                "ImageId",
            ]
            for field in required_fields:
                if field not in aws_instance_data:
                    self._logger.error(f"Missing required field in AWS instance data: {field}")
                    raise AWSError(f"Missing required field in AWS instance data: {field}")

            # Validate AWS handler type
            try:
                ProviderApi(provider_api)
            except ValueError:
                self._logger.error(f"Invalid provider API type: {provider_api}")
                raise AWSError(f"Invalid provider API type: {provider_api}")

            # Validate instance type
            try:
                InstanceType(aws_instance_data["InstanceType"])
            except ValueError:
                self._logger.error(f"Invalid instance type: {aws_instance_data['InstanceType']}")
                raise AWSError(f"Invalid instance type: {aws_instance_data['InstanceType']}")

            # Extract core machine data
            machine_data = {
                "machine_id": aws_instance_data["InstanceId"],
                "request_id": request_id,
                "name": aws_instance_data.get("PrivateDnsName", ""),
                "status": MachineStatus.from_aws_state(aws_instance_data["State"]["Name"]).value,
                "instance_type": aws_instance_data["InstanceType"],
                "private_ip": aws_instance_data["PrivateIpAddress"],
                "public_ip": aws_instance_data.get("PublicIpAddress"),
                "provider_api": provider_api,
                "resource_id": resource_id,
                "price_type": (
                    PriceType.SPOT.value
                    if aws_instance_data.get("InstanceLifecycle") == "spot"
                    else PriceType.ON_DEMAND.value
                ),
                "cloud_host_id": aws_instance_data.get("Placement", {}).get("HostId"),
                "metadata": {
                    "availability_zone": aws_instance_data["Placement"]["AvailabilityZone"],
                    "subnet_id": aws_instance_data["SubnetId"],
                    "vpc_id": aws_instance_data["VpcId"],
                    "ami_id": aws_instance_data["ImageId"],
                    "ebs_optimized": aws_instance_data.get("EbsOptimized", False),
                    "monitoring": aws_instance_data.get("Monitoring", {}).get("State", "disabled"),
                    "tags": {tag["Key"]: tag["Value"] for tag in aws_instance_data.get("Tags", [])},
                },
            }

            self._logger.debug(
                f"Successfully created machine data for {machine_data['machine_id']}"
            )
            return machine_data

        except KeyError as e:
            self._logger.error(f"Missing key in AWS instance data: {str(e)}")
            raise AWSError(f"Missing key in AWS instance data: {str(e)}")
        except Exception as e:
            self._logger.error(f"Failed to create machine from AWS instance: {str(e)}")
            raise AWSError(f"Failed to create machine from AWS instance: {str(e)}")

    def perform_health_check(self, machine: Machine) -> Dict[str, Any]:
        """
        Perform health check on AWS instance.

        Args:
            machine: Machine domain entity

        Returns:
            Dictionary with health check results

        Raises:
            EC2InstanceNotFoundError: If the instance cannot be found
            AWSError: For other AWS-related errors
        """
        self._logger.debug(f"Performing health check for machine: {machine.machine_id}")

        try:
            health_checks = {}

            # Get instance status using circuit breaker
            def get_instance_status():
                """Get EC2 instance status from AWS."""
                return self._aws_client.ec2_client.describe_instance_status(
                    InstanceIds=[str(machine.machine_id)]
                )

            try:
                status = self._aws_client.execute_with_circuit_breaker(
                    "ec2", "describe_instance_status", get_instance_status
                )
            except NetworkError as e:
                self._logger.error(f"Network error during health check: {str(e)}")
                health_checks["system"] = {
                    "status": False,
                    "details": {"reason": f"Network error: {str(e)}"},
                }
                return health_checks
            except RateLimitError as e:
                self._logger.warning(f"Rate limit exceeded during health check: {str(e)}")
                health_checks["system"] = {
                    "status": False,
                    "details": {"reason": f"Rate limit exceeded: {str(e)}"},
                }
                return health_checks
            except AWSError as e:
                error_code = getattr(e, "error_code", "")
                if error_code == "InvalidInstanceID.NotFound":
                    self._logger.error(f"Instance not found: {machine.machine_id}")
                    raise EC2InstanceNotFoundError(str(machine.machine_id))
                else:
                    self._logger.error(f"AWS error during health check: {str(e)}")
                    raise AWSError(
                        f"AWS error during health check: {str(e)}", error_code=error_code
                    )

            if not status["InstanceStatuses"]:
                self._logger.warning(
                    f"No status information available for instance: {machine.machine_id}"
                )
                health_checks["system"] = {
                    "status": False,
                    "details": {"reason": "Instance status not available"},
                }
                return health_checks

            instance_status = status["InstanceStatuses"][0]

            # Check system status
            system_status = instance_status["SystemStatus"]["Status"] == "ok"
            health_checks["system"] = {
                "status": system_status,
                "details": {
                    "status": instance_status["SystemStatus"]["Status"],
                    "details": instance_status["SystemStatus"].get("Details", []),
                },
            }

            # Check instance status
            instance_health = instance_status["InstanceStatus"]["Status"] == "ok"
            health_checks["instance"] = {
                "status": instance_health,
                "details": {
                    "status": instance_status["InstanceStatus"]["Status"],
                    "details": instance_status["InstanceStatus"].get("Details", []),
                },
            }

            self._logger.debug(
                f"Health check completed for {machine.machine_id}: system={system_status}, instance={instance_health}"
            )
            return health_checks

        except EC2InstanceNotFoundError:
            # Re-raise specific exceptions
            raise
        except AWSError:
            # Re-raise specific exceptions
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error during health check: {str(e)}")
            raise AWSError(f"Unexpected error during health check: {str(e)}")

    def cleanup_machine_resources(self, machine: Machine) -> Dict[str, Any]:
        """
        Clean up AWS resources associated with machine.

        Args:
            machine: Machine domain entity

        Returns:
            Dictionary with cleanup results

        Raises:
            ResourceCleanupError: If there's an issue cleaning up resources
            EC2InstanceNotFoundError: If the instance cannot be found
        """
        self._logger.debug(f"Cleaning up resources for machine: {machine.machine_id}")

        cleanup_results = {
            "volumes": {"success": [], "failed": []},
            "network_interfaces": {"success": [], "failed": []},
        }

        try:
            # Check if instance exists using circuit breaker
            def check_instance_exists():
                """Check if EC2 instance exists in AWS."""
                return self._aws_client.ec2_client.describe_instances(
                    InstanceIds=[str(machine.machine_id)]
                )

            try:
                self._aws_client.execute_with_circuit_breaker(
                    "ec2", "describe_instances", check_instance_exists
                )
            except NetworkError as e:
                self._logger.error(f"Network error checking instance existence: {str(e)}")
                raise AWSError(f"Network error checking instance existence: {str(e)}")
            except RateLimitError as e:
                self._logger.warning(f"Rate limit exceeded checking instance existence: {str(e)}")
                raise AWSError(f"Rate limit exceeded checking instance existence: {str(e)}")
            except AWSError as e:
                error_code = getattr(e, "error_code", "")
                if error_code == "InvalidInstanceID.NotFound":
                    self._logger.error(f"Instance not found during cleanup: {machine.machine_id}")
                    raise EC2InstanceNotFoundError(str(machine.machine_id))
                else:
                    self._logger.error(f"AWS error during cleanup: {str(e)}")
                    raise AWSError(f"AWS error during cleanup: {str(e)}", error_code=error_code)

            # Detach and delete EBS volumes using circuit breaker
            try:

                def get_volumes():
                    """Get EBS volumes attached to the EC2 instance."""
                    return self._aws_client.ec2_client.describe_volumes(
                        Filters=[
                            {"Name": "attachment.instance-id", "Value": [str(machine.machine_id)]}
                        ]
                    )

                volumes = self._aws_client.execute_with_circuit_breaker(
                    "ec2", "describe_volumes", get_volumes
                )

                for volume in volumes["Volumes"]:
                    volume_id = volume["VolumeId"]
                    try:
                        if volume["State"] == "in-use":
                            self._logger.debug(
                                f"Detaching volume {volume_id} from {machine.machine_id}"
                            )

                            def detach_volume():
                                return self._aws_client.ec2_client.detach_volume(VolumeId=volume_id)

                            self._aws_client.execute_with_circuit_breaker(
                                "ec2", "detach_volume", detach_volume
                            )

                            self._logger.debug(f"Deleting volume {volume_id}")

                            def delete_volume():
                                return self._aws_client.ec2_client.delete_volume(VolumeId=volume_id)

                            self._aws_client.execute_with_circuit_breaker(
                                "ec2", "delete_volume", delete_volume
                            )

                            cleanup_results["volumes"]["success"].append(volume_id)
                    except AWSError as e:
                        self._logger.error(f"Failed to cleanup volume {volume_id}: {str(e)}")
                        cleanup_results["volumes"]["failed"].append(
                            {"id": volume_id, "error": str(e)}
                        )
            except AWSError as e:
                self._logger.error(f"Error processing volumes for {machine.machine_id}: {str(e)}")
                # Continue with other resources even if volumes fail

            # Delete network interfaces using circuit breaker
            try:

                def get_network_interfaces():
                    """Get network interfaces attached to the EC2 instance."""
                    return self._aws_client.ec2_client.describe_network_interfaces(
                        Filters=[
                            {"Name": "attachment.instance-id", "Value": [str(machine.machine_id)]}
                        ]
                    )

                nics = self._aws_client.execute_with_circuit_breaker(
                    "ec2", "describe_network_interfaces", get_network_interfaces
                )

                for nic in nics["NetworkInterfaces"]:
                    nic_id = nic["NetworkInterfaceId"]
                    try:
                        if nic["Status"] == "in-use":
                            attachment_id = nic["Attachment"]["AttachmentId"]
                            self._logger.debug(
                                f"Detaching network interface {nic_id} from {machine.machine_id}"
                            )

                            def detach_network_interface():
                                return self._aws_client.ec2_client.detach_network_interface(
                                    AttachmentId=attachment_id
                                )

                            self._aws_client.execute_with_circuit_breaker(
                                "ec2", "detach_network_interface", detach_network_interface
                            )

                            self._logger.debug(f"Deleting network interface {nic_id}")

                            def delete_network_interface():
                                return self._aws_client.ec2_client.delete_network_interface(
                                    NetworkInterfaceId=nic_id
                                )

                            self._aws_client.execute_with_circuit_breaker(
                                "ec2", "delete_network_interface", delete_network_interface
                            )

                            cleanup_results["network_interfaces"]["success"].append(nic_id)
                    except AWSError as e:
                        self._logger.error(
                            f"Failed to cleanup network interface {nic_id}: {str(e)}"
                        )
                        cleanup_results["network_interfaces"]["failed"].append(
                            {"id": nic_id, "error": str(e)}
                        )
            except AWSError as e:
                self._logger.error(
                    f"Error processing network interfaces for {machine.machine_id}: {str(e)}"
                )
                # Continue with other resources even if network interfaces fail

            self._logger.debug(f"Resource cleanup completed for {machine.machine_id}")
            return cleanup_results

        except EC2InstanceNotFoundError:
            # Re-raise specific exceptions
            raise
        except AWSError:
            # Re-raise specific exceptions
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error during resource cleanup: {str(e)}")
            raise ResourceCleanupError(
                f"Failed to cleanup resources for {machine.machine_id}: {str(e)}",
                str(machine.machine_id),
                "EC2Instance",
            )

    def get_machine_details(self, machine: Machine) -> Dict[str, Any]:
        """
        Get detailed AWS information for a machine.

        Args:
            machine: Machine domain entity

        Returns:
            Dictionary with detailed AWS information

        Raises:
            EC2InstanceNotFoundError: If the instance cannot be found
            AWSError: For other AWS-related errors
        """
        self._logger.debug(f"Getting details for machine: {machine.machine_id}")

        try:
            # Get instance details using circuit breaker
            def get_instance_details():
                """Get detailed EC2 instance information from AWS."""
                return self._aws_client.ec2_client.describe_instances(
                    InstanceIds=[str(machine.machine_id)]
                )

            try:
                response = self._aws_client.execute_with_circuit_breaker(
                    "ec2", "describe_instances", get_instance_details
                )

                if not response["Reservations"] or not response["Reservations"][0]["Instances"]:
                    self._logger.error(f"Instance not found: {machine.machine_id}")
                    raise EC2InstanceNotFoundError(str(machine.machine_id))

                instance_info = response["Reservations"][0]["Instances"][0]

            except NetworkError as e:
                self._logger.error(f"Network error getting machine details: {str(e)}")
                raise AWSError(f"Network error getting machine details: {str(e)}")
            except RateLimitError as e:
                self._logger.warning(f"Rate limit exceeded getting machine details: {str(e)}")
                raise AWSError(f"Rate limit exceeded getting machine details: {str(e)}")
            except AWSError as e:
                error_code = getattr(e, "error_code", "")
                if error_code == "InvalidInstanceID.NotFound":
                    self._logger.error(f"Instance not found: {machine.machine_id}")
                    raise EC2InstanceNotFoundError(str(machine.machine_id))
                else:
                    self._logger.error(f"AWS error getting machine details: {str(e)}")
                    raise AWSError(
                        f"AWS error getting machine details: {str(e)}", error_code=error_code
                    )

            # Build details object
            details = {
                "aws_details": {
                    "placement": instance_info["Placement"],
                    "network": {
                        "vpc_id": instance_info["VpcId"],
                        "subnet_id": instance_info["SubnetId"],
                        "security_groups": instance_info["SecurityGroups"],
                    },
                    "block_devices": instance_info["BlockDeviceMappings"],
                    "ebs_optimized": instance_info["EbsOptimized"],
                    "monitoring": instance_info["Monitoring"],
                    "iam_instance_profile": instance_info.get("IamInstanceProfile", {}),
                    "tags": {tag["Key"]: tag["Value"] for tag in instance_info.get("Tags", [])},
                }
            }

            self._logger.debug(f"Successfully retrieved details for {machine.machine_id}")
            return details

        except EC2InstanceNotFoundError:
            # Re-raise specific exceptions
            raise
        except AWSError:
            # Re-raise specific exceptions
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error getting machine details: {str(e)}")
            raise AWSError(f"Unexpected error getting machine details: {str(e)}")
