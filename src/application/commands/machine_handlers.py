"""Command handlers for machine operations using unified base handler hierarchy."""
from typing import Any, Dict
from src.application.base.handlers import BaseCommandHandler
from src.application.machine.commands import (
    UpdateMachineStatusCommand,
    CleanupMachineResourcesCommand,
    RegisterMachineCommand,
    DeregisterMachineCommand
)
from src.domain.machine.repository import MachineRepository
from src.domain.base.ports import EventPublisherPort, LoggingPort, ErrorHandlingPort

# Exception handling through base handler (Clean Architecture compliant)
from src.domain.base.dependency_injection import injectable


@injectable
class UpdateMachineStatusHandler(BaseCommandHandler[UpdateMachineStatusCommand, None]):
    """Handler for updating machine status using unified base handler."""
    
    def __init__(self, 
                 machine_repository: MachineRepository, 
                 event_publisher: EventPublisherPort, 
                 logger: LoggingPort,
                 error_handler: ErrorHandlingPort):
        super().__init__(logger, event_publisher, error_handler)
        self._machine_repository = machine_repository
    
    async def validate_command(self, command: UpdateMachineStatusCommand) -> None:
        """Validate machine status update command."""
        await super().validate_command(command)
        if not command.machine_id:
            raise ValueError("machine_id is required")
        if not command.status:
            raise ValueError("status is required")
    
    async def execute_command(self, command: UpdateMachineStatusCommand) -> None:
        """Execute machine status update command - error handling via base handler."""
        # Get machine
        machine = await self._machine_repository.get_by_id(command.machine_id)
        if not machine:
            raise ValueError(f"Machine not found: {command.machine_id}")
        
        # Update status
        machine.update_status(command.status, command.metadata)
        
        # Save changes and get extracted events
        events = await self._machine_repository.save(machine)
        
        # Events will be published by the base handler
        return None  # No response needed for this command


@injectable
class CleanupMachineResourcesHandler(BaseCommandHandler[CleanupMachineResourcesCommand, None]):
    """Handler for cleaning up machine resources using unified base handler."""
    
    def __init__(self, 
                 machine_repository: MachineRepository, 
                 event_publisher: EventPublisherPort, 
                 logger: LoggingPort,
                 error_handler: ErrorHandlingPort):
        super().__init__(logger, event_publisher, error_handler)
        self._machine_repository = machine_repository
    
    async def validate_command(self, command: CleanupMachineResourcesCommand) -> None:
        """Validate cleanup command."""
        await super().validate_command(command)
        if not command.machine_id:
            raise ValueError("machine_id is required")
    
    async def execute_command(self, command: CleanupMachineResourcesCommand) -> None:
        """Execute machine cleanup command - error handling via base handler."""
        # Get machine
        machine = await self._machine_repository.get_by_id(command.machine_id)
        if not machine:
            if self.logger:
                self.logger.warning(f"Machine not found for cleanup: {command.machine_id}")
            return None
        
        # Perform cleanup
        machine.cleanup_resources()
        
        # Save changes
        await self._machine_repository.save(machine)
        
        return None


@injectable
class RegisterMachineHandler(BaseCommandHandler[RegisterMachineCommand, None]):
    """Handler for registering machines using unified base handler."""
    
    def __init__(self, 
                 machine_repository: MachineRepository, 
                 event_publisher: EventPublisherPort, 
                 logger: LoggingPort,
                 error_handler: ErrorHandlingPort):
        super().__init__(logger, event_publisher, error_handler)
        self._machine_repository = machine_repository
    
    async def validate_command(self, command: RegisterMachineCommand) -> None:
        """Validate machine registration command."""
        await super().validate_command(command)
        if not command.machine_id:
            raise ValueError("machine_id is required")
        if not command.template_id:
            raise ValueError("template_id is required")
    
    
    async def execute_command(self, command: RegisterMachineCommand) -> None:
        """Execute machine registration command."""
        # Check if machine already exists
        existing_machine = await self._machine_repository.get_by_id(command.machine_id)
        if existing_machine:
            raise ValueError(f"Machine already registered: {command.machine_id}")
        
        # Create new machine
        from src.domain.machine.aggregate import Machine
        machine = Machine.create(
            machine_id=command.machine_id,
            template_id=command.template_id,
            metadata=command.metadata or {}
        )
        
        # Save machine
        await self._machine_repository.save(machine)
        
        return None


@injectable
class DeregisterMachineHandler(BaseCommandHandler[DeregisterMachineCommand, None]):
    """Handler for deregistering machines using unified base handler."""
    
    def __init__(self, 
                 machine_repository: MachineRepository, 
                 event_publisher: EventPublisherPort, 
                 logger: LoggingPort,
                 error_handler: ErrorHandlingPort):
        super().__init__(logger, event_publisher, error_handler)
        self._machine_repository = machine_repository
    
    async def validate_command(self, command: DeregisterMachineCommand) -> None:
        """Validate machine deregistration command."""
        await super().validate_command(command)
        if not command.machine_id:
            raise ValueError("machine_id is required")
    
    
    async def execute_command(self, command: DeregisterMachineCommand) -> None:
        """Execute machine deregistration command."""
        # Get machine
        machine = await self._machine_repository.get_by_id(command.machine_id)
        if not machine:
            if self.logger:
                self.logger.warning(f"Machine not found for deregistration: {command.machine_id}")
            return None
        
        # Deregister machine
        machine.deregister(command.reason)
        
        # Save changes
        await self._machine_repository.save(machine)
        
        return None
