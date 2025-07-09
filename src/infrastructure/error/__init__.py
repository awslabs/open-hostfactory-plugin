"""Error handling infrastructure package."""
from src.infrastructure.error.exception_handler import (
    ExceptionHandler, ErrorResponse, ErrorCategory, ErrorCode, get_exception_handler
)
from src.infrastructure.error.error_middleware import (
    ErrorMiddleware, with_error_handling, with_api_error_handling
)

__all__ = [
    'ExceptionHandler',
    'ErrorResponse',
    'ErrorCategory',
    'ErrorCode',
    'ErrorMiddleware',
    'with_error_handling',
    'with_api_error_handling',
    'get_exception_handler',
    'create_error_middleware'
]

def create_error_middleware() -> ErrorMiddleware:
    """
    Create and configure an error middleware.
    
    Returns:
        Configured ErrorMiddleware instance
    """
    return ErrorMiddleware()
