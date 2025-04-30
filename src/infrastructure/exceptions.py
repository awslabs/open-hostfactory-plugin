from typing import Optional, Any

class InfrastructureError(Exception):
    """Base exception for infrastructure-related errors."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.details = details

class AWSError(InfrastructureError):
    """Raised when AWS operations fail."""
    pass

class StorageError(InfrastructureError):
    """Raised when storage operations fail."""
    pass

class ConfigurationError(InfrastructureError):
    """Raised when there's an issue with configuration."""
    pass

class ConnectionError(InfrastructureError):
    """Raised when there's a connection issue."""
    pass

class ResourceProvisioningError(InfrastructureError):
    """Raised when resource provisioning fails."""
    pass

class ResourceTerminationError(InfrastructureError):
    """Raised when resource termination fails."""
    pass

class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration is invalid."""
    pass

class CredentialsError(ConfigurationError):
    """Raised when there's an issue with credentials."""
    pass
