"""Core service registrations for dependency injection."""
from typing import Optional, Dict, Any, TYPE_CHECKING

from src.infrastructure.di.container import DIContainer
from src.config.manager import ConfigurationManager
from src.domain.base.ports import ConfigurationPort, LoggingPort, EventPublisherPort, ErrorHandlingPort, TemplateFormatPort
from src.monitoring.metrics import MetricsCollector
from src.application.template.format_service import TemplateFormatService
from src.infrastructure.template.format_converter import TemplateFormatConverter
from src.infrastructure.di.buses import CommandBus, QueryBus
from src.providers.base.strategy import ProviderContext

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from src.application.service import ApplicationService


def register_core_services(container: DIContainer) -> None:
    """Register core application services."""
    
    # Register metrics collector
    container.register_singleton(MetricsCollector)
    
    # Register template format converter
    container.register_singleton(TemplateFormatConverter)
    
    # Register template format service with port dependency
    container.register_singleton(
        TemplateFormatService,
        lambda c: TemplateFormatService(c.get(TemplateFormatPort))
    )
    
    # Register command and query buses with factory functions
    container.register_factory(
        CommandBus,
        lambda c: CommandBus(
            logger=c.get(LoggingPort),
            event_publisher=c.get(EventPublisherPort)
        )
    )
    
    container.register_factory(
        QueryBus,
        lambda c: QueryBus(
            logger=c.get(LoggingPort)
        )
    )
    
    # Register application service (main orchestrator)
    # Import here to avoid circular imports
    from src.application.service import ApplicationService
    container.register_factory(
        ApplicationService,
        lambda c: _create_application_service(c)
    )


def _create_application_service(container: DIContainer) -> 'ApplicationService':
    """Create application service with all dependencies."""
    from src.application.service import ApplicationService
    
    config_manager = container.get(ConfigurationManager)
    provider_type = config_manager.app_config.provider.type if hasattr(config_manager, 'app_config') else 'aws'
    
    return ApplicationService(
        provider_type=provider_type,
        command_bus=container.get(CommandBus),
        query_bus=container.get(QueryBus),
        logger=container.get(LoggingPort),
        container=container,
        config=container.get(ConfigurationPort),
        error_handler=container.get(ErrorHandlingPort),
        provider_context=container.get(ProviderContext)  # Always required
    )
