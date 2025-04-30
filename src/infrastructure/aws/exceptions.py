# src/infrastructure/aws/exceptions.py
from src.infrastructure.exceptions import InfrastructureError

class AWSHandlerError(InfrastructureError):
    """Base exception for AWS handler errors."""
    pass

class CapacityError(AWSHandlerError):
    """Raised when there's insufficient capacity."""
    pass

class NetworkError(AWSHandlerError):
    """Raised when there's a network configuration error."""
    pass

class IAMError(AWSHandlerError):
    """Raised when there's an IAM role or permission error."""
    pass

class QuotaError(AWSHandlerError):
    """Raised when AWS service quotas are exceeded."""
    pass

class ResourceNotFoundError(AWSHandlerError):
    """Raised when an AWS resource cannot be found."""
    pass

class ValidationError(AWSHandlerError):
    """Raised when AWS resource validation fails."""
    pass