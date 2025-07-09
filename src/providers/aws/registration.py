"""AWS Provider Registration - Register AWS provider with the provider registry."""

from typing import Any, Dict, TYPE_CHECKING

# Use TYPE_CHECKING to avoid direct infrastructure import
if TYPE_CHECKING:
    from src.infrastructure.registry.provider_registry import ProviderRegistry
    from src.domain.base.ports import LoggingPort


def create_aws_strategy(provider_config: Any) -> Any:
    """
    Create AWS provider strategy from configuration.
    
    Args:
        provider_config: Provider instance configuration
        
    Returns:
        Configured AWSProviderStrategy instance
    """
def create_aws_strategy(provider_config) -> 'AWSProviderStrategy':
    """Create AWS strategy from configuration."""
    from src.providers.aws.strategy.aws_provider_strategy import AWSProviderStrategy
    from src.providers.aws.configuration.config import AWSProviderConfig
    from src.infrastructure.adapters.logging_adapter import LoggingAdapter
    
    try:
        # Handle both ProviderInstanceConfig object and raw dict
        if hasattr(provider_config, 'config'):
            # ProviderInstanceConfig object
            config_data = provider_config.config
        else:
            # Raw config dict
            config_data = provider_config
            
        # Create AWS configuration
        aws_config = AWSProviderConfig(**config_data)
        
        # Create a simple logger adapter for now
        # The DI container will inject the proper logger later if needed
        logger = LoggingAdapter()
        
        # Create AWS provider strategy
        strategy = AWSProviderStrategy(aws_config, logger)
        
        # Set provider name for identification
        if hasattr(strategy, 'name'):
            strategy.name = provider_config.name
        
        return strategy
        
    except ImportError as e:
        raise ImportError(f"AWS provider strategy not available: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to create AWS strategy: {str(e)}") from e


def create_aws_config(data: Dict[str, Any]) -> Any:
    """
    Create AWS configuration from data dictionary.
    
    Args:
        data: Configuration data dictionary
        
    Returns:
        Configured AWSProviderConfig instance
    """
    try:
        from src.providers.aws.configuration.config import AWSProviderConfig
        return AWSProviderConfig(**data)
    except ImportError as e:
        raise ImportError(f"AWS configuration not available: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to create AWS config: {str(e)}") from e


def create_aws_resolver() -> Any:
    """
    Create AWS template resolver.
    
    Returns:
        AWS template resolver instance
    """
    try:
        from src.providers.aws.infrastructure.template.caching_ami_resolver import CachingAMIResolver
        return CachingAMIResolver()
    except ImportError:
        # AWS resolver not available, return None
        return None
    except Exception as e:
        # Re-raise with context - let caller handle logging
        raise RuntimeError(f"Failed to create AWS resolver: {str(e)}") from e


def create_aws_validator() -> Any:
    """
    Create AWS template validator.
    
    Returns:
        AWS template validator instance
    """
    try:
        # AWS doesn't have a specific validator yet, return None
        return None
    except Exception as e:
        # Re-raise with context - let caller handle logging
        raise RuntimeError(f"Failed to create AWS validator: {str(e)}") from e


def register_aws_provider(registry: 'ProviderRegistry' = None, logger: 'LoggingPort' = None, instance_name: str = None) -> None:
    """Register AWS provider with the provider registry.
    
    Args:
        registry: Provider registry instance (optional)
        logger: Logger port for logging (optional)
        instance_name: Optional instance name for multi-instance support
    """
    if registry is None:
        # Import here to avoid circular dependencies
        from src.infrastructure.registry.provider_registry import get_provider_registry
        registry = get_provider_registry()
    
    try:
        if instance_name:
            # Register as named instance
            registry.register_provider_instance(
                provider_type="aws",
                instance_name=instance_name,
                strategy_factory=create_aws_strategy,
                config_factory=create_aws_config,
                resolver_factory=create_aws_resolver,
                validator_factory=create_aws_validator
            )
        else:
            # Register as provider type (backward compatibility)
            registry.register_provider(
                provider_type="aws",
                strategy_factory=create_aws_strategy,
                config_factory=create_aws_config,
                resolver_factory=create_aws_resolver,
                validator_factory=create_aws_validator
            )
        
        # Register AWS template store
        # _register_aws_template_store(logger)
        
        # Register AWS template adapter (following adapter/port pattern)
        # _register_aws_template_adapter(logger)
        
        if logger:
            logger.info("AWS provider registered successfully")
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to register AWS provider: {str(e)}")
        raise


