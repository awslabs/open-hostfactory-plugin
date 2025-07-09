"""
CQRS Bus Implementation.

This module provides QueryBus and CommandBus implementations that mediate
between callers and handlers, providing a clean separation of concerns
and enabling cross-cutting concerns like logging, validation, and caching.

Follows SOLID principles:
- Single Responsibility: Each bus handles one type of message
- Open/Closed: Easy to add middleware without changing core logic
- Liskov Substitution: All buses implement same interface pattern
- Interface Segregation: Separate interfaces for queries and commands
- Dependency Inversion: Depends on handler abstractions
"""
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Callable, Generic, List, Optional, TypeVar

from src.application.decorators import (
    get_command_handler_for_type,
    get_query_handler_for_type,
)
from src.application.interfaces.command_query import (
    Command,
    CommandHandler,
    Query,
    QueryHandler,
)
from src.domain.base.ports import LoggingPort
from src.infrastructure.di.container import DIContainer
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

TQuery = TypeVar('TQuery', bound=Query)
TCommand = TypeVar('TCommand', bound=Command)
TResult = TypeVar('TResult')


class BusMiddleware(ABC):
    """Base class for bus middleware."""
    
    @abstractmethod
    async def execute(self, message: Any, next_handler: Callable) -> Any:
        """Execute middleware logic."""
        pass


class LoggingMiddleware(BusMiddleware):
    """Middleware for logging bus operations."""
    
    def __init__(self, logger: LoggingPort):
        self.logger = logger
    
    async def execute(self, message: Any, next_handler: Callable) -> Any:
        """Log bus operations."""
        message_type = type(message).__name__
        start_time = time.time()
        
        self.logger.debug(f"Executing {message_type}")
        
        try:
            result = await next_handler()
            execution_time = time.time() - start_time
            self.logger.debug(f"Completed {message_type} in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Failed {message_type} after {execution_time:.3f}s: {str(e)}")
            raise


class ValidationMiddleware(BusMiddleware):
    """Middleware for validating messages."""
    
    async def execute(self, message: Any, next_handler: Callable) -> Any:
        """Validate message before processing."""
        # Basic validation - can be extended
        if message is None:
            raise ValueError("Message cannot be None")
        
        # If message has validate method, call it
        if hasattr(message, 'validate') and callable(getattr(message, 'validate')):
            message.validate()
        
        return await next_handler()


class QueryBus:
    """
    Bus for handling queries in CQRS architecture.
    
    Provides mediation between query callers and query handlers,
    with support for middleware and cross-cutting concerns.
    """
    
    def __init__(self, container: DIContainer, logger: LoggingPort):
        self.container = container
        self.logger = logger
        self.middleware: List[BusMiddleware] = []
        
        # Add default middleware
        self.add_middleware(LoggingMiddleware(logger))
        self.add_middleware(ValidationMiddleware())
    
    def add_middleware(self, middleware: BusMiddleware) -> None:
        """Add middleware to the bus."""
        self.middleware.append(middleware)
        self.logger.debug(f"Added middleware: {type(middleware).__name__}")
    
    def execute(self, query: TQuery) -> TResult:
        """
        Execute a query through the bus.
        
        Args:
            query: Query to execute
            
        Returns:
            Query result
            
        Raises:
            KeyError: If no handler is registered for the query type
            Exception: If query execution fails
        """
        return self._execute_sync(query)
    
    async def execute_async(self, query: TQuery) -> TResult:
        """
        Execute a query asynchronously through the bus.
        
        Args:
            query: Query to execute
            
        Returns:
            Query result
        """
        return await self._execute_with_middleware(query)
    
    def _execute_sync(self, query: TQuery) -> TResult:
        """Execute query synchronously."""
        try:
            # Get handler for query type
            handler_class = get_query_handler_for_type(type(query))
            handler = self.container.get(handler_class)
            
            # Execute with basic logging
            query_type = type(query).__name__
            self.logger.debug(f"Executing query: {query_type}")
            
            start_time = time.time()
            result = handler.handle(query)
            execution_time = time.time() - start_time
            
            self.logger.debug(f"Query {query_type} completed in {execution_time:.3f}s")
            return result
            
        except KeyError as e:
            self.logger.error(f"No handler registered for query: {type(query).__name__}")
            raise
        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            raise
    
    async def _execute_with_middleware(self, query: TQuery) -> TResult:
        """Execute query with middleware chain."""
        async def final_handler():
            # Get handler for query type
            handler_class = get_query_handler_for_type(type(query))
            handler = self.container.get(handler_class)
            return handler.handle(query)
        
        # Build middleware chain
        handler = final_handler
        for middleware in reversed(self.middleware):
            current_handler = handler
            handler = lambda: middleware.execute(query, current_handler)
        
        return await handler()


