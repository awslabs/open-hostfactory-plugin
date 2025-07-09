"""Infrastructure service registrations for dependency injection."""

from src.infrastructure.di.container import DIContainer
from src.infrastructure.logging.logger import get_logger
from src.domain.base.ports import LoggingPort
from src.domain.request.repository import RequestRepository
from src.domain.machine.repository import MachineRepository
from src.domain.template.repository import TemplateRepository
from src.infrastructure.template import (
    TemplateLoader, 
    TemplateCacheService, 
    NoOpTemplateCacheService, 
    TemplateConfigurationStore,
    SyncTemplateConfigurationStore,
    create_template_configuration_store,
    create_sync_template_configuration_store
)
from src.providers.aws.infrastructure.template.caching_ami_resolver import CachingAMIResolver
from src.domain.template.ami_resolver import AMIResolver


def register_infrastructure_services(container: DIContainer) -> None:
    """Register infrastructure services."""
    
    # Register template services
    _register_template_services(container)
    
    # Register repository services
    _register_repository_services(container)


def _register_template_services(container: DIContainer) -> None:
    """Register template configuration services."""
    
    # Register template loader
    container.register_singleton(TemplateLoader)
    
    # Register template cache service
    # Determine which cache service to use based on configuration
    from src.config.manager import ConfigurationManager
    config_manager = container.get(ConfigurationManager)
    
    # Check if caching is enabled
    if hasattr(config_manager, 'is_template_caching_enabled') and config_manager.is_template_caching_enabled():
        # Use TTL cache service as the concrete implementation
        from src.infrastructure.template.template_cache_service import TTLTemplateCacheService
        container.register_singleton(TemplateCacheService, lambda c: TTLTemplateCacheService(ttl_seconds=300, logger=c.get(LoggingPort)))
    else:
        container.register_singleton(TemplateCacheService, lambda c: NoOpTemplateCacheService(logger=c.get(LoggingPort)))
    
    # Check if AMI resolution is enabled
    from src.config import TemplateConfig
    template_config = config_manager.get_typed(TemplateConfig)
    
    
    # Register synchronous wrapper for CQRS handlers
    container.register_singleton(
        SyncTemplateConfigurationStore,
        lambda c: create_sync_template_configuration_store(
            async_store=c.get(TemplateConfigurationStore),
            logger=c.get(LoggingPort)
        )
    )
    
    # Register AMI resolver if enabled
    if template_config.ami_resolution.enabled:
        container.register_singleton(CachingAMIResolver)


def _register_repository_services(container: DIContainer) -> None:
    """Register repository services using storage registry pattern."""
    from src.infrastructure.utilities.factories.repository_factory import RepositoryFactory
    from src.infrastructure.persistence.registration import register_all_storage_types
    
    # Ensure all storage types are registered
    try:
        register_all_storage_types()
    except Exception as e:
        logger = get_logger(__name__)
        logger.warning(f"Some storage types failed to register: {e}")
    
    # Register repository factory
    container.register_singleton(RepositoryFactory)
    
    # Register repositories using the factory
    container.register_singleton(
        RequestRepository,
        lambda c: c.get(RepositoryFactory).create_request_repository()
    )
    
    container.register_singleton(
        MachineRepository,
        lambda c: c.get(RepositoryFactory).create_machine_repository()
    )
    
    container.register_singleton(
        TemplateRepository,
        lambda c: c.get(RepositoryFactory).create_template_repository()
    )
