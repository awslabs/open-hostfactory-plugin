"""Storage Registry - Registry pattern for storage strategy factories.

This module implements the registry pattern for storage strategy creation,
eliminating hard-coded storage conditionals and enabling true OCP compliance.

The registry ONLY handles storage strategies, maintaining clean separation
from repository concerns.
"""

from typing import Dict, Callable, Optional, List, Any
import threading
from abc import ABC, abstractmethod

from src.domain.base.exceptions import ConfigurationError
from src.infrastructure.logging.logger import get_logger


class UnsupportedStorageError(Exception):
    """Exception raised when an unsupported storage type is requested."""
    pass


class StorageFactoryInterface(ABC):
    """Interface for storage factory functions."""
    
    @abstractmethod
    def create_strategy(self, config: Any) -> Any:
        """Create a storage strategy."""
        pass
    
    @abstractmethod
    def create_config(self, data: Dict[str, Any]) -> Any:
        """Create a storage configuration."""
        pass


class StorageRegistration:
    """Container for storage registration information."""
    
    def __init__(self,
                 storage_type: str,
                 strategy_factory: Callable,
                 config_factory: Callable,
                 unit_of_work_factory: Optional[Callable] = None):
        """
        Initialize storage registration.
        
        Args:
            storage_type: Type identifier for the storage (e.g., 'json', 'sql', 'dynamodb')
            strategy_factory: Factory function to create storage strategy
            config_factory: Factory function to create storage configuration
            unit_of_work_factory: Optional factory function to create unit of work
        """
        self.storage_type = storage_type
        self.strategy_factory = strategy_factory
        self.config_factory = config_factory
        self.unit_of_work_factory = unit_of_work_factory
        
    def __repr__(self) -> str:
        return f"StorageRegistration(type='{self.storage_type}')"


