"""Base query handler implementation."""
from abc import abstractmethod
from typing import TypeVar, Generic

from src.infrastructure.handlers.base.base_handler import BaseHandler

T = TypeVar('T')  # Query type
R = TypeVar('R')  # Result type

class BaseQueryHandler(BaseHandler, Generic[T, R]):
    """
    Base class for query handlers.
    
    This class provides common functionality for query handlers,
    including validation, execution, and result formatting.
    """
    
    def __init__(self, logger=None, metrics=None):
        """
        Initialize the query handler.
        
        Args:
            logger: Optional logger instance
            metrics: Optional metrics collector
        """
        super().__init__(logger, metrics)
        
    @abstractmethod
    def handle(self, query: T) -> R:
        """
        Handle a query.
        
        Args:
            query: Query to handle
            
        Returns:
            Query result
        """
        
    def validate(self, query: T) -> None:
        """
        Validate a query.
        
        Args:
            query: Query to validate
            
        Raises:
            ValidationError: If validation fails
        """
        # Default implementation does nothing
        
    def execute(self, query: T) -> R:
        """
        Execute a query with validation and error handling.
        
        Args:
            query: Query to execute
            
        Returns:
            Query result
        """
        # Validate query
        self.validate(query)
        
        # Handle query with logging and metrics
        handle_with_logging = self.with_logging(self.handle)
        handle_with_metrics = self.with_metrics(handle_with_logging)
        
        return handle_with_metrics(query)
        
    def with_caching(self, func, ttl=300, key_func=None):
        """
        Decorator for adding caching to query handlers.
        
        Args:
            func: Function to decorate
            ttl: Time to live in seconds
            key_func: Optional function to generate cache key
            
        Returns:
            Decorated function with caching
        """
        import threading
        import time

        cache = {}
        cache_lock = threading.RLock()
        
        @self.with_logging
        def wrapper(query):
            # Generate cache key
            if key_func:
                cache_key = key_func(query)
            else:
                # Default to string representation of query
                cache_key = str(query)
                
            with cache_lock:
                # Check if result is in cache and not expired
                if cache_key in cache:
                    result, timestamp = cache[cache_key]
                    if time.time() - timestamp < ttl:
                        self.logger.debug(f"Cache hit for {cache_key}")
                        return result
                    else:
                        # Expired, remove from cache
                        self.logger.debug(f"Cache expired for {cache_key}")
                        del cache[cache_key]
                
                # Execute function
                result = func(query)
                
                # Store in cache
                cache[cache_key] = (result, time.time())
                self.logger.debug(f"Cached result for {cache_key}")
                
                return result
                
        return wrapper
