"""Application bootstrap - DI-based architecture."""
from __future__ import annotations

from typing import Any, Dict, Optional

# Import DI container
from src.application.service import ApplicationService

# Import configuration
from src.config import AppConfig

# Import logging
from src.infrastructure.logging.logger import get_logger, setup_logging


class Application:
    """DI-based application context manager."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config_path = config_path
        self._application_service: Optional[ApplicationService] = None
        self._initialized = False
        self.logger = get_logger(__name__)
        
        # Initialize DI container and register services
        from src.infrastructure.di.services import register_services
        self._container = register_services()
        
        # Set up domain container for decorators (Clean Architecture compliance)
        from src.domain.base.decorators import set_domain_container
        set_domain_container(self._container)
        
        # Get configuration with config path
        from src.config.manager import get_config_manager
        config_manager = get_config_manager(config_path)
        
        # Extract provider type from config
        provider_config = config_manager.get("provider", {"type": "mock"})
        if isinstance(provider_config, dict):
            self.provider_type = provider_config.get("type", "mock")
        else:
            self.provider_type = str(provider_config)

    def initialize(self) -> bool:
        """Initialize the application with DI container."""
        try:
            self.logger.info(f"Initializing application with provider: {self.provider_type}")
            
            # Initialize configuration with config path
            from src.config.manager import get_config_manager
            config_manager = get_config_manager(self.config_path)
            
            # Log provider configuration information
            self._log_provider_configuration(config_manager)
            
            # Setup logging
            app_config = config_manager.get_typed(AppConfig)
            setup_logging(app_config.logging)
            
            # Get application service from DI container
            self._application_service = self._container.get(ApplicationService)
            
            # Initialize the service
            if not self._application_service.initialize():
                self.logger.error("Failed to initialize application service")
                return False
            
            # Log final provider information
            self._log_final_provider_info()
            
            self._initialized = True
            self.logger.info(f"Open Host Factory initialized successfully with {self.provider_type} provider")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize application: {e}")
            return False
    
    def _log_provider_configuration(self, config_manager) -> None:
        """Log provider configuration information during initialization."""
        try:
            # Check if unified provider configuration is available
            if hasattr(config_manager, 'get_provider_config'):
                unified_config = config_manager.get_provider_config()
                mode = unified_config.get_mode()
                active_providers = unified_config.get_active_providers()
                
                self.logger.info(f"Provider configuration mode: {mode.value}")
                self.logger.info(f"Active providers: {[p.name for p in active_providers]}")
                
                if mode.value == "multi":
                    self.logger.info(f"Selection policy: {unified_config.selection_policy}")
                    self.logger.info(f"Health check interval: {unified_config.health_check_interval}s")
                    
            elif hasattr(config_manager, 'is_provider_strategy_enabled'):
                if config_manager.is_provider_strategy_enabled():
                    self.logger.info("Provider strategy enabled but configuration not available")
                else:
                    self.logger.info("Using legacy provider configuration")
            else:
                self.logger.info("Using legacy provider configuration")
                
        except Exception as e:
            self.logger.debug(f"Could not log provider configuration details: {str(e)}")
    
    def _log_final_provider_info(self) -> None:
        """Log final provider information after initialization."""
        try:
            if self._application_service:
                provider_info = self._application_service.get_provider_info()
                self.logger.info(f"Final provider mode: {provider_info.get('mode', 'unknown')}")
                
                if 'provider_names' in provider_info:
                    self.logger.info(f"Active provider names: {provider_info['provider_names']}")
                elif 'provider_type' in provider_info:
                    self.logger.info(f"Provider type: {provider_info['provider_type']}")
                    
        except Exception as e:
            self.logger.debug(f"Could not log final provider info: {str(e)}")

    def get_application_service(self) -> ApplicationService:
        """Get the application service."""
        if not self._initialized:
            raise RuntimeError("Application not initialized")
        return self._application_service
    
    def get_query_bus(self):
        """Get the query bus for CQRS operations (cached after first access)."""
        if not self._initialized:
            raise RuntimeError("Application not initialized")
        
        # Cache the query bus after first lookup for performance
        if not hasattr(self, '_query_bus'):
            from src.infrastructure.di.buses import QueryBus
            self._query_bus = self._container.get(QueryBus)
        return self._query_bus
    
    def get_command_bus(self):
        """Get the command bus for CQRS operations (cached after first access)."""
        if not self._initialized:
            raise RuntimeError("Application not initialized")
        
        # Cache the command bus after first lookup for performance
        if not hasattr(self, '_command_bus'):
            from src.infrastructure.di.buses import CommandBus
            self._command_bus = self._container.get(CommandBus)
        return self._command_bus

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information."""
        if not self._initialized:
            return {'status': 'not_initialized'}
        
        return self._application_service.get_provider_info()

    def health_check(self) -> Dict[str, Any]:
        """Check application health."""
        if not self._initialized:
            return {
                'status': 'error',
                'message': 'Application not initialized'
            }
        
        return self._application_service.health_check()

    def shutdown(self) -> None:
        """Shutdown the application."""
        self.logger.info("Shutting down application")
        self._initialized = False

    def __enter__(self) -> 'Application':
        """Context manager entry."""
        if not self.initialize():
            raise RuntimeError("Failed to initialize application")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.shutdown()


def create_application(config_path: Optional[str] = None) -> Application:
    """Create and initialize a provider-aware application."""
    app = Application(config_path)
    if not app.initialize():
        raise RuntimeError(f"Failed to initialize application with {app.provider_type} provider")
    return app


def main() -> None:
    """Main entry point for provider-aware application."""
    import os
    import sys

    # Get provider type from environment or config
    config_path = os.getenv('CONFIG_PATH')
    
    # Only print before app creation - no logger available yet
    print("Starting Open Host Factory...")
    
    try:
        with create_application(config_path) as app:
            # Use existing app.logger - no need to create new logger
            app.logger.info(f"Application started successfully with {app.provider_type.upper()} provider")
            
            # Get provider info
            provider_info = app.get_provider_info()
            app.logger.info(f"Provider: {provider_info.get('provider_type')}")
            app.logger.info(f"Status: {provider_info.get('initialized', False)}")
            
            # Health check
            health = app.health_check()
            app.logger.info(f"Health check status: {health.get('status')}")
            
            # Get application service for API operations
            app_service = app.get_application_service()
            
            # Example: Get available templates
            try:
                templates = app_service.get_available_templates()  # List[Template]
                app.logger.info(f"Available templates: {len(templates)}")
                for template in templates:
                    app.logger.debug(f"  - {template.name}: {template.description}")
            except Exception as e:
                app.logger.error(f"Error getting templates: {e}")
            
            # Keep running (in a real application, this would be the API server)
            app.logger.info("Application running... (Press Ctrl+C to stop)")
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                app.logger.info("Shutdown requested by user")
                
    except Exception as e:
        # Keep print here - app creation failed, no logger available
        print(f"Application failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
