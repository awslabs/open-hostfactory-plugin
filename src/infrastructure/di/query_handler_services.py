"""Query handler service registrations for dependency injection."""
from typing import Optional, Dict, Any, TYPE_CHECKING

from src.infrastructure.di.container import DIContainer
from src.domain.base.ports import LoggingPort
from src.infrastructure.di.buses import QueryBus
from src.providers.base.strategy import ProviderContext


def register_query_handler_services(container: DIContainer) -> None:
    """Register query handler services."""
    
    # Register template query handlers
    _register_template_query_handlers(container)
    
    # Register request query handlers
    _register_request_query_handlers(container)
    
    # Register machine query handlers
    _register_machine_query_handlers(container)
    
    # Register system query handlers
    _register_system_query_handlers(container)


def _register_template_query_handlers(container: DIContainer) -> None:
    """Register template-related query handlers."""
    
    # Import template query handlers
    try:
        from src.application.queries.handlers import (
            GetTemplateHandler,
            ListTemplatesHandler,
            SearchTemplatesHandler,
            ValidateTemplateQueryHandler
        )
        
        # Use direct registration with @injectable decorator
        container.register_singleton(GetTemplateHandler)
        container.register_singleton(ListTemplatesHandler)
        container.register_singleton(SearchTemplatesHandler)
        container.register_singleton(ValidateTemplateQueryHandler)
    except ImportError as e:
        logger = container.get(LoggingPort)
        logger.debug(f"Template query handlers not available: {e}")


def _register_request_query_handlers(container: DIContainer) -> None:
    """Register request-related query handlers."""
    
    # Import request query handlers
    try:
        from src.application.queries.handlers import (
            GetRequestStatusHandler,
            ListRequestsHandler,
            GetRequestHistoryHandler,
            GetActiveRequestsHandler,
            GetRequestMetricsHandler
        )
        
        # Use direct registration with @injectable decorator
        container.register_singleton(GetRequestStatusHandler)
        container.register_singleton(ListRequestsHandler)
        container.register_singleton(GetRequestHistoryHandler)
        container.register_singleton(GetActiveRequestsHandler)
        container.register_singleton(GetRequestMetricsHandler)
    except ImportError as e:
        logger = container.get(LoggingPort)
        logger.debug(f"Request query handlers not available: {e}")


def _register_machine_query_handlers(container: DIContainer) -> None:
    """Register machine-related query handlers."""
    
    # Import machine query handlers
    try:
        from src.application.queries.handlers import (
            GetMachineHandler,
            ListMachinesHandler,
            GetMachineStatusHandler,
            GetMachineMetricsHandler
        )
        
        # Use direct registration with @injectable decorator
        container.register_singleton(GetMachineHandler)
        container.register_singleton(ListMachinesHandler)
        container.register_singleton(GetMachineStatusHandler)
        container.register_singleton(GetMachineMetricsHandler)
    except ImportError as e:
        logger = container.get(LoggingPort)
        logger.debug(f"Machine query handlers not available: {e}")


def _register_system_query_handlers(container: DIContainer) -> None:
    """Register system-related query handlers."""
    
    # Import system query handlers
    try:
        from src.application.queries.system_handlers import (
            GetSystemStatusHandler,
            GetHealthCheckHandler,
            GetSystemMetricsHandler
        )
        
        container.register_singleton(GetSystemStatusHandler)
        container.register_singleton(GetHealthCheckHandler)
        container.register_singleton(GetSystemMetricsHandler)
    except ImportError as e:
        logger = container.get(LoggingPort)
        logger.debug(f"System query handlers not available: {e}")


def register_query_handlers_with_bus(container: DIContainer) -> None:
    """Register query handlers with the query bus."""
    
    try:
        query_bus = container.get(QueryBus)
        logger = container.get(LoggingPort)
        
        # Get provider context for strategy handlers
        provider_context = container.get(ProviderContext)
        
        # Register template query handlers
        try:
            from src.application.dto.queries import (
                GetTemplateQuery,
                ListTemplatesQuery,
                SearchTemplatesQuery,
                ValidateTemplateQuery
            )
            
            from src.application.queries.handlers import (
                GetTemplateHandler,
                ListTemplatesHandler,
                SearchTemplatesHandler,
                ValidateTemplateQueryHandler
            )
            
            query_bus.register(
                GetTemplateQuery,
                container.get(GetTemplateHandler)
            )
            
            query_bus.register(
                ListTemplatesQuery,
                container.get(ListTemplatesHandler)
            )
            
            query_bus.register(
                SearchTemplatesQuery,
                container.get(SearchTemplatesHandler)
            )
            
            query_bus.register(
                ValidateTemplateQuery,
                container.get(ValidateTemplateQueryHandler)
            )
        except Exception as e:
            logger.debug(f"Failed to register template query handlers with bus: {e}")
        
        # Register request query handlers
        try:
            from src.application.request.queries import (
                GetRequestStatusQuery,
                ListRequestsQuery,
                GetRequestHistoryQuery,
                GetActiveRequestsQuery,
                GetRequestMetricsQuery
            )
            
            from src.application.queries.handlers import (
                GetRequestStatusHandler,
                ListRequestsHandler,
                GetRequestHistoryHandler,
                GetActiveRequestsHandler,
                GetRequestMetricsHandler
            )
            
            query_bus.register(
                GetRequestStatusQuery,
                container.get(GetRequestStatusHandler)
            )
            
            query_bus.register(
                ListRequestsQuery,
                container.get(ListRequestsHandler)
            )
            
            query_bus.register(
                GetRequestHistoryQuery,
                container.get(GetRequestHistoryHandler)
            )
            
            query_bus.register(
                GetActiveRequestsQuery,
                container.get(GetActiveRequestsHandler)
            )
            
            query_bus.register(
                GetRequestMetricsQuery,
                container.get(GetRequestMetricsHandler)
            )
        except Exception as e:
            logger.debug(f"Failed to register request query handlers with bus: {e}")
        
    except Exception as e:
        logger = container.get(LoggingPort)
        logger.warning(f"Failed to register some query handlers: {e}")
