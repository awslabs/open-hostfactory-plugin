"""
Unified CQRS-aligned base handler hierarchy.

This module provides the single source of truth for all handler base classes,
eliminating the confusion of multiple base handlers across different layers.
Designed to support our CQRS architecture while providing common functionality.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

from src.application.dto.base import BaseCommand, BaseResponse
from src.application.interfaces.command_handler import CommandHandler
from src.application.interfaces.command_query import QueryHandler
from src.domain.base.events import DomainEvent
from src.domain.base.ports import ErrorHandlingPort, EventPublisherPort, LoggingPort
from src.infrastructure.error.exception_handler import InfrastructureErrorResponse

TCommand = TypeVar("TCommand", bound=BaseCommand)
TResponse = TypeVar("TResponse", bound=BaseResponse)
TQuery = TypeVar("TQuery")
TResult = TypeVar("TResult")


class BaseHandler(ABC):
    """
    Root base handler with common cross-cutting concerns.

    Provides unified logging, metrics, error handling, and monitoring
    for all handlers in the system. This eliminates duplication across
    the 4 different base handlers we previously had.
    """

    def __init__(
        self,
        logger: Optional[LoggingPort] = None,
        error_handler: Optional[ErrorHandlingPort] = None,
    ):
        """Initialize base handler with optional logger and error handler."""
        self.logger = logger
        self.error_handler = error_handler
        self._metrics: Dict[str, Any] = {}

    async def handle_with_error_management(
        self, operation: Callable[[], Any], context: str = ""
    ) -> Any:
        """
        Execute operation with proper error handling using ErrorHandlingPort.

        This method provides consistent error handling across all handlers
        using the injected ErrorHandlingPort, maintaining Clean Architecture
        principles and CQRS patterns.

        Args:
            operation: The operation to execute (can be async)
            context: Context string for error reporting

        Returns:
            Result of the operation
        """
        if self.error_handler:
            # Use the ErrorHandlingPort for consistent error management
            @self.error_handler.handle_exceptions
            async def wrapped_operation():
                return await operation()

            return await wrapped_operation()
        else:
            # Fallback for when error handler is not available (testing, etc.)
            try:
                return await operation()
            except Exception as e:
                if self.logger:
                    self.logger.log_domain_event(
                        "error",
                        {
                            "context": context,
                            "error": str(e),
                            "handler": self.__class__.__name__,
                        },
                    )
                raise

    def with_monitoring(self, operation: str) -> Callable:
        """
        Add monitoring to handler operations.

        Provides consistent logging, timing, and error handling
        across all handler operations.
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                operation_id = f"{self.__class__.__name__}.{operation}"

                if self.logger:
                    self.logger.info(f"Starting operation: {operation_id}")

                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time

                    if self.logger:
                        self.logger.info(
                            f"Completed operation: {operation_id} in {duration:.3f}s"
                        )

                    self._metrics[operation_id] = {
                        "duration": duration,
                        "status": "success",
                        "timestamp": datetime.utcnow(),
                    }

                    return result

                except Exception as e:
                    duration = time.time() - start_time

                    if self.logger:
                        self.logger.error(
                            f"Failed operation: {operation_id} in {duration:.3f}s - {str(e)}"
                        )

                    self._metrics[operation_id] = {
                        "duration": duration,
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.utcnow(),
                    }

                    raise

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                if asyncio.iscoroutinefunction(func):
                    return asyncio.run(async_wrapper(*args, **kwargs))
                else:
                    start_time = time.time()
                    operation_id = f"{self.__class__.__name__}.{operation}"

                    if self.logger:
                        self.logger.info(f"Starting operation: {operation_id}")

                    try:
                        result = func(*args, **kwargs)
                        duration = time.time() - start_time

                        if self.logger:
                            self.logger.info(
                                f"Completed operation: {operation_id} in {duration:.3f}s"
                            )

                        return result

                    except Exception as e:
                        duration = time.time() - start_time

                        if self.logger:
                            self.logger.error(
                                f"Failed operation: {operation_id} in {duration:.3f}s - {str(e)}"
                            )

                        raise

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return decorator

    def get_metrics(self) -> Dict[str, Any]:
        """Get handler performance metrics."""
        return self._metrics.copy()

    def handle_error(
        self, error: Exception, context: str
    ) -> InfrastructureErrorResponse:
        """
        Unified error handling for all handlers.

        Creates consistent error responses across all handler types.
        """
        if self.logger:
            self.logger.error(f"Handler error in {context}: {str(error)}")

        return InfrastructureErrorResponse.from_exception(error, context)


