"""Command handler service registrations for dependency injection."""
from typing import Optional, Dict, Any, TYPE_CHECKING

from src.infrastructure.di.container import DIContainer
from src.domain.base.ports import LoggingPort
from src.providers.base.strategy import ProviderContext
from src.infrastructure.di.buses import CommandBus

# Import command handlers
from src.application.machine.handlers import (
    ConvertMachineStatusCommandHandler,
    ConvertBatchMachineStatusCommandHandler,
    ValidateProviderStateCommandHandler,
    UpdateMachineStatusCommandHandler,
    CleanupMachineResourcesCommandHandler
)


def register_command_handler_services(container: DIContainer) -> None:
    """Register command handler services."""
    
    # Register machine command handlers
    _register_machine_command_handlers(container)
    
    # Register request command handlers
    _register_request_command_handlers(container)
    
    # Register template command handlers
    _register_template_command_handlers(container)
    
    # Register system command handlers
    _register_system_command_handlers(container)
    
    # Register CLI command handlers
    _register_cli_command_handlers(container)


def _register_machine_command_handlers(container: DIContainer) -> None:
    """Register machine-related command handlers."""
    
    container.register_singleton(ConvertMachineStatusCommandHandler)
    
    container.register_singleton(ConvertBatchMachineStatusCommandHandler)
    
    container.register_singleton(ValidateProviderStateCommandHandler)
    
    container.register_singleton(UpdateMachineStatusCommandHandler)
    
    container.register_singleton(CleanupMachineResourcesCommandHandler)


def _register_request_command_handlers(container: DIContainer) -> None:
    """Register request-related command handlers."""
    
    # Import request command handlers
    from src.application.commands.request_handlers import (
        CreateMachineRequestHandler,
        CreateReturnRequestHandler,
        UpdateRequestStatusHandler,
        CancelRequestHandler,
        CompleteRequestHandler
    )
    
    try:
        # Use direct registration with @injectable decorator
        container.register_singleton(CreateMachineRequestHandler)
        container.register_singleton(CreateReturnRequestHandler)
        container.register_singleton(UpdateRequestStatusHandler)
        container.register_singleton(CancelRequestHandler)
        container.register_singleton(CompleteRequestHandler)
    except Exception as e:
        logger = container.get(LoggingPort)
        logger.warning(f"Failed to register some request command handlers: {e}")


def _register_template_command_handlers(container: DIContainer) -> None:
    """Register template-related command handlers."""
    
    # Import template command handlers
    try:
        from src.application.commands.template_handlers import (
            CreateTemplateHandler,
            UpdateTemplateHandler,
            DeleteTemplateHandler,
            ValidateTemplateHandler
        )
        
        # Use direct registration with @injectable decorator
        container.register_singleton(CreateTemplateHandler)
        container.register_singleton(UpdateTemplateHandler)
        container.register_singleton(DeleteTemplateHandler)
        container.register_singleton(ValidateTemplateHandler)
    except ImportError as e:
        logger = container.get(LoggingPort)
        logger.debug(f"Template command handlers not available: {e}")


def _register_system_command_handlers(container: DIContainer) -> None:
    """Register system-related command handlers."""
    
    # Import system command handlers
    try:
        from src.application.commands.system_handlers import (
            MigrateRepositoryHandler,
            HealthCheckHandler,
            CleanupResourcesHandler
        )
        
        container.register_singleton(MigrateRepositoryHandler)
        container.register_singleton(HealthCheckHandler)
        container.register_singleton(CleanupResourcesHandler)
    except ImportError as e:
        logger = container.get(LoggingPort)
        logger.debug(f"System command handlers not available: {e}")


def register_command_handlers_with_bus(container: DIContainer) -> None:
    """Register command handlers with the command bus."""
    
    try:
        command_bus = container.get(CommandBus)
        logger = container.get(LoggingPort)
        
        # Get provider context for strategy handlers
        provider_context = container.get(ProviderContext)
        
        # Register machine command handlers
        from src.application.machine.commands import (
            ConvertMachineStatusCommand,
            ConvertBatchMachineStatusCommand,
            ValidateProviderStateCommand,
            UpdateMachineStatusCommand,
            CleanupMachineResourcesCommand
        )
        
        command_bus.register(
            ConvertMachineStatusCommand,
            container.get(ConvertMachineStatusCommandHandler)
        )
        
        command_bus.register(
            ConvertBatchMachineStatusCommand,
            container.get(ConvertBatchMachineStatusCommandHandler)
        )
        
        command_bus.register(
            ValidateProviderStateCommand,
            container.get(ValidateProviderStateCommandHandler)
        )
        
        command_bus.register(
            UpdateMachineStatusCommand,
            container.get(UpdateMachineStatusCommandHandler)
        )
        
        command_bus.register(
            CleanupMachineResourcesCommand,
            container.get(CleanupMachineResourcesCommandHandler)
        )
        
        # Register request command handlers
        try:
            from src.application.dto.commands import (
                CreateRequestCommand,
                CreateReturnRequestCommand,
                UpdateRequestStatusCommand,
                CancelRequestCommand,
                CleanupOldRequestsCommand
            )
            
            from src.application.commands.request_handlers import (
                CreateMachineRequestHandler,
                CreateReturnRequestHandler,
                UpdateRequestStatusHandler,
                CancelRequestHandler
            )
            
            command_bus.register(
                CreateRequestCommand,
                container.get(CreateMachineRequestHandler)
            )
            
            command_bus.register(
                CreateReturnRequestCommand,
                container.get(CreateReturnRequestHandler)
            )
            
            command_bus.register(
                UpdateRequestStatusCommand,
                container.get(UpdateRequestStatusHandler)
            )
            
            command_bus.register(
                CancelRequestCommand,
                container.get(CancelRequestHandler)
            )
            
            # Register CleanupOldRequestsCommand if handler exists
            try:
                from src.application.commands.cleanup_handlers import CleanupOldRequestsHandler
                container.register_singleton(CleanupOldRequestsHandler)
                
                command_bus.register(
                    CleanupOldRequestsCommand,
                    container.get(CleanupOldRequestsHandler)
                )
            except (ImportError, Exception) as e:
                logger.debug(f"CleanupOldRequestsHandler not available: {e}")
                
        except Exception as e:
            logger.warning(f"Failed to register request command handlers with bus: {e}")
        
    except Exception as e:
        logger = container.get(LoggingPort)
        logger.warning(f"Failed to register some command handlers: {e}")


def _register_cli_command_handlers(container: DIContainer) -> None:
    """Register CLI command handlers with proper dependency injection."""
    
    # Import CLI handlers
    from src.interface.template_command_handlers import GetAvailableTemplatesCLIHandler
    from src.infrastructure.di.buses import QueryBus, CommandBus
    from src.application.template.format_service import TemplateFormatService
    from src.domain.base.ports import LoggingPort
    
    # Register GetAvailableTemplatesCLIHandler with constructor injection
    container.register_singleton(
        GetAvailableTemplatesCLIHandler,
        lambda c: GetAvailableTemplatesCLIHandler(
            query_bus=c.get(QueryBus),
            command_bus=c.get(CommandBus),
            format_service=c.get(TemplateFormatService),
            logger=c.get(LoggingPort)
        )
    )
