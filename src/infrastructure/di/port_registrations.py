"""Port adapter registrations for dependency injection."""

import os
from src.domain.base.ports import (
    LoggingPort,
    ContainerPort,
    EventPublisherPort,
    ErrorHandlingPort,
    TemplateConfigurationPort,
    TemplateFormatPort,
    ConfigurationPort
)
from src.infrastructure.adapters.logging_adapter import LoggingAdapter
from src.infrastructure.adapters.factories.container_adapter_factory import ContainerAdapterFactory
from src.infrastructure.adapters.error_handling_adapter import ErrorHandlingAdapter
from src.infrastructure.adapters.template_configuration_adapter import TemplateConfigurationAdapter
from src.infrastructure.adapters.template_format_adapter import TemplateFormatAdapter
from src.infrastructure.template.loader import TemplateLoader
from src.infrastructure.template.template_cache_service import TemplateCacheService
from src.infrastructure.template.format_converter import TemplateFormatConverter

# Import configuration manager
from src.config.manager import ConfigurationManager, get_config_manager

def register_port_adapters(container):
    """Register all port adapters in the DI container."""
    
    # Register configuration manager FIRST (needed by other services)
    container.register_singleton(
        ConfigurationManager,
        lambda c: get_config_manager()
    )
    
    # Register configuration port
    container.register_singleton(
        ConfigurationPort,
        lambda c: get_config_manager()
    )
    
    # Register logging port adapter
    container.register_singleton(
        LoggingPort,
        LoggingAdapter("application")
    )
    
    # Register container port adapter using factory to avoid circular dependency
    container.register_singleton(
        ContainerPort,
        lambda c: ContainerAdapterFactory.create_adapter(c)
    )
    
    # Register error handling port adapter
    container.register_singleton(
        ErrorHandlingAdapter,
        lambda c: ErrorHandlingAdapter()
    )
    container.register_singleton(
        ErrorHandlingPort,
        lambda c: c.get(ErrorHandlingAdapter)
    )
    
    # Register template dependencies first (needed by TemplateConfigurationPort)
    _register_template_services(container)
    
    # Register TemplateConfigurationStore (needed by CQRS query handlers)
    from src.infrastructure.template.configuration_store import TemplateConfigurationStore
    container.register_singleton(TemplateConfigurationStore, create_template_configuration_store)
    
    # Register template configuration port adapter
    container.register_singleton(TemplateConfigurationAdapter, create_template_configuration_adapter)
    container.register_singleton(
        TemplateConfigurationPort,
        lambda c: c.get(TemplateConfigurationAdapter)
    )
    
    # Register template format port adapter
    container.register_singleton(
        TemplateFormatPort,
        lambda c: TemplateFormatAdapter(c.get(TemplateFormatConverter))
    )


def _register_template_services(container):
    """Register template-related services."""
    
    # Register template loader with proper path resolution
    def create_template_loader(c):
        """Create template loader with resolved file paths."""
        config_manager = c.get(ConfigurationManager)
        
        # Resolve template file paths using configuration manager
        legacy_path = config_manager.resolve_file('legacy', 'awsprov_templates.json')
        new_path = config_manager.resolve_file('template', 'templates.json')
        
        return TemplateLoader(
            legacy_path=legacy_path,
            new_path=new_path if os.path.exists(new_path) else None
        )
    
    container.register_singleton(TemplateLoader, create_template_loader)
    
    # Register template cache service  
    from src.infrastructure.template.template_cache_service import NoOpTemplateCacheService
    container.register_singleton(
        TemplateCacheService,
        lambda c: NoOpTemplateCacheService(
            logger=c.get(LoggingPort)
        )
    )


def create_template_configuration_store(c):
    """Create TemplateConfigurationStore using our working Phase 2 TemplateLoader."""
    # Use our successful Phase 2 template loader fix
    template_loader = c.get(TemplateLoader)
    
    # Create file store wrapper with logger
    from src.infrastructure.template.configuration_store import TemplateFileStore
    from src.domain.base.ports import LoggingPort
    logger = c.get(LoggingPort)
    file_store = TemplateFileStore(template_loader, logger)
    
    # Get cache service (already registered)
    cache = c.get(TemplateCacheService)
    
    # Get logger for the store
    logger = c.get(LoggingPort)
    
    # Create the unified configuration store
    from src.infrastructure.template.configuration_store import TemplateConfigurationStore
    return TemplateConfigurationStore(
        file_store=file_store,
        cache=cache,
        logger=logger
    )


def create_template_configuration_adapter(c):
    """Create TemplateConfigurationAdapter using registered TemplateConfigurationStore."""
    # Use the TemplateConfigurationStore we registered above
    from src.infrastructure.template.configuration_store import TemplateConfigurationStore
    store = c.get(TemplateConfigurationStore)
    return TemplateConfigurationAdapter(store)
