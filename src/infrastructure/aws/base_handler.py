import logging
import boto3
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from botocore.exceptions import ClientError

from src.domain.request.request_aggregate import Request
from src.domain.template.template_aggregate import Template
from src.infrastructure.exceptions import InfrastructureError
from src.infrastructure.aws.exceptions import *
from src.infrastructure.aws.aws_client import AWSClient

logger = logging.getLogger(__name__)

class AWSHandler(ABC):
    """
    Base class for AWS handlers.
    Defines common interface and shared functionality for all AWS handlers.
    """
    
    def __init__(self, aws_client: AWSClient):
        """
        Initialize AWS handler.

        Args:
            aws_client: Configured AWS client instance
        """
        self.aws_client = aws_client
        self._validate_aws_client()

        self.max_retries = 3
        self.base_delay = 1  # Base delay for exponential backoff (seconds)

    def _resolve_image_id(self, image_id: str) -> str:
        """
        Resolve image ID, handling both SSM parameters and direct AMI IDs.
        
        Args:
            image_id: Either an SSM parameter path or AMI ID
            
        Returns:
            str: Resolved AMI ID
            
        Raises:
            InfrastructureError: If image ID resolution fails
            
        Examples:
            - Direct AMI: "ami-1234567890abcdef0"
            - SSM Parameter: "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64"
        """
        # Check if it's a direct AMI ID
        if image_id.startswith('ami-'):
            logger.debug(f"Using direct AMI ID: {image_id}")
            return image_id
            
        # Check if it's an SSM parameter
        if image_id.startswith('/'):
            try:
                logger.debug(f"Resolving AMI ID from SSM parameter: {image_id}")
                ssm_client = self.aws_client.ssm_client
                response = ssm_client.get_parameter(Name=image_id)
                resolved_ami = response['Parameter']['Value']
                logger.info(f"Resolved SSM parameter {image_id} to AMI: {resolved_ami}")
                return resolved_ami
            except Exception as e:
                logger.error(f"Failed to resolve SSM parameter {image_id}: {str(e)}")
                raise InfrastructureError(f"Failed to resolve AMI ID from SSM parameter: {str(e)}")
                
        # If neither format matches
        raise InfrastructureError(
            f"Invalid image ID format: {image_id}. Must be either an AMI ID (ami-xxxxxx) "
            "or an SSM parameter path (/aws/service/...)"
        )

    def _validate_aws_client(self) -> None:
        """Validate that all required AWS clients are available."""
        required_clients = [
            'ec2_client',
            'ec2_resource',
            'iam_client',
            'autoscaling_client',
            'ssm_client'
        ]
        
        missing_clients = [
            client for client in required_clients
            if not hasattr(self.aws_client, client)
        ]
        
        if missing_clients:
            raise InfrastructureError(
                f"AWS client missing required clients: {', '.join(missing_clients)}"
            )

    def _create_launch_template_data(self, template: Template, request: Request) -> Dict[str, Any]:
        """
        Create Launch Template data with enhanced configuration.
        
        Args:
            template: Template with resolved AMI ID
            request: Request instance
            
        Returns:
            Dict containing launch template configuration
        """
        # Note: template.image_id should already be resolved by _validate_prerequisites
        launch_template_data = {
            'ImageId': template.image_id,  # Already resolved
            'InstanceType': template.vm_type,
            'SecurityGroupIds': template.security_group_ids,
            'Monitoring': {'Enabled': True},
            'MetadataOptions': {
                'HttpTokens': 'required',
                'HttpPutResponseHopLimit': 2
            }
        }

        if template.key_name:
            launch_template_data['KeyName'] = template.key_name

        if template.subnet_id:
            launch_template_data['NetworkInterfaces'] = [{
                'SubnetId': template.subnet_id,
                'DeviceIndex': 0,
                'AssociatePublicIpAddress': True
            }]

        # Add tags
        tags = [
            {'Key': 'Name', 'Value': f"hf-{request.request_id}"},
            {'Key': 'RequestId', 'Value': str(request.request_id)},
            {'Key': 'TemplateId', 'Value': str(template.template_id)},
            {'Key': 'CreatedBy', 'Value': 'HostFactory'},
            {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()}
        ]
        
        # Add template tags
        tags.extend([{'Key': k, 'Value': v} for k, v in template.tags.items()])
        
        launch_template_data['TagSpecifications'] = [{
            'ResourceType': 'instance',
            'Tags': tags
        }]

        return launch_template_data

    @abstractmethod
    def acquire_hosts(self, request: Request, template: Template) -> str:
        """
        Acquire hosts using the specific AWS mechanism.
        Returns the AWS resource ID (Fleet ID, ASG name, etc.).
        """
        pass

    @abstractmethod
    def release_hosts(self, request: Request) -> None:
        """Release hosts using the specific AWS mechanism."""
        pass

    @abstractmethod
    def check_hosts_status(self, request: Request) -> List[Dict[str, Any]]:
        """Check the status of hosts for a request."""
        pass

    def _retry_with_backoff(self, operation: callable, *args, **kwargs) -> Any:
        """Execute an operation with exponential backoff retry."""
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                return operation(*args, **kwargs)
            except ClientError as e:
                last_exception = e
                if not self._should_retry(e):
                    raise self._convert_client_error(e)
                
                delay = (2 ** attempt) * self.base_delay
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay} seconds: {str(e)}")
                time.sleep(delay)
        
        raise last_exception

    def _should_retry(self, error: ClientError) -> bool:
        """Determine if an error should trigger a retry."""
        error_code = error.response['Error']['Code']
        return error_code in [
            'RequestLimitExceeded',
            'ThrottlingException',
            'InternalError',
            'ServiceUnavailable',
            'TooManyRequestsException'
        ]

    def _convert_client_error(self, error: ClientError) -> AWSHandlerError:
        """Convert AWS ClientError to appropriate handler exception."""
        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']

        if 'InsufficientInstanceCapacity' in error_code:
            return CapacityError(f"Insufficient capacity: {error_message}")
        elif 'VpcNotFound' in error_code or 'SubnetNotFound' in error_code:
            return NetworkError(f"Network configuration error: {error_message}")
        elif 'InvalidIamRole' in error_code or 'UnauthorizedOperation' in error_code:
            return IAMError(f"IAM error: {error_message}")
        elif 'LimitExceeded' in error_code:
            return QuotaError(f"AWS quota exceeded: {error_message}")
        elif 'NotFound' in error_code:
            return ResourceNotFoundError(f"Resource not found: {error_message}")
        elif 'Validation' in error_code:
            return ValidationError(f"Validation error: {error_message}")
        
        return AWSHandlerError(f"AWS error: {error_message}")

    def create_launch_template(self, template: Template, request: Request) -> Dict[str, str]:
        """
        Create an AWS Launch Template for the request.
        
        Args:
            template: Template configuration
            request: Request instance
            
        Returns:
            Dict containing LaunchTemplateId and Version
            
        Raises:
            InfrastructureError: If template creation fails
        """
        try:
            # First resolve the AMI ID
            resolved_ami = self._resolve_image_id(template.image_id)
            template.image_id = resolved_ami
            
            # Now create launch template data with the resolved AMI
            launch_template_data = {
                'ImageId': resolved_ami,
                'InstanceType': template.vm_type,
                'Monitoring': {'Enabled': True},
                'MetadataOptions': {
                    'HttpTokens': 'required',
                    'HttpPutResponseHopLimit': 2
                }
            }

            if template.key_name:
                launch_template_data['KeyName'] = template.key_name

            # Add tags
            tags = [
                {'Key': 'Name', 'Value': f"hf-{request.request_id}"},
                {'Key': 'RequestId', 'Value': str(request.request_id)},
                {'Key': 'TemplateId', 'Value': str(template.template_id)},
                {'Key': 'CreatedBy', 'Value': 'HostFactory'},
                {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()}
            ]
            
            # Add template tags
            if template.tags:
                tags.extend([{'Key': k, 'Value': v} for k, v in template.tags.items()])
            
            launch_template_data['TagSpecifications'] = [{
                'ResourceType': 'instance',
                'Tags': tags
            }]

            # Add user data if provided
            if template.user_data:
                launch_template_data['UserData'] = template.user_data

            # Add any additional instance metadata options
            if hasattr(template, 'metadata_options'):
                launch_template_data['MetadataOptions'].update(template.metadata_options)

            # Add any additional block device mappings
            if hasattr(template, 'block_device_mappings'):
                launch_template_data['BlockDeviceMappings'] = template.block_device_mappings

            # Add any additional IAM instance profile
            if hasattr(template, 'iam_instance_profile'):
                launch_template_data['IamInstanceProfile'] = template.iam_instance_profile

            # Add any additional instance market options (spot)
            if hasattr(template, 'instance_market_options'):
                launch_template_data['InstanceMarketOptions'] = template.instance_market_options

            # Add any CPU options
            if hasattr(template, 'cpu_options'):
                launch_template_data['CpuOptions'] = template.cpu_options

            # Create launch template with retry
            response = self._retry_with_backoff(
                self.aws_client.ec2_client.create_launch_template,
                LaunchTemplateName=f"lt-{request.request_id}",
                LaunchTemplateData=launch_template_data,
                VersionDescription=f"Created for request {request.request_id}"
            )
            
            logger.info(f"Created launch template {response['LaunchTemplate']['LaunchTemplateId']} "
                    f"version {response['LaunchTemplate']['LatestVersionNumber']}")
            
            return {
                'LaunchTemplateId': response['LaunchTemplate']['LaunchTemplateId'],
                'Version': str(response['LaunchTemplate']['LatestVersionNumber'])
            }
            
        except Exception as e:
            logger.error(f"Failed to create launch template: {str(e)}")
            raise

    def _get_instance_details(self, instance_ids: List[str]) -> List[Dict[str, Any]]:
        """Get details for specific instances with retry."""
        return self._retry_with_backoff(
            self.aws_client.describe_instances,
            instance_ids
        )

    def _create_tags(self, resource_ids: List[str], tags: Dict[str, str]) -> None:
        """Create tags for AWS resources with retry."""
        self._retry_with_backoff(
            self.aws_client.create_tags,
            resource_ids,
            tags
        )

    def _terminate_instances(self, instance_ids: List[str]) -> None:
        """Terminate EC2 instances with retry."""
        self._retry_with_backoff(
            self.aws_client.terminate_instances,
            instance_ids
        )

    def _validate_prerequisites(self, template: Template) -> None:
        """Validate AWS prerequisites."""
        errors = []
        logger.debug(f"Starting base prerequisites validation for template: {template.template_id}")

        try:
            # Resolve and validate AMI ID first
            logger.debug(f"Resolving AMI ID from: {template.image_id}")
            resolved_ami = self._resolve_image_id(template.image_id)
            logger.debug(f"Successfully resolved AMI ID to: {resolved_ami}")
            template.image_id = resolved_ami
        except Exception as e:
            error_msg = f"Invalid image ID: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        # Validate VPC/Subnet
        try:
            if template.subnet_id:
                logger.debug(f"Validating subnet: {template.subnet_id}")
                self.aws_client.ec2_client.describe_subnets(SubnetIds=[template.subnet_id])
                logger.debug("Subnet validation passed")
        except Exception as e:
            logger.error(f"Subnet validation failed: {str(e)}")
            errors.append(f"Invalid subnet: {str(e)}")

        # Validate Security Groups
        try:
            if template.security_group_ids:
                logger.debug(f"Validating security groups: {template.security_group_ids}")
                self.aws_client.ec2_client.describe_security_groups(
                    GroupIds=template.security_group_ids
                )
                logger.debug("Security groups validation passed")
        except Exception as e:
            logger.error(f"Security groups validation failed: {str(e)}")
            errors.append(f"Invalid security groups: {str(e)}")

        if errors:
            logger.error(f"Base validation errors found: {errors}")
            raise ValidationError("\n".join(errors))
        else:
            logger.debug("All base prerequisites validation passed")