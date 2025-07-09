"""Provider service registrations for dependency injection."""
from typing import Optional, Dict, Any

from src.infrastructure.di.container import DIContainer
from src.config.manager import get_config_manager, ConfigurationManager
from src.domain.base.ports import LoggingPort, ConfigurationPort
from src.infrastructure.logging.logger import get_logger
from src.providers.base.strategy import ProviderContext
from src.infrastructure.factories.provider_strategy_factory import ProviderStrategyFactory


def register_provider_services(container: DIContainer) -> None:
    """Register provider-specific services."""
    
    # Register provider strategy factory
    container.register_factory(ProviderStrategyFactory, create_provider_strategy_factory)
    
    # Register ProviderContext with configuration-driven factory
    container.register_factory(ProviderContext, create_configured_provider_context)
    
    # Register SelectorFactory (keep existing)
    from src.providers.base.strategy import SelectorFactory
    container.register_singleton(
        SelectorFactory,
        lambda c: SelectorFactory()
    )
    
    # Register provider-specific services conditionally
    _register_provider_specific_services(container)


# Global flag to prevent duplicate provider registration
_providers_registered = False

def _register_providers() -> None:
    """Register providers based on configuration."""
    global _providers_registered
    
    if _providers_registered:
        return
    
    logger = get_logger(__name__)
    
    try:
        # Get configuration manager
        from src.config.manager import get_config_manager
        config_manager = get_config_manager()
        
        # Get provider configuration
        provider_config = config_manager.get_provider_config()
        
        if not provider_config:
            logger.warning("No provider configuration found - no providers will be registered")
            return
        
        # Validate configuration
        if not _validate_provider_config(provider_config):
            logger.error("Provider configuration validation failed - no providers will be registered")
            return
        
        # Get active providers from configuration
        active_providers = provider_config.get_active_providers()
        
        if not active_providers:
            logger.warning("No active providers found in configuration")
            return
        
        logger.info(f"Found {len(active_providers)} active provider(s) in configuration")
        
        # Register each active provider
        registered_count = 0
        for provider_instance in active_providers:
            if provider_instance.enabled:
                if _register_provider_instance(provider_instance):
                    registered_count += 1
            else:
                logger.info(f"Provider instance '{provider_instance.name}' is disabled - skipping")
        
        logger.info(f"Successfully registered {registered_count} provider instance(s)")
        _providers_registered = True
                
    except Exception as e:
        logger.error(f"Failed to register providers from configuration: {str(e)}")
        logger.info("No providers registered due to configuration errors")


def _register_providers_with_di_context(container: DIContainer) -> None:
    """Register providers with full DI container context available."""
    global _providers_registered
    
    if _providers_registered:
        return
    
    _providers_registered = True
    
    logger = container.get(LoggingPort)
    
    try:
        # Get configuration manager from DI container
        config_manager = container.get(ConfigurationManager)
        
        # Get provider configuration
        provider_config = config_manager.get_provider_config()
        
        if not provider_config:
            logger.warning("No provider configuration found - no providers will be registered")
            return
        
        # Validate configuration
        if not _validate_provider_config(provider_config):
            logger.error("Provider configuration validation failed - no providers will be registered")
            return
        
        # Get active providers from configuration
        active_providers = provider_config.get_active_providers()
        
        if not active_providers:
            logger.warning("No active providers found in configuration")
            return
        
        logger.info(f"Found {len(active_providers)} active provider(s) in configuration")
        
        # Register each active provider with DI context
        registered_count = 0
        for provider_instance in active_providers:
            if provider_instance.enabled:
                if _register_provider_instance_with_di(provider_instance, container):
                    registered_count += 1
            else:
                logger.info(f"Provider instance '{provider_instance.name}' is disabled - skipping")
        
        logger.info(f"Successfully registered {registered_count} provider instance(s)")
        _providers_registered = True
                
    except Exception as e:
        logger.error(f"Failed to register providers from configuration: {str(e)}")
        logger.info("No providers registered due to configuration errors")


