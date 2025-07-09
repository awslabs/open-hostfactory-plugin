"""Provider Strategy Command Handlers - CQRS handlers for provider strategy commands.

This module implements command handlers for provider strategy operations,
integrating the existing provider strategy ecosystem with the CQRS architecture.
"""

from typing import Dict, Any
import time

from src.application.interfaces.command_query import CommandHandler
from src.application.provider.commands import (
    SelectProviderStrategyCommand,
    ExecuteProviderOperationCommand,
    RegisterProviderStrategyCommand,
    UpdateProviderHealthCommand,
    ConfigureProviderStrategyCommand
)

from src.providers.base.strategy import (
    ProviderContext,
    ProviderResult,
    SelectionPolicy,
    SelectorFactory
)

from src.domain.base.ports import EventPublisherPort, LoggingPort
from src.domain.base.events.provider_events import (
    ProviderStrategySelectedEvent,
    ProviderOperationExecutedEvent,
    ProviderHealthChangedEvent,
    ProviderStrategyRegisteredEvent
)

from src.domain.base.dependency_injection import injectable
# Logging through LoggingPort (Clean Architecture compliant)


@injectable
class SelectProviderStrategyHandler(CommandHandler):
    """Handler for selecting optimal provider strategy."""
    
    def __init__(self, 
                 provider_context: ProviderContext,
                 event_publisher: EventPublisherPort,
                 logger: LoggingPort):
        self._provider_context = provider_context
        self._event_publisher = event_publisher
        self._logger = logger
    
    
    def handle(self, command: SelectProviderStrategyCommand) -> Dict[str, Any]:
        """Handle provider strategy selection command."""
        self._logger.info(f"Selecting provider strategy for operation: {command.operation_type}")
        
        try:
            # Use existing provider context to select strategy
            selector = SelectorFactory.create_selector(
                SelectionPolicy.CAPABILITY_BASED,  # Use capability-based selection
                self._logger
            )
            
            # Get available strategies from context
            available_strategies = self._provider_context.get_available_strategies()
            
            if not available_strategies:
                raise ValueError("No provider strategies available")
            
            # Select optimal strategy based on criteria
            selection_result = selector.select(
                available_strategies,
                command.selection_criteria,
                command.operation_type
            )
            
            if not selection_result.selected_strategy:
                raise ValueError("No suitable provider strategy found")
            
            # Publish strategy selection event
            event = ProviderStrategySelectedEvent(
                strategy_name=selection_result.selected_strategy.name,
                operation_type=command.operation_type,
                selection_criteria=command.selection_criteria,
                selection_reason=selection_result.selection_reason
            )
            self._event_publisher.publish(event)
            
            self._logger.info(f"Selected strategy: {selection_result.selected_strategy.name}")
            
            return {
                "selected_strategy": selection_result.selected_strategy.name,
                "selection_reason": selection_result.selection_reason,
                "confidence_score": selection_result.confidence_score,
                "alternatives": [s.name for s in selection_result.alternative_strategies]
            }
            
        except Exception as e:
            self._logger.error(f"Failed to select provider strategy: {str(e)}")
            raise


@injectable
class ExecuteProviderOperationHandler(CommandHandler):
    """Handler for executing provider operations through strategy pattern."""
    
    def __init__(self,
                 provider_context: ProviderContext,
                 event_publisher: EventPublisherPort,
                 logger: LoggingPort):
        self._provider_context = provider_context
        self._event_publisher = event_publisher
        self._logger = logger
    
    
    def handle(self, command: ExecuteProviderOperationCommand) -> ProviderResult:
        """Handle provider operation execution command."""
        operation = command.operation
        self._logger.info(f"Executing provider operation: {operation.operation_type}")
        
        start_time = time.time()
        
        try:
            # Execute operation through provider context
            if command.strategy_override:
                # Use specific strategy if override provided
                result = self._provider_context.execute_with_strategy(
                    command.strategy_override,
                    operation
                )
            else:
                # Use context's strategy selection
                result = self._provider_context.execute_operation(operation)
            
            execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Publish operation execution event
            event = ProviderOperationExecutedEvent(
                operation_type=operation.operation_type,
                strategy_name=self._provider_context.current_strategy_name,
                success=result.success,
                execution_time_ms=execution_time,
                error_message=result.error_message if not result.success else None
            )
            self._event_publisher.publish(event)
            
            if result.success:
                self._logger.info(f"Operation completed successfully in {execution_time:.2f}ms")
            else:
                self._logger.error(f"Operation failed: {result.error_message}")
            
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self._logger.error(f"Failed to execute provider operation: {str(e)}")
            
            # Publish failure event
            event = ProviderOperationExecutedEvent(
                operation_type=operation.operation_type,
                strategy_name=self._provider_context.current_strategy_name or "unknown",
                success=False,
                execution_time_ms=execution_time,
                error_message=str(e)
            )
            self._event_publisher.publish(event)
            
            # Return error result instead of raising
            return ProviderResult.error_result(
                error_message=str(e),
                error_code="EXECUTION_FAILED"
            )


