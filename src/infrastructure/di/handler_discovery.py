"""
Infrastructure Handler Discovery System.

This module provides the infrastructure implementation for discovering
and registering CQRS handlers. It consumes application-layer handler
registrations and provides concrete discovery mechanisms.

Clean Architecture Compliance:
- Infrastructure depends on Application (✅)
- Application does NOT depend on Infrastructure (✅)
- Domain is independent (✅)

Layer Separation:
- Application: @query_handler, @command_handler decorators
- Infrastructure: Discovery, module scanning, DI registration
"""
from typing import Type, Dict, Any
import importlib
import pkgutil
from pathlib import Path

from src.application.decorators import (
    get_registered_query_handlers,
    get_registered_command_handlers,
    get_handler_registry_stats
)
from src.application.interfaces.command_query import QueryHandler, CommandHandler, Query, Command
from src.infrastructure.di.container import DIContainer
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class HandlerDiscoveryService:
    """
    Infrastructure service for discovering and registering CQRS handlers.
    
    This service scans application modules to trigger decorator registration,
    then registers discovered handlers with the DI container.
    """
    
    def __init__(self, container: DIContainer):
        self.container = container
    
    def discover_and_register_handlers(self, base_package: str = "src.application") -> None:
        """
        Discover all handlers and register them with the DI container.
        
        Args:
            base_package: Base package to scan for handlers
        """
        logger.info(f"Starting handler discovery in package: {base_package}")
        
        # Step 1: Discover handlers by importing modules
        self._discover_handlers(base_package)
        
        # Step 2: Register discovered handlers with DI container
        self._register_handlers()
        
        # Step 3: Log results
        stats = get_handler_registry_stats()
        logger.info(f"Handler discovery complete: {stats}")
    
    def _discover_handlers(self, base_package: str) -> None:
        """
        Discover handlers by importing all modules in the package.
        
        This triggers the @query_handler and @command_handler decorators
        to register themselves in the application-layer registry.
        """
        try:
            # Import the base package
            package = importlib.import_module(base_package)
            package_path = Path(package.__file__).parent
            
            # Walk through all modules in the package
            for module_info in pkgutil.walk_packages([str(package_path)], f"{base_package}."):
                try:
                    # Import the module to trigger decorator registration
                    importlib.import_module(module_info.name)
                    logger.debug(f"Imported module: {module_info.name}")
                except Exception as e:
                    logger.warning(f"Failed to import module {module_info.name}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Handler discovery failed: {e}")
            raise
    
    def _register_handlers(self) -> None:
        """
        Register all discovered handlers with the DI container.
        
        Consumes the application-layer handler registries and registers
        handlers as singletons in the infrastructure DI container.
        """
        logger.info("Registering discovered handlers with DI container")
        
        # Register query handlers
        query_handlers = get_registered_query_handlers()
        for query_type, handler_class in query_handlers.items():
            try:
                # Register as singleton (handlers are stateless)
                self.container.register_singleton(handler_class, handler_class)
                logger.debug(f"Registered query handler: {handler_class.__name__} for {query_type.__name__}")
            except Exception as e:
                logger.error(f"Failed to register query handler {handler_class.__name__}: {e}")
        
        # Register command handlers
        command_handlers = get_registered_command_handlers()
        for command_type, handler_class in command_handlers.items():
            try:
                # Register as singleton (handlers are stateless)
                self.container.register_singleton(handler_class, handler_class)
                logger.debug(f"Registered command handler: {handler_class.__name__} for {command_type.__name__}")
            except Exception as e:
                logger.error(f"Failed to register command handler {handler_class.__name__}: {e}")
        
        total_registered = len(query_handlers) + len(command_handlers)
        logger.info(f"Handler registration complete. Registered {total_registered} handlers")


def create_handler_discovery_service(container: DIContainer) -> HandlerDiscoveryService:
    """
    Factory function to create handler discovery service.
    
    Args:
        container: DI container to register handlers with
        
    Returns:
        Configured handler discovery service
    """
    return HandlerDiscoveryService(container)