def _register_provider_instance_with_di(provider_instance, container: DIContainer) -> bool:
    """Register a single provider instance using DI container context."""
    logger = container.get(LoggingPort)
    
    try:
        provider_type = provider_instance.type.lower()
        
        if provider_type == 'aws':
            return _register_aws_provider_with_di(provider_instance, container)
        else:
            logger.warning(f"Unknown provider type: {provider_type}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to register provider instance '{provider_instance.name}': {str(e)}")
        return False


def _register_aws_provider_with_di(provider_instance, container: DIContainer) -> bool:
    """Register AWS provider instance using DI container context."""
    logger = container.get(LoggingPort)
    
    try:
        from src.providers.aws.registration import register_aws_provider_with_di
        return register_aws_provider_with_di(provider_instance, container)
    except Exception as e:
        logger.error(f"Failed to register AWS provider '{provider_instance.name}': {str(e)}")
        return False


def _validate_provider_config(provider_config) -> bool:
    """Validate provider configuration."""
    logger = get_logger(__name__)
    
    try:
        # Check if providers list exists
        if not hasattr(provider_config, 'providers') or not provider_config.providers:
            logger.error("Provider configuration must have at least one provider instance")
            return False
        
        # Validate each provider instance
        for provider_instance in provider_config.providers:
            if not hasattr(provider_instance, 'name') or not provider_instance.name:
                logger.error("Provider instance must have a name")
                return False
            
            if not hasattr(provider_instance, 'type') or not provider_instance.type:
                logger.error(f"Provider instance '{provider_instance.name}' must have a type")
                return False
            
            # Check for supported provider types
            supported_types = ['aws']  # Add more as they're implemented
            if provider_instance.type not in supported_types:
                logger.warning(f"Provider type '{provider_instance.type}' is not supported (supported: {supported_types})")
        
        return True
        
    except Exception as e:
        logger.error(f"Provider configuration validation error: {str(e)}")
        return False


def _register_provider_instance(provider_instance) -> bool:
    """Register a specific provider instance based on its type."""
    logger = get_logger(__name__)
    
    try:
        logger.info(f"Registering provider instance: {provider_instance.name} (type: {provider_instance.type})")
        
        if provider_instance.type == "aws":
            from src.providers.aws.registration import register_aws_provider
            from src.infrastructure.registry.provider_registry import get_provider_registry
            
            # Get provider registry
            registry = get_provider_registry()
            
            # Register AWS provider instance with unique name
            register_aws_provider(registry=registry, instance_name=provider_instance.name)
            logger.info(f"AWS provider instance '{provider_instance.name}' registered successfully")
            return True
        else:
            logger.warning(f"Unknown provider type: {provider_instance.type} for instance: {provider_instance.name}")
            return False
            
    except ImportError as e:
        logger.warning(f"Provider type '{provider_instance.type}' not available: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to register provider instance '{provider_instance.name}': {str(e)}")
        return False


def create_provider_strategy_factory(container: DIContainer) -> ProviderStrategyFactory:
    """Create provider strategy factory."""
    return ProviderStrategyFactory(
        logger=container.get(LoggingPort),
        config=container.get(ConfigurationManager)
    )


def create_configured_provider_context(container: DIContainer) -> ProviderContext:
    """Create provider context using configuration-driven factory."""
    try:
        logger = container.get(LoggingPort)
        config_manager = container.get(ConfigurationManager)
        
        # Register providers first (now that DI container is ready)
        _register_providers()
        
        # Try to get provider config
        try:
            provider_config = config_manager.get_provider_config()
            if provider_config and provider_config.providers:
                # Use configuration-driven approach
                from src.providers.base.strategy import create_provider_context
                return create_provider_context(logger=logger)
        except (AttributeError, Exception) as e:
            logger.warning(f"Failed to create provider context: {e}")
        
        # Fallback to basic provider context
        from src.providers.base.strategy import create_provider_context
        return create_provider_context(logger)
        
    except Exception as e:
        logger = container.get(LoggingPort)
        logger.error(f"Failed to create configured provider context, using fallback: {e}")
        from src.providers.base.strategy import create_provider_context
        return create_provider_context(logger)


