"""Base command handler implementation."""
from abc import abstractmethod
import json
from typing import Any, Dict, TypeVar, Generic

from src.infrastructure.handlers.base.base_handler import BaseHandler

T = TypeVar('T')  # Command type
R = TypeVar('R')  # Result type

class BaseCommandHandler(BaseHandler, Generic[T, R]):
    """
    Base class for command handlers.
    
    This class provides common functionality for command handlers,
    including validation, execution, and result formatting.
    """
    
    def __init__(self, logger=None, metrics=None):
        """
        Initialize the command handler.
        
        Args:
            logger: Optional logger instance
            metrics: Optional metrics collector
        """
        super().__init__(logger, metrics)
        
    @abstractmethod
    def handle(self, command: T) -> R:
        """
        Handle a command.
        
        Args:
            command: Command to handle
            
        Returns:
            Command result
        """
        
    def validate(self, command: T) -> None:
        """
        Validate a command.
        
        Args:
            command: Command to validate
            
        Raises:
            ValidationError: If validation fails
        """
        # Default implementation does nothing
        
    def execute(self, command: T) -> R:
        """
        Execute a command with validation and error handling.
        
        Args:
            command: Command to execute
            
        Returns:
            Command result
        """
        # Validate command
        self.validate(command)
        
        # Handle command with logging and metrics
        handle_with_logging = self.with_logging(self.handle)
        handle_with_metrics = self.with_metrics(handle_with_logging)
        
        return handle_with_metrics(command)
        
    def format_result(self, result: R) -> Dict[str, Any]:
        """
        Format the command result for response.
        
        Args:
            result: Command result
            
        Returns:
            Formatted result
        """
        # Default implementation returns result as is if it's a dict,
        # or calls to_dict() if available
        if isinstance(result, dict):
            return result
        elif hasattr(result, 'to_dict') and callable(getattr(result, 'to_dict')):
            to_dict_method = getattr(result, 'to_dict')
            return to_dict_method()
        else:
            # Try to convert to a dictionary
            try:
                return json.loads(json.dumps(result))
            except (TypeError, json.JSONDecodeError):
                # If all else fails, return as a simple value
                return {'result': result}