class StorageRegistry:
    """
    Registry for storage strategy factories.
    
    This class implements the registry pattern for storage strategy creation,
    eliminating hard-coded storage conditionals and enabling easy addition
    of new storage types without modifying existing code.
    
    The registry maintains clean separation of concerns by ONLY handling
    storage strategies, not repositories.
    
    Thread-safe singleton implementation.
    """
    
    _instance: Optional['StorageRegistry'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'StorageRegistry':
        """Ensure singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize storage registry."""
        if hasattr(self, '_initialized'):
            return
            
        self._registrations: Dict[str, StorageRegistration] = {}
        self._registry_lock = threading.Lock()
        self.logger = get_logger(__name__)
        self._initialized = True
        
        self.logger.debug("Storage registry initialized")
    
    def register_storage(self,
                        storage_type: str,
                        strategy_factory: Callable,
                        config_factory: Callable,
                        unit_of_work_factory: Optional[Callable] = None) -> None:
        """
        Register a storage type with its factories.
        
        Args:
            storage_type: Type identifier for the storage (e.g., 'json', 'sql')
            strategy_factory: Factory function to create storage strategy
            config_factory: Factory function to create storage configuration
            unit_of_work_factory: Optional factory function to create unit of work
            
        Raises:
            ConfigurationError: If storage type is already registered
        """
        with self._registry_lock:
            if storage_type in self._registrations:
                raise ConfigurationError(f"Storage type '{storage_type}' is already registered")
            
            registration = StorageRegistration(
                storage_type=storage_type,
                strategy_factory=strategy_factory,
                config_factory=config_factory,
                unit_of_work_factory=unit_of_work_factory
            )
            
            self._registrations[storage_type] = registration
            
            self.logger.info(f"Registered storage type: {storage_type}")
            self.logger.debug(f"Storage registration: {registration}")
    
    def create_strategy(self, storage_type: str, config: Any) -> Any:
        """
        Create a storage strategy for the given type and configuration.
        
        Args:
            storage_type: Type of storage to create
            config: Configuration for the storage strategy
            
        Returns:
            Storage strategy instance
            
        Raises:
            UnsupportedStorageError: If storage type is not registered
        """
        registration = self._get_registration(storage_type)
        
        try:
            strategy = registration.strategy_factory(config)
            self.logger.debug(f"Created storage strategy for type: {storage_type}")
            return strategy
        except Exception as e:
            error_msg = f"Failed to create storage strategy for type '{storage_type}': {str(e)}"
            self.logger.error(error_msg)
            raise ConfigurationError(error_msg) from e
    
    def create_config(self, storage_type: str, data: Dict[str, Any]) -> Any:
        """
        Create a storage configuration for the given type and data.
        
        Args:
            storage_type: Type of storage
            data: Configuration data
            
        Returns:
            Storage configuration instance
            
        Raises:
            UnsupportedStorageError: If storage type is not registered
        """
        registration = self._get_registration(storage_type)
        
        try:
            config = registration.config_factory(data)
            self.logger.debug(f"Created storage config for type: {storage_type}")
            return config
        except Exception as e:
            error_msg = f"Failed to create storage config for type '{storage_type}': {str(e)}"
            self.logger.error(error_msg)
            raise ConfigurationError(error_msg) from e
    
    def create_unit_of_work(self, storage_type: str, config: Any) -> Any:
        """
        Create a unit of work for the given storage type.
        
        Args:
            storage_type: Type of storage
            config: Configuration for the unit of work
            
        Returns:
            Unit of work instance
            
        Raises:
            UnsupportedStorageError: If storage type is not registered or no UoW factory
        """
        registration = self._get_registration(storage_type)
        
        if registration.unit_of_work_factory is None:
            raise UnsupportedStorageError(
                f"Unit of work factory not registered for storage type '{storage_type}'"
            )
        
        try:
            unit_of_work = registration.unit_of_work_factory(config)
            self.logger.debug(f"Created unit of work for storage type: {storage_type}")
            return unit_of_work
        except Exception as e:
            error_msg = f"Failed to create unit of work for storage type '{storage_type}': {str(e)}"
            self.logger.error(error_msg)
            raise ConfigurationError(error_msg) from e
        """
        Get list of registered storage types.
        
        Returns:
            List of registered storage type names
        """
        with self._registry_lock:
            return list(self._registrations.keys())
    
    def is_storage_registered(self, storage_type: str) -> bool:
        """
        Check if a storage type is registered.
        
        Args:
            storage_type: Type of storage to check
            
        Returns:
            True if storage type is registered, False otherwise
        """
        with self._registry_lock:
            return storage_type in self._registrations
    
    def clear_registrations(self) -> None:
        """
        Clear all storage registrations.
        
        This method is primarily for testing purposes.
        """
        with self._registry_lock:
            self._registrations.clear()
            self.logger.debug("Cleared all storage registrations")
    
    def _get_registration(self, storage_type: str) -> StorageRegistration:
        """
        Get storage registration for the given type.
        
        Args:
            storage_type: Type of storage
            
        Returns:
            Storage registration
            
        Raises:
            UnsupportedStorageError: If storage type is not registered
        """
        with self._registry_lock:
            if storage_type not in self._registrations:
                available_types = list(self._registrations.keys())
                raise UnsupportedStorageError(
                    f"Storage type '{storage_type}' is not registered. "
                    f"Available types: {available_types}"
                )
            
            return self._registrations[storage_type]


# Global registry instance
_storage_registry: Optional[StorageRegistry] = None


def get_storage_registry() -> StorageRegistry:
    """
    Get the global storage registry instance.
    
    Returns:
        Storage registry singleton instance
    """
    global _storage_registry
    if _storage_registry is None:
        _storage_registry = StorageRegistry()
    return _storage_registry


def reset_storage_registry() -> None:
    """
    Reset the global storage registry instance.
    
    This function is primarily for testing purposes.
    """
    global _storage_registry
    _storage_registry = None