class CommandBus:
    """
    Bus for handling commands in CQRS architecture.
    
    Provides mediation between command callers and command handlers,
    with support for middleware and cross-cutting concerns.
    """
    
    def __init__(self, container: DIContainer, logger: LoggingPort):
        self.container = container
        self.logger = logger
        self.middleware: List[BusMiddleware] = []
        
        # Add default middleware
        self.add_middleware(LoggingMiddleware(logger))
        self.add_middleware(ValidationMiddleware())
    
    def add_middleware(self, middleware: BusMiddleware) -> None:
        """Add middleware to the bus."""
        self.middleware.append(middleware)
        self.logger.debug(f"Added middleware: {type(middleware).__name__}")
    
    def execute(self, command: TCommand) -> None:
        """
        Execute a command through the bus.
        
        Args:
            command: Command to execute
            
        Raises:
            KeyError: If no handler is registered for the command type
            Exception: If command execution fails
        """
        self._execute_sync(command)
    
    async def execute_async(self, command: TCommand) -> None:
        """
        Execute a command asynchronously through the bus.
        
        Args:
            command: Command to execute
        """
        await self._execute_with_middleware(command)
    
    def _execute_sync(self, command: TCommand) -> None:
        """Execute command synchronously."""
        try:
            # Get handler for command type
            handler_class = get_command_handler_for_type(type(command))
            handler = self.container.get(handler_class)
            
            # Execute with basic logging
            command_type = type(command).__name__
            self.logger.debug(f"Executing command: {command_type}")
            
            start_time = time.time()
            handler.handle(command)
            execution_time = time.time() - start_time
            
            self.logger.debug(f"Command {command_type} completed in {execution_time:.3f}s")
            
        except KeyError as e:
            self.logger.error(f"No handler registered for command: {type(command).__name__}")
            raise
        except Exception as e:
            self.logger.error(f"Command execution failed: {str(e)}")
            raise
    
    async def _execute_with_middleware(self, command: TCommand) -> None:
        """Execute command with middleware chain."""
        async def final_handler():
            # Get handler for command type
            handler_class = get_command_handler_for_type(type(command))
            handler = self.container.get(handler_class)
            handler.handle(command)
        
        # Build middleware chain
        handler = final_handler
        for middleware in reversed(self.middleware):
            current_handler = handler
            handler = lambda: middleware.execute(command, current_handler)
        
        await handler()


class BusFactory:
    """Factory for creating and configuring buses."""
    
    @staticmethod
    def create_query_bus(container: DIContainer, logger: LoggingPort) -> QueryBus:
        """Create a configured query bus."""
        return QueryBus(container, logger)
    
    @staticmethod
    def create_command_bus(container: DIContainer, logger: LoggingPort) -> CommandBus:
        """Create a configured command bus."""
        return CommandBus(container, logger)
    
    @staticmethod
    def create_buses(container: DIContainer, logger: LoggingPort) -> tuple[QueryBus, CommandBus]:
        """Create both query and command buses."""
        query_bus = BusFactory.create_query_bus(container, logger)
        command_bus = BusFactory.create_command_bus(container, logger)
        return query_bus, command_bus


@contextmanager
def bus_transaction():
    """Context manager for bus transactions (future enhancement)."""
    try:
        yield
    except Exception:
        # Future: Add transaction rollback logic
        raise
