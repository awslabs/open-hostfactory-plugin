# src/domain/machine/exceptions.py
from src.domain.core.exceptions import DomainException, ResourceNotFoundError
from typing import Dict

class MachineNotFoundError(ResourceNotFoundError):
    """Raised when a machine cannot be found."""
    def __init__(self, machine_id: str):
        super().__init__("Machine", machine_id)

class MachineValidationError(DomainException):
    """Raised when machine validation fails."""
    def __init__(self, machine_id: str, errors: Dict[str, str]):
        super().__init__(f"Machine validation failed for {machine_id}")
        self.machine_id = machine_id
        self.errors = errors

class InvalidMachineStateError(DomainException):
    """Raised when attempting an invalid machine state transition."""
    def __init__(self, machine_id: str, current_state: str, attempted_state: str):
        super().__init__(
            f"Cannot transition machine {machine_id} from {current_state} to {attempted_state}"
        )
        self.machine_id = machine_id
        self.current_state = current_state
        self.attempted_state = attempted_state

class MachineTerminationError(DomainException):
    """Raised when there's an error terminating a machine."""
    def __init__(self, machine_id: str, message: str):
        super().__init__(f"Failed to terminate machine {machine_id}: {message}")
        self.machine_id = machine_id