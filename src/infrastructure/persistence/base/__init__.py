"""Base persistence package."""

from src.infrastructure.persistence.base.repository import StrategyBasedRepository
from src.infrastructure.persistence.base.unit_of_work import BaseUnitOfWork, StrategyUnitOfWork
from src.infrastructure.persistence.base.strategy import StorageStrategy, BaseStorageStrategy

__all__ = [
    "StrategyBasedRepository",
    "BaseUnitOfWork",
    "StrategyUnitOfWork",
    "StorageStrategy",
    "BaseStorageStrategy",
]
