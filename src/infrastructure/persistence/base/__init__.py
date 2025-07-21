"""Base persistence package."""

from src.infrastructure.persistence.base.repository import StrategyBasedRepository
from src.infrastructure.persistence.base.strategy import (
    BaseStorageStrategy,
    StorageStrategy,
)
from src.infrastructure.persistence.base.unit_of_work import (
    BaseUnitOfWork,
    StrategyUnitOfWork,
)

__all__ = [
    "StrategyBasedRepository",
    "BaseUnitOfWork",
    "StrategyUnitOfWork",
    "StorageStrategy",
    "BaseStorageStrategy",
]
