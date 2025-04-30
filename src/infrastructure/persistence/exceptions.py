# src/infrastructure/persistence/exceptions.py
class PersistenceError(Exception):
    """Base exception for persistence-related errors."""
    pass

class StorageError(PersistenceError):
    """Raised when there's an error with storage operations."""
    pass

class DataNotFoundError(PersistenceError):
    """Raised when requested data is not found."""
    pass

class ValidationError(PersistenceError):
    """Raised when data validation fails."""
    pass

class ConcurrencyError(PersistenceError):
    """Raised when there's a concurrency conflict during data operations."""
    pass