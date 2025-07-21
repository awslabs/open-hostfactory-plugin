"""
DI Container components package.

This package provides modular dependency injection components:
- ServiceRegistry: Service registration management
- CQRSHandlerRegistry: CQRS handler registration
- DependencyResolver: Dependency resolution engine
"""

from .service_registry import ServiceRegistry
from .cqrs_registry import CQRSHandlerRegistry
from .dependency_resolver import DependencyResolver

__all__ = [
    'ServiceRegistry',
    'CQRSHandlerRegistry',
    'DependencyResolver'
]
