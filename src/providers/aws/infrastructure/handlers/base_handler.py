"""Base AWS handler with common functionality."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, TypeVar, Callable
from botocore.exceptions import ClientError

from src.domain.template.aggregate import Template
from src.domain.request.aggregate import Request
from src.providers.aws.infrastructure.aws_client import AWSClient
from src.providers.aws.exceptions.aws_exceptions import (
    AWSEntityNotFoundError,
    AWSValidationError,
    QuotaExceededError,
    ResourceInUseError,
    AuthorizationError,
    RateLimitError,
    NetworkError,
    InfrastructureError
)
from src.domain.base.ports import LoggingPort
from src.infrastructure.resilience import retry
from src.infrastructure.utilities.common.resource_naming import (
    get_launch_template_name,
    get_instance_name
)
from src.domain.base.dependency_injection import injectable

T = TypeVar('T')

@injectable
class AWSHandler(ABC):
    """Base class for AWS resource handlers."""

    def __init__(self, aws_client: AWSClient, logger: LoggingPort, 
                 aws_ops=None, template_config_store=None, request_adapter=None) -> None:
        """
        Initialize AWS handler with common dependencies.
        
        Args:
            aws_client: AWS client instance
            logger: Logger for logging messages
            aws_ops: AWS operations utility (optional)
            template_config_store: Template configuration store for retrieving templates (optional)
            request_adapter: Request adapter for terminating instances (optional)
        """
        self.aws_client = aws_client
        self._logger = logger
        self.max_retries = 3
        self.base_delay = 1  # seconds
        self.max_delay = 10  # seconds
        
        # Setup common dependencies if provided
        if aws_ops:
            self._setup_aws_operations(aws_ops)
        if template_config_store is not None or request_adapter is not None:
            self._setup_dependencies(template_config_store, request_adapter)
    
    def _setup_aws_operations(self, aws_ops):
        """Configure AWS operations utility - eliminates duplication across handlers."""
        self.aws_ops = aws_ops
        self.aws_ops.set_retry_method(self._retry_with_backoff)
        self.aws_ops.set_pagination_method(self._paginate)
    
    def _setup_dependencies(self, template_config_store, request_adapter):
        """Configure optional dependencies - eliminates duplication across handlers."""
        self._template_config_store = template_config_store
        self._request_adapter = request_adapter
        
        # Standardized logging for request adapter status
        if request_adapter:
            self._logger.debug("Successfully initialized request adapter")
        else:
            self._logger.debug("No request adapter provided, will use EC2 client directly")

    @abstractmethod
    def acquire_hosts(self, request: Request, template: Template) -> str:
        """
        Acquire hosts using the specified template.
        
        Args:
            request: The request to fulfill
            template: The template to use
            
        Returns:
            str: The AWS resource ID (e.g., fleet ID)
            
        Raises:
            ValidationError: If the template is invalid
            QuotaExceededError: If AWS quotas would be exceeded
            InfrastructureError: For other AWS API errors
        """

    @abstractmethod
    def check_hosts_status(self, request: Request) -> List[Dict[str, Any]]:
        """
        Check the status of hosts for a request.
        
        Args:
            request: The request to check
            
        Returns:
            List of instance details
            
        Raises:
            AWSEntityNotFoundError: If the AWS resource is not found
            InfrastructureError: For other AWS API errors
        """

    @abstractmethod
    def release_hosts(self, request: Request) -> None:
        """
        Release hosts associated with a request.
        
        Args:
            request: The request containing hosts to release
            
        Raises:
            AWSEntityNotFoundError: If the AWS resource is not found
            InfrastructureError: For other AWS API errors
        """

    def create_launch_template(self, template: Template, request: Request) -> Dict[str, Any]:
        """
        Create an EC2 launch template or a new version if it already exists.
        Uses ClientToken for idempotency to prevent duplicate versions.
        
        Args:
            template: The template configuration
            request: The associated request
            
        Returns:
            Dict containing launch template ID and version
            
        Raises:
            ValidationError: If the template configuration is invalid
            InfrastructureError: For AWS API errors
        """
        try:
            # Create launch template data
            launch_template_data = self._create_launch_template_data(template, request)
            
            # Get the launch template name using the helper function
            launch_template_name = get_launch_template_name(request.request_id)
            
            # Generate a deterministic client token based on the request ID, template ID, and image ID
            # This ensures idempotency - identical requests will return the same result
            import hashlib
            client_token = hashlib.sha256(
                f"{request.request_id}:{template.template_id}:{template.image_id}".encode()
            ).hexdigest()[:32]  # Truncate to 32 chars to maintain compatibility with services expecting MD5 length
            
            # First try to describe the launch template to see if it exists
            try:
                existing_template = self._retry_with_backoff(
                    self.aws_client.ec2_client.describe_launch_templates,
                    LaunchTemplateNames=[launch_template_name],
                    non_retryable_errors=['InvalidLaunchTemplateName.NotFoundException']
                )
                
                # If we get here, the template exists, so create a new version with ClientToken
                template_id = existing_template['LaunchTemplates'][0]['LaunchTemplateId']
                self._logger.info(f"Launch template {launch_template_name} exists with ID {template_id}. Creating/reusing version.")
                
                response = self._retry_with_backoff(
                    self.aws_client.ec2_client.create_launch_template_version,
                    LaunchTemplateId=template_id,
                    VersionDescription=f"For request {request.request_id}",
                    LaunchTemplateData=launch_template_data,
                    ClientToken=client_token  # Key for idempotency!
                )
                
                version = str(response['LaunchTemplateVersion']['VersionNumber'])
                self._logger.info(f"Using version {version} of launch template {template_id}")
                
                return {
                    'LaunchTemplateId': template_id,
                    'Version': version
                }
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'InvalidLaunchTemplateName.NotFoundException':
                    # Template doesn't exist, create it with ClientToken
                    self._logger.info(f"Launch template {launch_template_name} does not exist. Creating new template.")
                    
                    response = self._retry_with_backoff(
                        self.aws_client.ec2_client.create_launch_template,
                        LaunchTemplateName=launch_template_name,
                        VersionDescription=f"Created for request {request.request_id}",
                        LaunchTemplateData=launch_template_data,
                        ClientToken=client_token,  # Key for idempotency!
                        TagSpecifications=[{
                            'ResourceType': 'launch-template',
                            'Tags': [
                                {'Key': 'Name', 'Value': launch_template_name},
                                {'Key': 'RequestId', 'Value': str(request.request_id)},
                                {'Key': 'TemplateId', 'Value': str(template.template_id)},
                                {'Key': 'CreatedBy', 'Value': 'HostFactory'}
                            ]
                        }]
                    )

                    launch_template = response['LaunchTemplate']
                    self._logger.info(f"Created launch template {launch_template['LaunchTemplateId']}")

                    return {
                        'LaunchTemplateId': launch_template['LaunchTemplateId'],
                        'Version': str(launch_template['LatestVersionNumber'])
                    }
                else:
                    # Some other error
                    raise e

        except ClientError as e:
            error = self._convert_client_error(e)
            self._logger.error(f"Failed to create launch template: {str(error)}")
            raise error
        except Exception as e:
            self._logger.error(f"Unexpected error creating launch template: {str(e)}")
            raise InfrastructureError(f"Failed to create launch template: {str(e)}")

    def _create_launch_template_data(self, template: Template, request: Request) -> Dict[str, Any]:
        """Create launch template data from template configuration."""
        # Template should already contain resolved AMI ID from boundary resolution
        image_id = template.image_id
        if not image_id:
            error_msg = f"Template {template.template_id} has no image_id specified"
            self._logger.error(error_msg)
            raise InfrastructureError(error_msg)
            
        # Log the image_id being used
        self._logger.info(f"Creating launch template with resolved image_id: {image_id}")
        
        # Get instance name using the helper function
        instance_name = get_instance_name(request.request_id)
        
        launch_template_data = {
            'ImageId': image_id,
            'InstanceType': template.vm_type if template.vm_type else list(template.vm_types.keys())[0],
            'TagSpecifications': [{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': instance_name},
                    {'Key': 'RequestId', 'Value': str(request.request_id)},
                    {'Key': 'TemplateId', 'Value': str(template.template_id)},
                    {'Key': 'CreatedBy', 'Value': 'HostFactory'}
                ]
            }]
        }

        # Add template tags if any
        if template.tags:
            instance_tags = [{'Key': k, 'Value': v} for k, v in template.tags.items()]
            launch_template_data['TagSpecifications'][0]['Tags'].extend(instance_tags)

        # Add optional configurations
        if template.subnet_id:
            launch_template_data['NetworkInterfaces'] = [{
                'DeviceIndex': 0,
                'SubnetId': template.subnet_id,
                'AssociatePublicIpAddress': True
            }]

        if template.key_name:
            launch_template_data['KeyName'] = template.key_name

        if template.user_data:
            launch_template_data['UserData'] = template.user_data

        return launch_template_data

    def _retry_with_backoff(self, func: Callable[..., T], *args, 
                           operation_type: str = "standard",
                           non_retryable_errors: List[str] = None, **kwargs) -> T:
        """
        Execute a function with operation-specific retry and circuit breaker strategy.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            operation_type: Type of operation (critical, standard, read_only)
            non_retryable_errors: List of error codes that should not be retried (for compatibility)
            **kwargs: Keyword arguments for the function
            
        Returns:
            The function's return value
            
        Raises:
            CircuitBreakerOpenError: When circuit breaker is open
            The last error encountered after all retries
        """
        # Get operation details
        operation_name = getattr(func, '__name__', 'aws_operation')
        service_name = self._get_service_name()
        
        # Determine retry strategy based on operation type
        strategy_config = self._get_retry_strategy_config(operation_type, service_name)
        
        # Create retry decorator with appropriate strategy
        @retry(**strategy_config)
        def wrapped_operation():
            return func(*args, **kwargs)
        
        try:
            return wrapped_operation()
        except Exception as e:
            # Handle circuit breaker exceptions
            if hasattr(e, '__class__') and 'CircuitBreakerOpenError' in str(type(e)):
                # Log circuit breaker state and re-raise
                self._logger.error(
                    f"Circuit breaker OPEN for {service_name}.{operation_name}",
                    extra={
                        'service': service_name,
                        'operation': operation_name,
                        'operation_type': operation_type
                    }
                )
                raise e
            
            # Convert AWS ClientError to domain exception
            if isinstance(e, ClientError):
                raise self._convert_client_error(e, operation_name)
            
            # Re-raise other exceptions as-is
            raise e
    
    def _get_service_name(self) -> str:
        """Get service name from handler class name."""
        return self.__class__.__name__.replace('Handler', '').lower()
    
    def _get_retry_strategy_config(self, operation_type: str, service_name: str) -> Dict[str, Any]:
        """
        Get retry strategy configuration based on operation type.
        
        Args:
            operation_type: Type of operation (critical, standard, read_only)
            service_name: AWS service name
            
        Returns:
            Dictionary with retry configuration
        """
        # Define critical operations that need circuit breaker
        critical_operations = {
            'create_fleet', 'request_spot_fleet', 'create_auto_scaling_group', 
            'run_instances', 'modify_fleet', 'delete_fleets', 'cancel_spot_fleet_requests',
            'update_auto_scaling_group', 'delete_auto_scaling_group'
        }
        
        if operation_type == "critical":
            # Use circuit breaker for critical operations
            return {
                'strategy': 'circuit_breaker',
                'service': service_name,
                'max_attempts': 3,
                'base_delay': 1.0,
                'failure_threshold': 5,
                'reset_timeout': 60,
                'half_open_timeout': 30
            }
        elif operation_type == "read_only":
            # Use lighter retry for read operations
            return {
                'strategy': 'exponential',
                'service': service_name,
                'max_attempts': 2,
                'base_delay': 0.5,
                'max_delay': 10.0
            }
        else:
            # Standard exponential backoff for regular operations
            return {
                'strategy': 'exponential',
                'service': service_name,
                'max_attempts': 3,
                'base_delay': 1.0,
                'max_delay': 30.0
            }
    
    def _convert_client_error(self, error: ClientError, operation_name: str = "unknown") -> Exception:
        """Convert AWS ClientError to domain exception."""
        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']

        if error_code in ['ValidationError', 'InvalidParameterValue']:
            return AWSValidationError(error_message)
        elif error_code in ['LimitExceeded', 'InstanceLimitExceeded']:
            return QuotaExceededError(error_message)
        elif error_code == 'ResourceInUse':
            return ResourceInUseError(error_message)
        elif error_code in ['UnauthorizedOperation', 'AccessDenied']:
            return AuthorizationError(error_message)
        elif error_code == 'RequestLimitExceeded':
            return RateLimitError(error_message)
        elif error_code in ['ResourceNotFound', 'InvalidInstanceID.NotFound']:
            return AWSEntityNotFoundError(error_message)
        elif error_code in ['RequestTimeout', 'ServiceUnavailable']:
            return NetworkError(error_message)
        else:
            return InfrastructureError(f"AWS Error: {error_code} - {error_message}")

    def _paginate(self, client_method: Callable, result_key: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Paginate through AWS API results.
        
        Args:
            client_method: The AWS client method to call
            result_key: The key in the response containing the results
            **kwargs: Arguments to pass to the client method
            
        Returns:
            Combined results from all pages
        """
        from src.providers.aws.infrastructure.utils import paginate
        return paginate(client_method, result_key, **kwargs)
        
    def _get_instance_details(self, instance_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get detailed information about EC2 instances.
        
        Args:
            instance_ids: List of instance IDs to describe
            
        Returns:
            List of instance details
            
        Raises:
            AWSEntityNotFoundError: If any instance is not found
            InfrastructureError: For other AWS API errors
        """
        try:
            # Use AWS client's describe_instances with adaptive batch sizing
            response = self.aws_client.describe_instances(instance_ids=instance_ids)
            
            instances = []
            for reservation in response.get('Reservations', []):
                for instance in reservation['Instances']:
                    instances.append({
                        'InstanceId': instance['InstanceId'],
                        'State': instance['State']['Name'],
                        'PrivateIpAddress': instance.get('PrivateIpAddress'),
                        'PublicIpAddress': instance.get('PublicIpAddress'),
                        'LaunchTime': instance['LaunchTime'].isoformat(),
                        'Tags': instance.get('Tags', []),
                        'InstanceType': instance['InstanceType']
                    })

            return instances

        except ClientError as e:
            error = self._convert_client_error(e)
            self._logger.error(f"Failed to get instance details: {str(error)}")
            raise error
        except Exception as e:
            self._logger.error(f"Unexpected error getting instance details: {str(e)}")
            raise InfrastructureError(f"Failed to get instance details: {str(e)}")

    def _validate_prerequisites(self, template: Template) -> None:
        """
        Validate template prerequisites.
        
        Args:
            template: The template to validate
            
        Raises:
            ValidationError: If prerequisites are not met
        """
        errors = {}

        # Validate image ID
        if not template.image_id:
            errors['imageId'] = "Image ID is required"
        # Skip AMI ID format validation as it might have been updated by AWSTemplateAdapter
        # The actual AWS API call will validate the AMI ID format

        # Validate instance type(s)
        if not (template.vm_type or template.vm_types):
            errors['instanceType'] = "Either vm_type or vm_types must be specified"
        if template.vm_type and template.vm_types:
            errors['instanceType'] = "Cannot specify both vm_type and vm_types"

        # Validate subnet(s)
        if not (template.subnet_id or template.subnet_ids):
            errors['subnet'] = "Either subnet_id or subnet_ids must be specified"
        if template.subnet_id and template.subnet_ids:
            errors['subnet'] = "Cannot specify both subnet_id and subnet_ids"

        # Validate security groups
        if not template.security_group_ids:
            errors['securityGroups'] = "At least one security group is required"

        if errors:
            raise AWSValidationError("Template validation failed", errors)
