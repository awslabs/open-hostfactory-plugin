"""Caching AMI resolver with fallback capabilities."""
from src.config import AMIResolutionConfig
from src.providers.aws.infrastructure.aws_client import AWSClient
from src.providers.aws.infrastructure.template.ami_cache import RuntimeAMICache
from src.domain.base.ports import LoggingPort, ConfigurationPort
from src.domain.base.exceptions import InfrastructureError
from src.domain.base.dependency_injection import injectable


@injectable
class CachingAMIResolver:
    """
    AMI resolver with runtime caching and graceful fallback.
    
    Features:
    - Resolves SSM parameters to actual AMI IDs
    - Runtime caching to avoid duplicate AWS calls
    - Graceful fallback when AWS is unavailable
    - Configurable behavior via AMIResolutionConfig
    """
    
    def __init__(self, aws_client: AWSClient, config: ConfigurationPort, logger: LoggingPort):
        """
        Initialize caching AMI resolver.
        
        Args:
            aws_client: AWS client for SSM operations
            config: Configuration port for accessing configuration
            logger: Logger for logging messages
        """
        self._aws_client = aws_client
        self._logger = logger
        
        # Get AMI resolution configuration
        try:
            self._ami_config = config.get_typed(AMIResolutionConfig)
        except Exception as e:
            self._logger.warning(f"Failed to get AMI resolution config: {str(e)}")
            # Use default configuration
            self._ami_config = AMIResolutionConfig(
                enabled=True,
                fallback_on_failure=True,
                cache_enabled=True
            )
        
        self._cache = RuntimeAMICache()
        
        self._logger.debug(f"Initialized CachingAMIResolver with config: "
                          f"enabled={self._ami_config.enabled}, "
                          f"fallback_on_failure={self._ami_config.fallback_on_failure}, "
                          f"cache_enabled={self._ami_config.cache_enabled}")
    
    def resolve_with_fallback(self, ami_id_or_parameter: str) -> str:
        """
        Resolve AMI ID with caching and fallback.
        
        Args:
            ami_id_or_parameter: AMI ID, SSM parameter, or alias
            
        Returns:
            Resolved AMI ID or original parameter if resolution fails and fallback enabled
            
        Raises:
            InfrastructureError: If resolution fails and fallback disabled
        """
        # Skip resolution if disabled
        if not self._ami_config.enabled:
            self._logger.debug(f"AMI resolution disabled, returning original: {ami_id_or_parameter}")
            return ami_id_or_parameter
        
        # Return as-is if already an AMI ID
        if ami_id_or_parameter.startswith('ami-'):
            self._logger.debug(f"Already AMI ID, returning: {ami_id_or_parameter}")
            return ami_id_or_parameter
        
        # Skip if not an SSM parameter
        if not ami_id_or_parameter.startswith('/aws/service/'):
            self._logger.debug(f"Not SSM parameter, returning original: {ami_id_or_parameter}")
            return ami_id_or_parameter
        
        # Check cache first if enabled
        if self._ami_config.cache_enabled:
            # Return cached result if available
            cached_ami = self._cache.get(ami_id_or_parameter)
            if cached_ami:
                return cached_ami
            
            # Skip if previously failed
            if self._cache.is_failed(ami_id_or_parameter):
                self._logger.debug(f"Previously failed parameter, returning original: {ami_id_or_parameter}")
                return ami_id_or_parameter
        
        # Attempt resolution
        self._logger.info(f"Resolving SSM parameter: {ami_id_or_parameter}")
        try:
            ami_id = self._resolve_ssm_parameter(ami_id_or_parameter)
            
            # Cache successful resolution
            if self._ami_config.cache_enabled:
                self._cache.set(ami_id_or_parameter, ami_id)
            
            self._logger.info(f"Successfully resolved {ami_id_or_parameter} to {ami_id}")
            return ami_id
            
        except Exception as e:
            self._logger.warning(f"Failed to resolve SSM parameter {ami_id_or_parameter}: {str(e)}")
            
            # Mark as failed in cache
            if self._ami_config.cache_enabled:
                self._cache.mark_failed(ami_id_or_parameter)
            
            # Handle fallback
            if self._ami_config.fallback_on_failure:
                self._logger.info(f"Fallback enabled, returning original parameter: {ami_id_or_parameter}")
                return ami_id_or_parameter
            else:
                self._logger.error(f"Fallback disabled, raising error for {ami_id_or_parameter}")
                raise InfrastructureError(f"Failed to resolve AMI parameter {ami_id_or_parameter}: {str(e)}")
    
    def _resolve_ssm_parameter(self, parameter_path: str) -> str:
        """
        Resolve SSM parameter to AMI ID.
        
        Args:
            parameter_path: SSM parameter path
            
        Returns:
            Resolved AMI ID
            
        Raises:
            Exception: If resolution fails
        """
        try:
            # Use the AWS client's SSM client to get the parameter value
            response = self._aws_client.ssm_client.get_parameter(Name=parameter_path)
            
            if 'Parameter' not in response or 'Value' not in response['Parameter']:
                raise ValueError(f"Invalid SSM parameter response for {parameter_path}")
            
            ami_id = response['Parameter']['Value']
            
            # Validate that we got a valid AMI ID
            if not ami_id.startswith('ami-'):
                raise ValueError(f"SSM parameter {parameter_path} resolved to invalid AMI ID: {ami_id}")
            
            return ami_id
            
        except Exception as e:
            # Re-raise with more context
            raise Exception(f"SSM parameter resolution failed: {str(e)}")
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return self._cache.get_stats()
    
    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._logger.info("AMI resolution cache cleared")
