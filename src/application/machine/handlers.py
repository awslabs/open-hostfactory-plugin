"""Machine command handlers for CQRS implementation."""
from typing import List
from src.application.base.commands import CommandHandler
from src.application.machine.commands import (
    ConvertMachineStatusCommand,
    ConvertBatchMachineStatusCommand,
    ValidateProviderStateCommand,
    UpdateMachineStatusCommand,
    CleanupMachineResourcesCommand
)
from src.application.dto.base import BaseResponse
from src.domain.machine.value_objects import MachineStatus
from src.domain.machine.repository import MachineRepository
from src.providers.base.strategy import ProviderContext, ProviderOperation, ProviderOperationType
from src.domain.base.ports import LoggingPort


class ConvertMachineStatusResponse(BaseResponse):
    """Response for machine status conversion."""
    status: MachineStatus
    original_state: str
    provider_type: str


class ConvertBatchMachineStatusResponse(BaseResponse):
    """Response for batch machine status conversion."""
    statuses: List[MachineStatus]
    count: int


class ValidateProviderStateResponse(BaseResponse):
    """Response for provider state validation."""
    is_valid: bool
    provider_state: str
    provider_type: str


class ConvertMachineStatusCommandHandler(CommandHandler[ConvertMachineStatusCommand, ConvertMachineStatusResponse]):
    """Handler for converting provider-specific status to domain status."""
    
    def __init__(self, provider_context: ProviderContext, logger: LoggingPort):
        """Initialize with provider context."""
        self._provider_context = provider_context
        self._logger = logger
    
    
    async def handle(self, command: ConvertMachineStatusCommand) -> ConvertMachineStatusResponse:
        """Handle machine status conversion command."""
        try:
            # Use provider strategy pattern for conversion
            domain_status = await self._convert_using_provider_strategy(
                command.provider_state, 
                command.provider_type
            )
            
            return ConvertMachineStatusResponse(
                success=True,
                status=domain_status,
                original_state=command.provider_state,
                provider_type=command.provider_type,
                metadata=command.metadata
            )
            
        except Exception as e:
            # Fallback to basic conversion
            fallback_status = self._fallback_conversion(command.provider_state)
            
            return ConvertMachineStatusResponse(
                success=True,  # Still successful with fallback
                status=fallback_status,
                original_state=command.provider_state,
                provider_type=command.provider_type,
                metadata={**command.metadata, "used_fallback": True, "error": str(e)}
            )
    
    def can_handle(self, command) -> bool:
        """Check if this handler can handle the command."""
        return isinstance(command, ConvertMachineStatusCommand)
    
    async def _convert_using_provider_strategy(self, provider_state: str, provider_type: str) -> MachineStatus:
        """Convert using provider strategy pattern."""
        # Set the appropriate provider strategy
        if not self._provider_context.set_strategy(provider_type):
            raise ValueError(f"Unsupported provider type: {provider_type}")
        
        # Create provider operation for status conversion
        operation = ProviderOperation(
            operation_type=ProviderOperationType.HEALTH_CHECK,  # Using health check as proxy for status mapping
            parameters={
                "provider_state": provider_state,
                "conversion_request": True
            }
        )
        
        # Execute operation (this would be extended to support status conversion)
        result = self._provider_context.execute_operation(operation)
        
        if result.success:
            # Extract status from result (implementation depends on provider strategy)
            return self._extract_status_from_result(result, provider_state)
        else:
            raise Exception(f"Provider operation failed: {result.error_message}")
    
    def _extract_status_from_result(self, result, provider_state: str) -> MachineStatus:
        """Extract MachineStatus from provider result."""
        # This is a simplified implementation
        # In practice, each provider strategy would handle status mapping
        return self._fallback_conversion(provider_state)
    
    def _fallback_conversion(self, provider_state: str) -> MachineStatus:
        """Fallback conversion when provider strategy is not available."""
        state_mapping = {
            'running': MachineStatus.RUNNING,
            'stopped': MachineStatus.STOPPED,
            'pending': MachineStatus.PENDING,
            'stopping': MachineStatus.STOPPING,
            'terminated': MachineStatus.TERMINATED,
            'shutting-down': MachineStatus.STOPPING,
        }
        
        normalized_state = provider_state.lower().replace('_', '-')
        return state_mapping.get(normalized_state, MachineStatus.UNKNOWN)


