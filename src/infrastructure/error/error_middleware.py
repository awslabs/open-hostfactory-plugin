"""Error handling middleware for the application."""

from typing import Dict, Any, Optional, Callable
import functools
import json

from src.infrastructure.error.exception_handler import ExceptionHandler, get_exception_handler
from src.infrastructure.logging.logger import get_logger

# Configure logger
logger = get_logger(__name__)


class ErrorMiddleware:
    """Middleware for consistent error handling."""

    def __init__(self, error_handler: Optional[ExceptionHandler] = None):
        self._error_handler = error_handler or get_exception_handler()

    def wrap_handler(self, handler_func: Callable) -> Callable:
        """
        Wrap a handler function with error handling.

        Args:
            handler_func: The handler function to wrap

        Returns:
            Wrapped handler function with error handling
        """

        @functools.wraps(handler_func)
        def wrapped_handler(*args, **kwargs):
            try:
                # Execute the original handler
                return handler_func(*args, **kwargs)
            except Exception as e:
                # Handle the error
                error_response = self._error_handler.handle_error_for_http(e)
                return error_response.to_dict()

        return wrapped_handler

    def wrap_api_handler(self, api_handler: Callable) -> Callable:
        """
        Wrap an API handler function with error handling.

        Args:
            api_handler: The API handler function to wrap

        Returns:
            Wrapped API handler function with error handling
        """

        @functools.wraps(api_handler)
        def wrapped_api_handler(input_data: Optional[Dict[str, Any]] = None, **kwargs):
            try:
                # Execute the original API handler
                return api_handler(input_data, **kwargs)
            except Exception as e:
                # Handle the error
                error_response = self._error_handler.handle_error_for_http(e)

                # Format response for Host Factory API
                return {
                    "error": error_response.error_code,
                    "message": error_response.message,
                    "details": error_response.details,
                }

        return wrapped_api_handler

    def wrap_script_handler(self, script_handler: Callable) -> Callable:
        """
        Wrap a script handler function with error handling.

        Args:
            script_handler: The script handler function to wrap

        Returns:
            Wrapped script handler function with error handling
        """

        @functools.wraps(script_handler)
        def wrapped_script_handler(*args, **kwargs):
            try:
                # Execute the original script handler
                return script_handler(*args, **kwargs)
            except Exception as e:
                # Handle the error
                error_response = self._error_handler.handle_error_for_http(e)

                # Format response for script output
                print(
                    json.dumps(
                        {
                            "error": error_response.error_code,
                            "message": error_response.message,
                            "details": error_response.details,
                        },
                        indent=2,
                    )
                )

                # Exit with error code
                import sys

                sys.exit(1)

        return wrapped_script_handler


def with_error_handling(error_handler: Optional[ExceptionHandler] = None):
    """
    Decorator for adding error handling to functions.

    Args:
        error_handler: Optional error handler instance

    Returns:
        Decorator function
    """
    # Create error handler if not provided
    handler = error_handler or get_exception_handler()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_response = handler.handle_error_for_http(e)
                return error_response.to_dict()

        return wrapper

    return decorator


def with_api_error_handling(error_handler: Optional[ExceptionHandler] = None):
    """
    Decorator for adding API-specific error handling to functions.

    Args:
        error_handler: Optional error handler instance

    Returns:
        Decorator function
    """
    # Create error handler if not provided
    handler = error_handler or get_exception_handler()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(input_data: Optional[Dict[str, Any]] = None, **kwargs):
            try:
                return func(input_data, **kwargs)
            except Exception as e:
                error_response = handler.handle_error_for_http(e)

                # Format response for Host Factory API
                return {
                    "error": error_response.error_code,
                    "message": error_response.message,
                    "details": error_response.details,
                }

        return wrapper

    return decorator
