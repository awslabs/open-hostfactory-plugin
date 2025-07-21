"""Error handling adapter implementing ErrorHandlingPort."""

from typing import Callable, TypeVar, Optional, Any, List
from functools import wraps
from src.domain.base.ports.error_handling_port import ErrorHandlingPort
from src.infrastructure.error.decorators import handle_exceptions, handle_application_exceptions
from src.domain.base.exceptions import DomainException
from src.infrastructure.di.decorators import injectable

T = TypeVar("T")


@injectable
class ErrorHandlingAdapter(ErrorHandlingPort):
    """Adapter that implements ErrorHandlingPort using infrastructure error handling."""

    def __init__(self):
        """Initialize the error handling adapter."""
        pass

    def handle_exceptions(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for handling exceptions in application methods."""
        return handle_application_exceptions(context="application_service")(func)

    def log_errors(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for logging errors."""
        # Use the general handle_exceptions decorator for logging
        return handle_exceptions(context="error_logging", layer="application")(func)

    def retry_on_failure(self, max_retries: int = 3, delay: float = 1.0) -> Callable:
        """Decorator for retrying operations on failure."""

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exception = None
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_retries:
                            import time

                            time.sleep(delay)
                        else:
                            raise last_exception
                return None  # Should never reach here

            return wrapper

        return decorator

    def handle_domain_exceptions(self, exception: Exception) -> Optional[str]:
        """Handle domain-specific exceptions and return error message."""
        if isinstance(exception, DomainException):
            return str(exception)
        return None
