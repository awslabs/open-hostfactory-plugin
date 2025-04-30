# src/domain/core/exceptions.py
from typing import Any, Optional, List, Dict

class DomainException(Exception):
    """Base exception for all domain-specific errors."""
    pass

class ValidationError(DomainException):
    """Raised when domain validation fails."""
    def __init__(self, message: str, details: Any = None):
        super().__init__(message)
        self.details = details

class ResourceNotFoundError(DomainException):
    """Raised when a requested resource cannot be found."""
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(f"{resource_type} with ID {resource_id} not found")
        self.resource_type = resource_type
        self.resource_id = resource_id

class ResourceLimitExceededError(DomainException):
    """Raised when attempting to exceed resource limits."""
    def __init__(self, resource_type: str, current: int, maximum: int):
        super().__init__(
            f"Cannot exceed {resource_type} limit: {current}/{maximum}"
        )
        self.resource_type = resource_type
        self.current = current
        self.maximum = maximum

class InvalidStateTransitionError(DomainException):
    """Raised when attempting an invalid state transition."""
    def __init__(self, current_state: str, attempted_state: str):
        super().__init__(
            f"Cannot transition from {current_state} to {attempted_state}"
        )
        self.current_state = current_state
        self.attempted_state = attempted_state

class AWSOperationError(DomainException):
    """Raised when an AWS operation fails."""
    def __init__(self, operation: str, message: str, details: Any = None):
        super().__init__(f"AWS {operation} failed: {message}")
        self.operation = operation
        self.details = details

class ConfigurationError(DomainException):
    """Raised when there's an issue with configuration."""
    def __init__(self, message: str, missing_fields: Optional[List[str]] = None):
        super().__init__(message)
        self.missing_fields = missing_fields or []

class TemplateValidationError(ValidationError):
    """Raised when template validation fails."""
    def __init__(self, template_id: str, errors: Dict[str, str]):
        super().__init__(f"Template validation failed for {template_id}", errors)
        self.template_id = template_id
        self.errors = errors

class RequestValidationError(ValidationError):
    """Raised when request validation fails."""
    def __init__(self, request_id: str, errors: Dict[str, str]):
        super().__init__(f"Request validation failed for {request_id}", errors)
        self.request_id = request_id
        self.errors = errors