class BaseCommandHandler(BaseHandler, CommandHandler[TCommand, TResponse]):
    """
    Base for all CQRS command handlers.

    Provides command-specific functionality including validation,
    event publishing, and transaction management.
    """

    def __init__(
        self,
        logger: Optional[LoggingPort] = None,
        event_publisher: Optional[EventPublisherPort] = None,
        error_handler: Optional[ErrorHandlingPort] = None,
    ):
        super().__init__(logger, error_handler)
        self.event_publisher = event_publisher

    async def handle(self, command: TCommand) -> TResponse:
        """
        Handle command with monitoring and event publishing.

        Template method that provides consistent command handling
        across all command handlers.
        """
        operation_id = f"{self.__class__.__name__}.handle"

        # Execute command directly without error wrapper that causes issues
        return await self._execute_command_with_monitoring(command, operation_id)

    async def _execute_command_with_monitoring(
        self, command: TCommand, operation_id: str
    ) -> TResponse:
        """Execute command with monitoring - separated for error handling."""
        start_time = time.time()

        if self.logger:
            self.logger.info(f"Starting command: {operation_id}")

        # Validate command
        await self.validate_command(command)

        # Execute command
        result = await self.execute_command(command)

        # Publish events if any
        if hasattr(result, "events") and result.events:
            await self.publish_events(result.events)

        # Log completion
        duration = time.time() - start_time
        if self.logger:
            self.logger.info(f"Completed command: {operation_id} in {duration:.3f}s")

        return result

    async def validate_command(self, command: TCommand) -> None:
        """
        Validate command before execution.

        Override in specific handlers for custom validation logic.
        """
        if not command:
            raise ValueError("Command cannot be None")

    @abstractmethod
    async def execute_command(self, command: TCommand) -> TResponse:
        """
        Execute the specific command logic.

        Must be implemented by concrete command handlers.
        """

    async def publish_events(self, events: list[DomainEvent]) -> None:
        """Publish domain events after successful command execution."""
        if self.event_publisher:
            for event in events:
                await self.event_publisher.publish(event)


class BaseQueryHandler(BaseHandler, QueryHandler[TQuery, TResult]):
    """
    Base for all CQRS query handlers.

    Provides query-specific functionality including caching,
    filtering, and result formatting.
    """

    def __init__(
        self,
        logger: Optional[LoggingPort] = None,
        error_handler: Optional[ErrorHandlingPort] = None,
    ):
        super().__init__(logger, error_handler)
        self._cache: Dict[str, Any] = {}

    async def handle(self, query: TQuery) -> TResult:
        """
        Handle query with monitoring and caching.

        Template method that provides consistent query handling
        across all query handlers. Now async for consistency with commands.
        """
        # Apply monitoring
        operation_id = f"{self.__class__.__name__}.handle"
        start_time = time.time()

        if self.logger:
            self.logger.info(f"Starting query: {operation_id}")

        try:
            # Check cache if enabled
            cache_key = self.get_cache_key(query)
            if cache_key and cache_key in self._cache:
                if self.logger:
                    self.logger.debug(f"Cache hit for query: {cache_key}")
                return self._cache[cache_key]

            # Execute query (now async)
            result = await self.execute_query(query)

            # Cache result if enabled
            if cache_key and self.is_cacheable(query, result):
                self._cache[cache_key] = result

            duration = time.time() - start_time
            if self.logger:
                self.logger.info(f"Completed query: {operation_id} in {duration:.3f}s")

            return result

        except Exception as e:
            duration = time.time() - start_time
            if self.logger:
                self.logger.error(
                    f"Failed query: {operation_id} in {duration:.3f}s - {str(e)}"
                )
            raise

    def get_cache_key(self, query: TQuery) -> Optional[str]:
        """
        Generate cache key for query.

        Override in specific handlers to enable caching.
        """
        return None

    def is_cacheable(self, query: TQuery, result: TResult) -> bool:
        """
        Determine if query result should be cached.

        Override in specific handlers for custom caching logic.
        """
        return False

    @abstractmethod
    async def execute_query(self, query: TQuery) -> TResult:
        """
        Execute the specific query logic.

        Must be implemented by concrete query handlers.
        Now async for consistency with command handlers.
        """


class BaseProviderHandler(BaseHandler):
    """
    Base for provider-specific handlers with cloud client management.

    Provides cloud provider functionality including client management,
    retry logic, and provider-specific error handling.
    """

    def __init__(
        self,
        logger: Optional[LoggingPort] = None,
        error_handler: Optional[ErrorHandlingPort] = None,
    ):
        super().__init__(logger, error_handler)
        self.max_retries = 3
        self.retry_delay = 2.0

    async def handle_provider_operation(self, operation: str, **kwargs) -> Any:
        """
        Handle provider operation with retry logic.

        Template method for consistent provider operation handling.
        """
        operation_id = f"{self.__class__.__name__}.{operation}"
        start_time = time.time()

        if self.logger:
            self.logger.info(f"Starting provider operation: {operation_id}")

        for attempt in range(self.max_retries + 1):
            try:
                result = await self.execute_provider_operation(operation, **kwargs)

                duration = time.time() - start_time
                if self.logger:
                    self.logger.info(
                        f"Completed provider operation: {operation_id} in {duration:.3f}s"
                    )

                return result

            except Exception as e:
                if attempt == self.max_retries:
                    duration = time.time() - start_time
                    if self.logger:
                        self.logger.error(
                            f"Failed provider operation: {operation_id} in {duration:.3f}s - {str(e)}"
                        )
                    raise
                else:
                    if self.logger:
                        self.logger.warning(
                            f"Provider operation failed (attempt {attempt + 1}): {str(e)}"
                        )
                    await asyncio.sleep(self.retry_delay * (attempt + 1))

    @abstractmethod
    async def execute_provider_operation(self, operation: str, **kwargs) -> Any:
        """
        Execute the specific provider operation.

        Must be implemented by concrete provider handlers.
        """
