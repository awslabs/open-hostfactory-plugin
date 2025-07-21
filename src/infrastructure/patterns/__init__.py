"""Infrastructure patterns package."""

from src.infrastructure.patterns.singleton_access import get_singleton
from src.infrastructure.patterns.singleton_registry import SingletonRegistry

__all__ = ["SingletonRegistry", "get_singleton"]