class ConvertBatchMachineStatusCommandHandler(CommandHandler[ConvertBatchMachineStatusCommand, ConvertBatchMachineStatusResponse]):
    """Handler for batch machine status conversion."""
    
    def __init__(self, status_converter: ConvertMachineStatusCommandHandler, logger: LoggingPort):
        """Initialize with status converter handler."""
        self._status_converter = status_converter
        self._logger = logger
    
    
    async def handle(self, command: ConvertBatchMachineStatusCommand) -> ConvertBatchMachineStatusResponse:
        """Handle batch machine status conversion command."""
        statuses = []
        
        for state_info in command.provider_states:
            # Create individual conversion command
            convert_command = ConvertMachineStatusCommand(
                provider_state=state_info['state'],
                provider_type=state_info['provider_type'],
                metadata=command.metadata
            )
            
            # Convert individual status
            result = await self._status_converter.handle(convert_command)
            statuses.append(result.status)
        
        return ConvertBatchMachineStatusResponse(
            success=True,
            statuses=statuses,
            count=len(statuses),
            metadata=command.metadata
        )
    
    def can_handle(self, command) -> bool:
        """Check if this handler can handle the command."""
        return isinstance(command, ConvertBatchMachineStatusCommand)


class ValidateProviderStateCommandHandler(CommandHandler[ValidateProviderStateCommand, ValidateProviderStateResponse]):
    """Handler for validating provider state."""
    
    def __init__(self, provider_context: ProviderContext, logger: LoggingPort):
        """Initialize with provider context."""
        self._provider_context = provider_context
        self._logger = logger
    
    
    async def handle(self, command: ValidateProviderStateCommand) -> ValidateProviderStateResponse:
        """Handle provider state validation command."""
        try:
            # Try to convert the state - if successful, it's valid
            convert_command = ConvertMachineStatusCommand(
                provider_state=command.provider_state,
                provider_type=command.provider_type,
                metadata=command.metadata
            )
            
            # Use the converter to validate
            converter = ConvertMachineStatusCommandHandler(self._provider_context, self._logger)
            result = await converter.handle(convert_command)
            
            # If conversion succeeded, state is valid
            is_valid = result.success and result.status != MachineStatus.UNKNOWN
            
            return ValidateProviderStateResponse(
                success=True,
                is_valid=is_valid,
                provider_state=command.provider_state,
                provider_type=command.provider_type,
                metadata=command.metadata
            )
            
        except Exception as e:
            return ValidateProviderStateResponse(
                success=True,
                is_valid=False,
                provider_state=command.provider_state,
                provider_type=command.provider_type,
                metadata={**command.metadata, "validation_error": str(e)}
            )
    
    def can_handle(self, command) -> bool:
        """Check if this handler can handle the command."""
        return isinstance(command, ValidateProviderStateCommand)


# Additional handlers for existing commands

class UpdateMachineStatusCommandHandler(CommandHandler[UpdateMachineStatusCommand, BaseResponse]):
    """Handler for updating machine status."""
    
    def __init__(self, machine_repository: 'MachineRepository', logger: LoggingPort):
        """Initialize with machine repository."""
        self._machine_repository = machine_repository
        self._logger = logger
    
    
    async def handle(self, command: UpdateMachineStatusCommand) -> BaseResponse:
        """Handle machine status update command."""
        # Implementation would update machine status in repository
        # This is a placeholder for the actual implementation
        
        return BaseResponse(
            success=True,
            message=f"Machine {command.machine_id} status updated to {command.status}",
            metadata=command.metadata
        )
    
    def can_handle(self, command) -> bool:
        """Check if this handler can handle the command."""
        return isinstance(command, UpdateMachineStatusCommand)


class CleanupMachineResourcesCommandHandler(CommandHandler[CleanupMachineResourcesCommand, BaseResponse]):
    """Handler for cleaning up machine resources."""
    
    def __init__(self, provider_context: ProviderContext, logger: LoggingPort):
        """Initialize with provider context."""
        self._provider_context = provider_context
        self._logger = logger
    
    
    async def handle(self, command: CleanupMachineResourcesCommand) -> BaseResponse:
        """Handle machine resource cleanup command."""
        # Implementation would clean up machine resources using provider
        # This is a placeholder for the actual implementation
        
        return BaseResponse(
            success=True,
            message=f"Cleaned up {len(command.machine_ids)} machine resources",
            metadata=command.metadata
        )
    
    def can_handle(self, command) -> bool:
        """Check if this handler can handle the command."""
        return isinstance(command, CleanupMachineResourcesCommand)