def _register_aws_template_store(logger: 'LoggingPort' = None) -> None:
    """Register AWS SSM template store with the provider template store registry."""
    try:
        from src.infrastructure.template import register_provider_template_store_factory
        from .infrastructure.template.ssm_template_store import create_aws_ssm_template_store
        from .infrastructure.aws_client import AWSClient
        from src.infrastructure.di.container import get_container
        
        def aws_template_store_factory():
            """Factory function to create AWS SSM template store."""
            try:
                container = get_container()
                aws_client = container.get(AWSClient)
                return create_aws_ssm_template_store(aws_client)
            except Exception as e:
                if logger:
                    logger.warning(f"Failed to create AWS template store: {e}")
                return None
        
        # Register the factory with the provider template store registry
        register_provider_template_store_factory("aws", aws_template_store_factory)
        
        if logger:
            logger.info("AWS template store registered successfully")
            
    except Exception as e:
        if logger:
            logger.warning(f"Failed to register AWS template store: {e}")
        # Don't raise - template store is optional


def _register_aws_template_adapter(logger: 'LoggingPort' = None) -> None:
    """Register AWS template adapter with the DI container."""
    try:
        from src.infrastructure.di.container import get_container
        from .infrastructure.adapters.template_adapter import AWSTemplateAdapter, create_aws_template_adapter
        from src.domain.base.ports.template_adapter_port import TemplateAdapterPort
        
        container = get_container()
        
        # Register AWS template adapter factory
        def aws_template_adapter_factory(container_instance):
            """Factory function to create AWS template adapter."""
            from src.providers.aws.infrastructure.aws_client import AWSClient
            from src.domain.base.ports import LoggingPort, ConfigurationPort
            
            aws_client = container_instance.get(AWSClient)
            logger_port = container_instance.get(LoggingPort)
            config_port = container_instance.get(ConfigurationPort)
            
            return create_aws_template_adapter(aws_client, logger_port, config_port)
        
        # Register the adapter with DI container
        container.register_singleton(AWSTemplateAdapter, aws_template_adapter_factory)
        container.register_singleton(TemplateAdapterPort, aws_template_adapter_factory)
        
        if logger:
            logger.info("AWS template adapter registered successfully")
        
    except Exception as e:
        if logger:
            logger.warning(f"Failed to register AWS template adapter: {e}")


def register_aws_provider_with_di(provider_instance, container) -> bool:
    """Register AWS provider instance using DI container context."""
    from src.domain.base.ports import LoggingPort
    
    logger = container.get(LoggingPort)
    
    try:
        logger.info(f"Registering AWS provider instance: {provider_instance.name}")
        
        # Create AWS provider configuration
        aws_config = create_aws_config(provider_instance.config)
        
        # Register AWS components with DI container
        _register_aws_components_with_di(container, aws_config, provider_instance.name)
        
        # Register provider strategy with registry
        from src.infrastructure.registry.provider_registry import get_provider_registry
        registry = get_provider_registry()
        
        # Create provider strategy factory using DI container
        def aws_strategy_factory():
            return _create_aws_strategy_with_di(container, aws_config, provider_instance.name)
        
        # First register the AWS provider type if not already registered
        try:
            registry.register_provider(
                provider_type='aws',
                strategy_factory=aws_strategy_factory,
                config_factory=lambda: aws_config
            )
            logger.info("AWS provider type registered")
        except ValueError as e:
            if "already registered" in str(e):
                logger.debug("AWS provider type already registered")
            else:
                raise
        
        # Then register the specific provider instance
        registry.register_provider_instance(
            provider_type='aws',
            instance_name=provider_instance.name,
            strategy_factory=aws_strategy_factory,
            config_factory=lambda: aws_config
        )
        
        logger.info(f"Successfully registered AWS provider instance: {provider_instance.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to register AWS provider instance '{provider_instance.name}': {str(e)}")
        return False


def _register_aws_components_with_di(container, aws_config, instance_name: str) -> None:
    """Register AWS components with DI container for specific instance."""
    from src.domain.base.ports import LoggingPort, ConfigurationPort
    from src.providers.aws.infrastructure.aws_client import AWSClient
    
    # Register AWS client for this instance
    def aws_client_factory(container_instance):
        config_port = container_instance.get(ConfigurationPort)
        logger_port = container_instance.get(LoggingPort)
        return AWSClient(config=config_port, logger=logger_port)
    
    # Register with instance-specific key
    container.register_factory(f"AWSClient_{instance_name}", aws_client_factory)


def _create_aws_strategy_with_di(container, aws_config, instance_name: str):
    """Create AWS strategy using DI container."""
    from src.domain.base.ports import LoggingPort
    
    logger = container.get(LoggingPort)
    
    # Get AWS client for this instance
    aws_client = container.get(f"AWSClient_{instance_name}")
    
    # Create and return AWS strategy
    from src.providers.aws.strategy import AWSProviderStrategy
    return AWSProviderStrategy(
        aws_client=aws_client,
        config=aws_config,
        logger=logger
    )
