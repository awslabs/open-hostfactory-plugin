"""Persistence package."""

# Import only the base classes to avoid circular imports
from src.infrastructure.persistence.base import (
    StrategyBasedRepository,
    BaseUnitOfWork,
    StrategyUnitOfWork,
)

# Import factory functions but not classes to avoid circular imports
# (No imports needed from repository_factory to avoid circular dependencies)

__all__ = [
    # Base
    "StrategyBasedRepository",
    "BaseUnitOfWork",
    "StrategyUnitOfWork",
    # Factory functions
]