def _register_provider_specific_services(container: DIContainer) -> None:
    """Register provider-specific services conditionally."""
    logger = get_logger(__name__)
    
    # Register AWS services if available
    try:
        import importlib.util
        # Check if AWS provider is available
        if importlib.util.find_spec("src.providers.aws"):
            logger.info("Registering AWS-specific services")
            _register_aws_services(container)
        else:
            logger.info("AWS provider not available, skipping AWS service registration")
    except ImportError:
        logger.info("AWS provider not available, skipping AWS service registration")
    except Exception as e:
        logger.warning(f"Error checking for AWS provider: {str(e)}")


def _register_aws_services(container: DIContainer) -> None:
    """Register AWS-specific services."""
    logger = get_logger(__name__)
    
    try:
        # Import AWS-specific classes
        from src.providers.aws.infrastructure.aws_client import AWSClient
        from src.providers.aws.infrastructure.aws_handler_factory import AWSHandlerFactory
        from src.providers.aws.utilities.aws_operations import AWSOperations
        from src.providers.aws.infrastructure.handlers.spot_fleet_handler import SpotFleetHandler
        from src.providers.aws.infrastructure.adapters.template_adapter import AWSTemplateAdapter
        from src.providers.aws.infrastructure.adapters.machine_adapter import AWSMachineAdapter
        from src.providers.aws.infrastructure.adapters.provisioning_adapter import AWSProvisioningAdapter
        from src.providers.aws.infrastructure.adapters.request_adapter import AWSRequestAdapter
        from src.providers.aws.infrastructure.adapters.resource_manager_adapter import AWSResourceManagerAdapter
        from src.providers.aws.strategy.aws_provider_adapter import AWSProviderAdapter
        from src.providers.aws.strategy.aws_provider_strategy import AWSProviderStrategy
        from src.providers.aws.managers.aws_instance_manager import AWSInstanceManager
        from src.providers.aws.managers.aws_resource_manager import AWSResourceManagerImpl
        from src.infrastructure.ports.resource_provisioning_port import ResourceProvisioningPort
        from src.infrastructure.ports.cloud_resource_manager_port import CloudResourceManagerPort
        from src.infrastructure.ports.request_adapter_port import RequestAdapterPort
        
        # Register AWS client
        container.register_singleton(
            AWSClient,
            lambda c: _create_aws_client(c)
        )
        
        # Register AWS operations utility
        container.register_singleton(AWSOperations)
        
        # Register AWS handler factory
        container.register_singleton(AWSHandlerFactory)
        
        # Register AWS handler implementations
        container.register_singleton(SpotFleetHandler)
        
        # Register AWS adapter implementations using @injectable decorator
        container.register_singleton(AWSTemplateAdapter)
        container.register_singleton(AWSMachineAdapter)
        container.register_singleton(AWSProvisioningAdapter)
        container.register_singleton(AWSRequestAdapter)
        container.register_singleton(AWSResourceManagerAdapter)
        
        # Register AWS provider strategy and adapter using @injectable decorator
        container.register_singleton(AWSProviderAdapter)
        container.register_singleton(AWSProviderStrategy)
        
        # Register AWS manager implementations using @injectable decorator
        container.register_singleton(AWSInstanceManager)
        container.register_singleton(AWSResourceManagerImpl)
        
        # Register port implementations
        container.register_factory(
            ResourceProvisioningPort,
            lambda c: c.get(AWSProvisioningAdapter)
        )
        
        container.register_factory(
            CloudResourceManagerPort,
            lambda c: c.get(AWSResourceManagerAdapter)
        )
        
        container.register_factory(
            RequestAdapterPort,
            lambda c: c.get(AWSRequestAdapter)
        )
        
        logger.info("AWS services registered successfully")
    except ImportError as e:
        logger.warning(f"Failed to import AWS classes: {str(e)}")
    except Exception as e:
        logger.warning(f"Failed to register AWS services: {str(e)}")


def _create_aws_client(container: DIContainer) -> Any:
    """Create AWS client with proper port dependencies."""
    config = container.get(ConfigurationPort)
    logger = container.get(LoggingPort)
    
    from src.providers.aws.infrastructure.aws_client import AWSClient
    return AWSClient(
        config=config,
        logger=logger
    )
