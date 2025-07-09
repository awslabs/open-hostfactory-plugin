"""Service registration orchestrator for dependency injection.

This module coordinates the registration of all services across different layers:
- Core services (logging, configuration, metrics)
- Provider services (AWS, strategy patterns)
- Infrastructure services (repositories, templates)
- CQRS handlers (commands and queries)
- Server services (FastAPI, REST API handlers)
"""
from typing import Optional, Dict, Any

from src.infrastructure.di.container import DIContainer, get_container

# Import focused service registration modules
from src.infrastructure.di.core_services import register_core_services
from src.infrastructure.di.provider_services import register_provider_services
from src.infrastructure.di.infrastructure_services import register_infrastructure_services
from src.infrastructure.di.command_handler_services import (
    register_command_handler_services
)
from src.infrastructure.di.query_handler_services import (
    register_query_handler_services
)
from src.infrastructure.di.server_services import register_server_services


def register_all_services(container: Optional[DIContainer] = None) -> DIContainer:
    """
    Register all services in the dependency injection container.
    
    Args:
        container: Optional container instance
        
    Returns:
        Configured container
    """
    if container is None:
        container = get_container()
    
    # Register services in dependency order
    # 1. Register port adapters first (foundational dependencies)
    from src.infrastructure.di.port_registrations import register_port_adapters
    register_port_adapters(container)
    
    # 2. Setup CQRS infrastructure (handlers and buses)
    from src.infrastructure.di.container import _setup_cqrs_infrastructure
    _setup_cqrs_infrastructure(container)
    
    # 3. Register provider services (needed by infrastructure services)
    register_provider_services(container)
    
    # 4. Register infrastructure services
    register_infrastructure_services(container)
    
    # 5. Register core services (depend on everything else)
    register_core_services(container)
    
    # Register CQRS handlers in container
    register_command_handler_services(container)
    register_query_handler_services(container)
    
    # 6. Register server services (conditionally based on config)
    register_server_services(container)
    
    return container


def create_handler(handler_class, config: Optional[Dict[str, Any]] = None) -> Any:
    """
    Create an API handler with dependencies.
    
    Args:
        handler_class: Handler class to create
        config: Optional configuration
        
    Returns:
        Created handler instance
    """
    # Ensure services are registered
    container = register_services()
    
    # Register handler class if not already registered
    if handler_class not in container._factories:
        # Get logger
        from src.infrastructure.logging.logger import get_logger
        logger = get_logger(__name__)
        
        # Register handler class directly if it uses @injectable
        try:
            from src.infrastructure.di.decorators import is_injectable
            if is_injectable(handler_class):
                logger.info(f"Registering injectable handler class {handler_class.__name__}")
                container.register_singleton(handler_class)
            else:
                # Legacy handler registration
                logger.info(f"Registering legacy handler class {handler_class.__name__}")
                
                def handler_factory(c):
                    # Get application service from container
                    from src.application.service import ApplicationService
                    from src.monitoring.metrics import MetricsCollector

                    app_service = c.get(ApplicationService)
                    
                    # Get metrics collector from container if available
                    metrics = c.get_optional(MetricsCollector)
                        
                    # Create handler with dependencies
                    return handler_class(app_service, metrics)
                    
                container.register_factory(handler_class, handler_factory)
        except ImportError:
            # Fallback to legacy registration if decorator module not available
            logger.info(f"Fallback registration for handler class {handler_class.__name__}")
            
            def handler_factory(c):
                # Get application service from container
                from src.application.service import ApplicationService
                from src.monitoring.metrics import MetricsCollector

                app_service = c.get(ApplicationService)
                
                # Get metrics collector from container if available
                metrics = c.get_optional(MetricsCollector)
                    
                # Create handler with dependencies
                return handler_class(app_service, metrics)
                
            container.register_factory(handler_class, handler_factory)
    
    # Get handler from container
    return container.get(handler_class)


def register_services(container: Optional[DIContainer] = None) -> DIContainer:
    """
    Main service registration function.
    
    Args:
        container: Optional container instance
        
    Returns:
        Configured container
    """
    return register_all_services(container)
