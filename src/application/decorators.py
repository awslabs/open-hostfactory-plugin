"""
Application Layer Decorators for CQRS.

This module provides decorators that belong to the application layer,
following Clean Architecture and DDD principles.

Layer Responsibilities:
- Application: CQRS patterns, handler registration abstractions
- Domain: Business logic, dependency injection abstractions  
- Infrastructure: Concrete implementations, discovery mechanisms
"""
from __future__ import annotations
from typing import Type, TypeVar, Dict, Set
from src.application.interfaces.command_query import QueryHandler, CommandHandler, Query, Command

# Type variables
TQuery = TypeVar('TQuery', bound=Query)
TCommand = TypeVar('TCommand', bound=Command)
TQueryHandler = TypeVar('TQueryHandler', bound=QueryHandler)
TCommandHandler = TypeVar('TCommandHandler', bound=CommandHandler)

# Handler registries (application-level abstractions)
_query_handler_registry: Dict[Type[Query], Type[QueryHandler]] = {}
_command_handler_registry: Dict[Type[Command], Type[CommandHandler]] = {}


def query_handler(query_type: Type[TQuery]):
    """
    Application-layer decorator to mark query handlers.
    
    This decorator belongs in the application layer because it represents
    a CQRS application pattern, not an infrastructure implementation detail.
    
    Usage:
        @query_handler(ListTemplatesQuery)
        @injectable  # Domain-layer DI decorator
        class ListTemplatesHandler(QueryHandler[ListTemplatesQuery, List[TemplateDTO]]):
            ...
    
    Args:
        query_type: The query type this handler processes
        
    Returns:
        Decorated handler class
    """
    def decorator(handler_class: Type[TQueryHandler]) -> Type[TQueryHandler]:
        # Register in application-layer registry
        _query_handler_registry[query_type] = handler_class
        
        # Mark the handler class with metadata for infrastructure discovery
        handler_class._query_type = query_type
        handler_class._is_query_handler = True
        
        return handler_class
    
    return decorator


def command_handler(command_type: Type[TCommand]):
    """
    Application-layer decorator to mark command handlers.
    
    This decorator belongs in the application layer because it represents
    a CQRS application pattern, not an infrastructure implementation detail.
    
    Usage:
        @command_handler(CreateMachineCommand)
        @injectable  # Domain-layer DI decorator
        class CreateMachineHandler(CommandHandler[CreateMachineCommand]):
            ...
    
    Args:
        command_type: The command type this handler processes
        
    Returns:
        Decorated handler class
    """
    def decorator(handler_class: Type[TCommandHandler]) -> Type[TCommandHandler]:
        # Register in application-layer registry
        _command_handler_registry[command_type] = handler_class
        
        # Mark the handler class with metadata for infrastructure discovery
        handler_class._command_type = command_type
        handler_class._is_command_handler = True
        
        return handler_class
    
    return decorator


# Application-layer registry access (for infrastructure to consume)
def get_registered_query_handlers() -> Dict[Type[Query], Type[QueryHandler]]:
    """Get all registered query handlers (for infrastructure consumption)."""
    return _query_handler_registry.copy()


def get_registered_command_handlers() -> Dict[Type[Command], Type[CommandHandler]]:
    """Get all registered command handlers (for infrastructure consumption)."""
    return _command_handler_registry.copy()


def get_query_handler_for_type(query_type: Type[Query]) -> Type[QueryHandler]:
    """Get handler for specific query type."""
    if query_type not in _query_handler_registry:
        raise KeyError(f"No handler registered for query type: {query_type.__name__}")
    return _query_handler_registry[query_type]


def get_command_handler_for_type(command_type: Type[Command]) -> Type[CommandHandler]:
    """Get handler for specific command type."""
    if command_type not in _command_handler_registry:
        raise KeyError(f"No handler registered for command type: {command_type.__name__}")
    return _command_handler_registry[command_type]


def get_handler_registry_stats() -> Dict[str, int]:
    """Get statistics about registered handlers."""
    return {
        'query_handlers': len(_query_handler_registry),
        'command_handlers': len(_command_handler_registry),
        'total_handlers': len(_query_handler_registry) + len(_command_handler_registry)
    }