@injectable
class RegisterProviderStrategyHandler(CommandHandler):
    """Handler for registering new provider strategies."""
    
    def __init__(self,
                 provider_context: ProviderContext,
                 event_publisher: EventPublisherPort,
                 logger: LoggingPort):
        self._provider_context = provider_context
        self._event_publisher = event_publisher
        self._logger = logger
    
    
    def handle(self, command: RegisterProviderStrategyCommand) -> Dict[str, Any]:
        """Handle provider strategy registration command."""
        self._logger.info(f"Registering provider strategy: {command.strategy_name}")
        
        try:
            # Use provider registry to create strategy
            from src.infrastructure.registry.provider_registry import get_provider_registry
            registry = get_provider_registry()
            
            # Create a mock provider config for strategy creation
            from dataclasses import dataclass
            from typing import Dict, Any
            
            @dataclass
            class MockProviderConfig:
                type: str
                name: str
                config: Dict[str, Any]
            
            provider_config = MockProviderConfig(
                type=command.provider_type.lower(),
                name=command.strategy_name,
                config=command.strategy_config
            )
            
            strategy = registry.create_strategy(command.provider_type.lower(), provider_config)
            
            # Register strategy with context
            self._provider_context.register_strategy(strategy, command.strategy_name)
            
            # Publish registration event
            event = ProviderStrategyRegisteredEvent(
                strategy_name=command.strategy_name,
                provider_type=command.provider_type,
                capabilities=command.capabilities or {},
                priority=command.priority
            )
            self._event_publisher.publish(event)
            
            self._logger.info(f"Successfully registered strategy: {command.strategy_name}")
            
            return {
                "strategy_name": command.strategy_name,
                "provider_type": command.provider_type,
                "status": "registered",
                "capabilities": strategy.get_capabilities().model_dump()
            }
            
        except Exception as e:
            self._logger.error(f"Failed to register provider strategy: {str(e)}")
            raise


@injectable
class UpdateProviderHealthHandler(CommandHandler):
    """Handler for updating provider health status."""
    
    def __init__(self,
                 provider_context: ProviderContext,
                 event_publisher: EventPublisherPort,
                 logger: LoggingPort):
        self._provider_context = provider_context
        self._event_publisher = event_publisher
        self._logger = logger
    
    
    def handle(self, command: UpdateProviderHealthCommand) -> Dict[str, Any]:
        """Handle provider health status update command."""
        self._logger.debug(f"Updating health for provider: {command.provider_name}")
        
        try:
            # Get current health status for comparison
            old_status = self._provider_context.get_provider_health(command.provider_name)
            
            # Update health status in context
            self._provider_context.update_provider_health(
                command.provider_name,
                command.health_status
            )
            
            # Publish health change event if status changed
            if old_status is None or old_status.is_healthy != command.health_status.is_healthy:
                event = ProviderHealthChangedEvent(
                    provider_name=command.provider_name,
                    old_status=old_status,
                    new_status=command.health_status,
                    source=command.source
                )
                self._event_publisher.publish(event)
                
                status_change = "healthy" if command.health_status.is_healthy else "unhealthy"
                self._logger.info(f"Provider {command.provider_name} is now {status_change}")
            
            return {
                "provider_name": command.provider_name,
                "health_status": command.health_status.model_dump(),
                "updated_at": command.timestamp or time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            self._logger.error(f"Failed to update provider health: {str(e)}")
            raise


@injectable
class ConfigureProviderStrategyHandler(CommandHandler):
    """Handler for configuring provider strategy policies."""
    
    def __init__(self,
                 provider_context: ProviderContext,
                 event_publisher: EventPublisherPort,
                 logger: LoggingPort):
        self._provider_context = provider_context
        self._event_publisher = event_publisher
        self._logger = logger
    
    
    def handle(self, command: ConfigureProviderStrategyCommand) -> Dict[str, Any]:
        """Handle provider strategy configuration command."""
        self._logger.info("Configuring provider strategy policies")
        
        try:
            # Update provider context configuration
            config_updates = {
                "default_selection_policy": command.default_selection_policy,
                "selection_criteria": command.selection_criteria,
                "fallback_strategies": command.fallback_strategies or [],
                "health_check_interval": command.health_check_interval,
                "circuit_breaker_config": command.circuit_breaker_config or {}
            }
            
            self._provider_context.update_configuration(config_updates)
            
            self._logger.info("Provider strategy configuration updated successfully")
            
            return {
                "status": "configured",
                "configuration": config_updates,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            self._logger.error(f"Failed to configure provider strategy: {str(e)}")
            raise
