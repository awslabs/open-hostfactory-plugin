"""Machine domain exceptions."""

from src.domain.base.exceptions import DomainException, ValidationError, EntityNotFoundError


class MachineException(DomainException):
    """Base exception for machine domain errors."""


class MachineNotFoundError(EntityNotFoundError):
    """Raised when a machine is not found."""

    def __init__(self, machine_id: str):
        super().__init__("Machine", machine_id)


class MachineValidationError(ValidationError):
    """Raised when machine validation fails."""


class InvalidMachineStateError(MachineException):
    """Raised when attempting an invalid state transition."""

    def __init__(self, current_state: str, attempted_state: str):
        message = f"Cannot transition from {current_state} to {attempted_state}"
        super().__init__(
            message,
            "INVALID_STATE_TRANSITION",
            {"current_state": current_state, "attempted_state": attempted_state},
        )


class MachineProvisioningError(MachineException):
    """Raised when machine provisioning fails."""
