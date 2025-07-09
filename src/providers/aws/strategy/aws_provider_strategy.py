"""AWS Provider Strategy - Strategy pattern implementation for AWS provider.

This module implements the ProviderStrategy interface for AWS cloud provider,
enabling AWS operations to be executed through the strategy pattern while
maintaining all existing AWS functionality and adding new capabilities.
"""

from typing import Dict, Any, List, Optional
import time

from src.domain.base.ports import LoggingPort
from src.domain.base.dependency_injection import injectable

# Import strategy pattern interfaces
from src.providers.base.strategy import (
    ProviderStrategy,
    ProviderOperation,
    ProviderResult,
    ProviderCapabilities,
    ProviderHealthStatus,
    ProviderOperationType
)

# Import AWS-specific components
from src.providers.aws.configuration.config import AWSProviderConfig
from src.providers.aws.managers.aws_resource_manager import AWSResourceManager
from src.providers.aws.managers.aws_instance_manager import AWSInstanceManager
from src.providers.aws.infrastructure.aws_client import AWSClient

@injectable
class AWSProviderStrategy(ProviderStrategy):
    """
    AWS implementation of the ProviderStrategy interface.
    
    This class adapts the existing AWS provider functionality to work with
    the strategy pattern, enabling runtime provider switching and composition
    while preserving all AWS-specific capabilities and optimizations.
    
    Features:
    - Full AWS provider functionality through strategy interface
    - Health monitoring and capability reporting
    - Performance metrics and error handling
    - Resource and instance management integration
    - AWS-specific optimizations and features
    """
    
    def __init__(self, config: AWSProviderConfig, logger: LoggingPort):
        """
        Initialize AWS provider strategy.
        
        Args:
            config: AWS-specific configuration
            logger: Logger for logging messages
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(config, AWSProviderConfig):
            raise ValueError("AWSProviderStrategy requires AWSProviderConfig")
        
        super().__init__(config)
        self._logger = logger
        self._aws_config = config
        self._aws_client: Optional[AWSClient] = None
        self._resource_manager: Optional[AWSResourceManager] = None
        self._instance_manager: Optional[AWSInstanceManager] = None
    
    @property
    def provider_type(self) -> str:
        """Get the provider type identifier."""
        return "aws"
    
    @property
    def aws_client(self) -> Optional[AWSClient]:
        """Get the AWS client instance."""
        return self._aws_client
    
    @property
    def resource_manager(self) -> Optional[AWSResourceManager]:
        """Get the AWS resource manager."""
        return self._resource_manager
    
    @property
    def instance_manager(self) -> Optional[AWSInstanceManager]:
        """Get the AWS instance manager."""
        return self._instance_manager
    
    
    def initialize(self) -> bool:
        """
        Initialize the AWS provider strategy.
        
        Sets up AWS client, resource manager, and instance manager
        with proper configuration and error handling.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self._logger.info(f"Initializing AWS provider strategy for region: {self._aws_config.region}")
            
            # Create a configuration port that provides the instance-specific AWS config
            class AWSInstanceConfigPort:
                """Configuration port that provides instance-specific AWS configuration."""
                def __init__(self, aws_config: AWSProviderConfig):
                    self._aws_config = aws_config
                
                def get_typed(self, config_type):
                    """Return the instance-specific AWS config."""
                    if config_type == AWSProviderConfig:
                        return self._aws_config
                    return None
            
            config_port = AWSInstanceConfigPort(self._aws_config)
            
            self._aws_client = AWSClient(
                config=config_port,
                logger=self._logger
            )
            
            # Initialize managers
            self._resource_manager = AWSResourceManager(
                aws_client=self._aws_client,
                config=self._aws_config,
                logger=self._logger
            )
            
            self._instance_manager = AWSInstanceManager(
                aws_client=self._aws_client,
                config=self._aws_config,
                logger=self._logger
            )
            
            # Test connectivity
            health_check = self.check_health()
            if not health_check.is_healthy:
                self._logger.error(f"AWS connectivity check failed: {health_check.status_message}")
                return False
            
            self._initialized = True
            self._logger.info("AWS provider strategy initialized successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to initialize AWS provider strategy: {e}")
            return False
    
    
    def execute_operation(self, operation: ProviderOperation) -> ProviderResult:
        """
        Execute a provider operation using AWS services.
        
        Args:
            operation: The operation to execute
            
        Returns:
            Result of the operation execution
        """
        if not self._initialized:
            return ProviderResult.error_result(
                "AWS provider strategy not initialized",
                "NOT_INITIALIZED"
            )
        
        start_time = time.time()
        
        # Check for dry-run context
        is_dry_run = bool(operation.context and operation.context.get('dry_run', False))
        
        try:
            # Import dry-run context here to avoid circular imports
            from src.providers.aws.infrastructure.dry_run_adapter import aws_dry_run_context
            
            # Execute operation within appropriate context
            if is_dry_run:
                with aws_dry_run_context():
                    result = self._execute_operation_internal(operation)
            else:
                result = self._execute_operation_internal(operation)
            
            # Add execution metadata
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Ensure metadata is a mutable dict
            if result.metadata is None:
                result.metadata = {}
            
            # Update metadata with execution info
            result.metadata.update({
                "execution_time_ms": execution_time_ms, 
                "provider": "aws", 
                "dry_run": is_dry_run
            })
            
            return result
            
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            self._logger.error(f"AWS operation failed: {e}")
            return ProviderResult.error_result(
                f"AWS operation failed: {str(e)}",
                "OPERATION_FAILED",
                {"execution_time_ms": execution_time_ms, "provider": "aws", "dry_run": is_dry_run}
            )
    
    def _execute_operation_internal(self, operation: ProviderOperation) -> ProviderResult:
        """
        Internal method to execute operations - separated for dry-run context wrapping.
        
        Args:
            operation: The operation to execute
            
        Returns:
            Result of the operation execution
        """
        # Route operation to appropriate handler
        if operation.operation_type == ProviderOperationType.CREATE_INSTANCES:
            return self._handle_create_instances(operation)
        elif operation.operation_type == ProviderOperationType.TERMINATE_INSTANCES:
            return self._handle_terminate_instances(operation)
        elif operation.operation_type == ProviderOperationType.GET_INSTANCE_STATUS:
            return self._handle_get_instance_status(operation)
        elif operation.operation_type == ProviderOperationType.VALIDATE_TEMPLATE:
            return self._handle_validate_template(operation)
        elif operation.operation_type == ProviderOperationType.GET_AVAILABLE_TEMPLATES:
            return self._handle_get_available_templates(operation)
        elif operation.operation_type == ProviderOperationType.HEALTH_CHECK:
            return self._handle_health_check(operation)
        else:
            return ProviderResult.error_result(
                f"Unsupported operation: {operation.operation_type}",
                "UNSUPPORTED_OPERATION"
            )
    
    def _handle_create_instances(self, operation: ProviderOperation) -> ProviderResult:
        """Handle instance creation operation."""
        try:
            template_config = operation.parameters.get('template_config', {})
            count = operation.parameters.get('count', 1)
            
            if not template_config:
                return ProviderResult.error_result(
                    "Template configuration is required for instance creation",
                    "MISSING_TEMPLATE_CONFIG"
                )
            
            # Use instance manager to create instances
            instance_ids = self._instance_manager.create_instances(template_config, count)
            
            return ProviderResult.success_result(
                {"instance_ids": instance_ids, "count": len(instance_ids)},
                {"operation": "create_instances", "template_config": template_config}
            )
            
        except Exception as e:
            return ProviderResult.error_result(
                f"Failed to create instances: {str(e)}",
                "CREATE_INSTANCES_ERROR"
            )
    
    def _handle_terminate_instances(self, operation: ProviderOperation) -> ProviderResult:
        """Handle instance termination operation."""
        try:
            instance_ids = operation.parameters.get('instance_ids', [])
            
            if not instance_ids:
                return ProviderResult.error_result(
                    "Instance IDs are required for termination",
                    "MISSING_INSTANCE_IDS"
                )
            
            # Use instance manager to terminate instances
            success = self._instance_manager.terminate_instances(instance_ids)
            
            return ProviderResult.success_result(
                {"success": success, "terminated_count": len(instance_ids)},
                {"operation": "terminate_instances", "instance_ids": instance_ids}
            )
            
        except Exception as e:
            return ProviderResult.error_result(
                f"Failed to terminate instances: {str(e)}",
                "TERMINATE_INSTANCES_ERROR"
            )
    
    def _handle_get_instance_status(self, operation: ProviderOperation) -> ProviderResult:
        """Handle instance status query operation."""
        try:
            instance_ids = operation.parameters.get('instance_ids', [])
            
            if not instance_ids:
                return ProviderResult.error_result(
                    "Instance IDs are required for status query",
                    "MISSING_INSTANCE_IDS"
                )
            
            # Use instance manager to get status
            status_map = self._instance_manager.get_instance_status(instance_ids)
            
            return ProviderResult.success_result(
                {"instance_status": status_map, "queried_count": len(instance_ids)},
                {"operation": "get_instance_status", "instance_ids": instance_ids}
            )
            
        except Exception as e:
            return ProviderResult.error_result(
                f"Failed to get instance status: {str(e)}",
                "GET_INSTANCE_STATUS_ERROR"
            )
    
    def _handle_validate_template(self, operation: ProviderOperation) -> ProviderResult:
        """Handle template validation operation."""
        try:
            template_config = operation.parameters.get('template_config', {})
            
            if not template_config:
                return ProviderResult.error_result(
                    "Template configuration is required for validation",
                    "MISSING_TEMPLATE_CONFIG"
                )
            
            # Perform AWS-specific template validation
            validation_result = self._validate_aws_template(template_config)
            
            return ProviderResult.success_result(
                validation_result,
                {"operation": "validate_template", "template_config": template_config}
            )
            
        except Exception as e:
            return ProviderResult.error_result(
                f"Failed to validate template: {str(e)}",
                "VALIDATE_TEMPLATE_ERROR"
            )
    
    def _handle_get_available_templates(self, operation: ProviderOperation) -> ProviderResult:
        """Handle available templates query operation."""
        try:
            # Get available templates from AWS
            templates = self._get_aws_templates()
            
            return ProviderResult.success_result(
                {"templates": templates, "count": len(templates)},
                {"operation": "get_available_templates"}
            )
            
        except Exception as e:
            return ProviderResult.error_result(
                f"Failed to get available templates: {str(e)}",
                "GET_TEMPLATES_ERROR"
            )
    
    def _handle_health_check(self, operation: ProviderOperation) -> ProviderResult:
        """Handle health check operation."""
        health_status = self.check_health()
        
        return ProviderResult.success_result(
            {
                "is_healthy": health_status.is_healthy,
                "status_message": health_status.status_message,
                "response_time_ms": health_status.response_time_ms
            },
            {"operation": "health_check"}
        )
    
    def get_capabilities(self) -> ProviderCapabilities:
        """
        Get AWS provider capabilities and features.
        
        Returns:
            Comprehensive capabilities information for AWS provider
        """
        return ProviderCapabilities(
            provider_type="aws",
            supported_operations=[
                ProviderOperationType.CREATE_INSTANCES,
                ProviderOperationType.TERMINATE_INSTANCES,
                ProviderOperationType.GET_INSTANCE_STATUS,
                ProviderOperationType.VALIDATE_TEMPLATE,
                ProviderOperationType.GET_AVAILABLE_TEMPLATES,
                ProviderOperationType.HEALTH_CHECK
            ],
            features={
                "instance_management": True,
                "spot_instances": True,
                "fleet_management": True,
                "auto_scaling": True,
                "load_balancing": True,
                "vpc_support": True,
                "security_groups": True,
                "key_pairs": True,
                "tags_support": True,
                "monitoring": True,
                "regions": ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
                "instance_types": ["t3.micro", "t3.small", "t3.medium", "m5.large", "c5.large"],
                "max_instances_per_request": 1000,
                "supports_windows": True,
                "supports_linux": True
            },
            limitations={
                "max_concurrent_requests": 100,
                "rate_limit_per_second": 10,
                "max_instance_lifetime_hours": 8760,  # 1 year
                "requires_vpc": False,
                "requires_key_pair": False
            },
            performance_metrics={
                "typical_create_time_seconds": 60,
                "typical_terminate_time_seconds": 30,
                "health_check_timeout_seconds": 10
            }
        )
    
    def check_health(self) -> ProviderHealthStatus:
        """
        Check the health status of AWS provider.
        
        Performs connectivity and service availability checks.
        
        Returns:
            Current health status of the AWS provider
        """
        start_time = time.time()
        
        try:
            if not self._aws_client:
                return ProviderHealthStatus.unhealthy(
                    "AWS client not initialized",
                    {"error": "client_not_initialized"}
                )
            
            # Perform basic AWS connectivity check
            # This is a lightweight operation to verify AWS access
            try:
                # Simple STS call to verify credentials and connectivity
                response = self._aws_client.sts_client.get_caller_identity()
                account_id = response.get('Account', 'unknown')
                
                response_time_ms = (time.time() - start_time) * 1000
                
                return ProviderHealthStatus.healthy(
                    f"AWS provider healthy - Account: {account_id}, Region: {self._aws_config.region}",
                    response_time_ms
                )
                
            except Exception as e:
                response_time_ms = (time.time() - start_time) * 1000
                return ProviderHealthStatus.unhealthy(
                    f"AWS connectivity check failed: {str(e)}",
                    {
                        "error": str(e),
                        "region": self._aws_config.region,
                        "response_time_ms": response_time_ms
                    }
                )
                
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return ProviderHealthStatus.unhealthy(
                f"Health check error: {str(e)}",
                {
                    "error": str(e),
                    "response_time_ms": response_time_ms
                }
            )
    
    def _validate_aws_template(self, template_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate AWS-specific template configuration."""
        validation_errors = []
        validation_warnings = []
        
        # Required fields validation
        required_fields = ['image_id', 'instance_type']
        for field in required_fields:
            if field not in template_config:
                validation_errors.append(f"Missing required field: {field}")
        
        # AWS-specific validations
        if 'image_id' in template_config:
            image_id = template_config['image_id']
            if not image_id.startswith('ami-'):
                validation_errors.append(f"Invalid AMI ID format: {image_id}")
        
        if 'instance_type' in template_config:
            instance_type = template_config['instance_type']
            # Basic instance type validation
            if not any(instance_type.startswith(prefix) for prefix in ['t3.', 't2.', 'm5.', 'c5.', 'r5.']):
                validation_warnings.append(f"Uncommon instance type: {instance_type}")
        
        return {
            "valid": len(validation_errors) == 0,
            "errors": validation_errors,
            "warnings": validation_warnings,
            "validated_fields": list(template_config.keys())
        }
    
    def _get_aws_templates(self) -> List[Dict[str, Any]]:
        """Get available AWS templates."""
        # This would typically query AWS for available templates/AMIs
        # For now, return a basic set of common templates
        return [
            {
                "template_id": "aws-linux-basic",
                "name": "Amazon Linux 2 Basic",
                "image_id": "ami-0abcdef1234567890",
                "instance_type": "t3.micro",
                "description": "Basic Amazon Linux 2 instance"
            },
            {
                "template_id": "aws-ubuntu-basic",
                "name": "Ubuntu 20.04 Basic",
                "image_id": "ami-0fedcba0987654321",
                "instance_type": "t3.small",
                "description": "Basic Ubuntu 20.04 instance"
            }
        ]
    
    def cleanup(self) -> None:
        """Clean up AWS provider resources."""
        try:
            if self._aws_client:
                self._aws_client.cleanup()
                self._logger.debug("AWS client cleaned up")
            
            self._aws_client = None
            self._resource_manager = None
            self._instance_manager = None
            self._initialized = False
            
        except Exception as e:
            self._logger.warning(f"Error during AWS provider cleanup: {e}")
    
    def __str__(self) -> str:
        """String representation for debugging."""
        return f"AWSProviderStrategy(region={self._aws_config.region}, initialized={self._initialized})"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"AWSProviderStrategy("
            f"region={self._aws_config.region}, "
            f"profile={self._aws_config.profile}, "
            f"initialized={self._initialized}"
            f")"
        )
