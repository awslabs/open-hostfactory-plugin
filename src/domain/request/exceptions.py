from src.domain.core.exceptions import DomainException, ResourceNotFoundError
from typing import Dict, List

class RequestNotFoundError(ResourceNotFoundError):
    """Raised when a request cannot be found."""
    def __init__(self, request_id: str):
        super().__init__("Request", request_id)

class RequestValidationError(DomainException):
    """Raised when request validation fails."""
    def __init__(self, request_id: str, errors: Dict[str, str]):
        super().__init__(f"Request validation failed for {request_id}")
        self.request_id = request_id
        self.errors = errors

class InvalidRequestStateError(DomainException):
    """Raised when attempting an invalid request state transition."""
    def __init__(self, request_id: str, current_state: str, attempted_state: str):
        super().__init__(
            f"Cannot transition request {request_id} from {current_state} to {attempted_state}"
        )
        self.request_id = request_id
        self.current_state = current_state
        self.attempted_state = attempted_state

class MachineAllocationError(DomainException):
    """Raised when there's an error allocating machines to a request."""
    def __init__(self, request_id: str, message: str):
        super().__init__(f"Machine allocation failed for request {request_id}: {message}")
        self.request_id = request_id