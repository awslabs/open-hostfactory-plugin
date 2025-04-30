# src/infrastructure/persistence/base_repository.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Generic, TypeVar, Type
from datetime import datetime, timedelta
import threading
from contextlib import contextmanager
import logging
from src.infrastructure.persistence.exceptions import StorageError, ConcurrencyError

T = TypeVar('T')  # Generic type for entities

class BaseRepository(ABC, Generic[T]):
    """
    Base repository interface with common functionality.
    
    Provides:
    - Basic CRUD operations
    - Query operations
    - Batch operations
    - Audit logging
    - Generic filtering
    """
    
    def __init__(self):
        """Initialize base repository."""
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def save(self, entity: T) -> None:
        """
        Save an entity.
        
        Args:
            entity: Entity to save
            
        Raises:
            StorageError: If save operation fails
        """
        pass

    @abstractmethod
    def find_by_id(self, entity_id: str) -> Optional[T]:
        """
        Find an entity by ID.
        
        Args:
            entity_id: ID of the entity to find
            
        Returns:
            Entity if found, None otherwise
            
        Raises:
            StorageError: If find operation fails
        """
        pass

    @abstractmethod
    def find_all(self) -> List[T]:
        """
        Find all entities.
        
        Returns:
            List of all entities
            
        Raises:
            StorageError: If find operation fails
        """
        pass

    @abstractmethod
    def delete(self, entity_id: str) -> None:
        """
        Delete an entity.
        
        Args:
            entity_id: ID of the entity to delete
            
        Raises:
            StorageError: If delete operation fails
        """
        pass

    @abstractmethod
    def exists(self, entity_id: str) -> bool:
        """
        Check if an entity exists.
        
        Args:
            entity_id: ID of the entity to check
            
        Returns:
            True if entity exists, False otherwise
            
        Raises:
            StorageError: If check operation fails
        """
        pass

    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """
        Find entities matching criteria.
        
        Args:
            criteria: Dictionary of field-value pairs to match
            
        Returns:
            List of matching entities
            
        Raises:
            StorageError: If find operation fails
        """
        raise NotImplementedError("find_by_criteria must be implemented by storage-specific repository")

    def batch_save(self, entities: List[T]) -> None:
        """
        Save multiple entities in a batch.
        
        Args:
            entities: List of entities to save
            
        Raises:
            StorageError: If batch save operation fails
        """
        raise NotImplementedError("batch_save must be implemented by storage-specific repository")

    def batch_delete(self, entity_ids: List[str]) -> None:
        """
        Delete multiple entities in a batch.
        
        Args:
            entity_ids: List of entity IDs to delete
            
        Raises:
            StorageError: If batch delete operation fails
        """
        raise NotImplementedError("batch_delete must be implemented by storage-specific repository")

    def find_by_field(self, field: str, value: Any) -> List[T]:
        """
        Find entities by a specific field value.
        
        Args:
            field: Field name to match
            value: Value to match
            
        Returns:
            List of matching entities
            
        Raises:
            StorageError: If find operation fails
        """
        return self.find_by_criteria({field: value})

    def create_backup(self) -> str:
        """
        Create a backup of the repository data.
        
        Returns:
            str: Backup identifier or path
            
        Raises:
            StorageError: If backup creation fails
        """
        raise NotImplementedError("create_backup must be implemented by storage-specific repository")

    def restore_from_backup(self, backup_id: str) -> None:
        """
        Restore repository data from a backup.
        
        Args:
            backup_id: Backup identifier or path
            
        Raises:
            StorageError: If restore operation fails
        """
        raise NotImplementedError("restore_from_backup must be implemented by storage-specific repository")

    def cleanup_old_entities(self, max_age_hours: int = 24) -> None:
        """
        Clean up old entities based on age.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
            
        Raises:
            StorageError: If cleanup operation fails
        """
        raise NotImplementedError("cleanup_old_entities must be implemented by storage-specific repository")

class VersionedEntity:
    """Mixin for versioned entities."""
    version: int
    last_modified: datetime

class OptimisticLockingMixin:
    """Mixin for optimistic locking functionality."""
    
    def save_with_version(self, entity: T) -> None:
        """
        Save entity with version checking.
        
        Args:
            entity: Entity to save
            
        Raises:
            ConcurrencyError: If version check fails
            StorageError: If save operation fails
        """
        if not isinstance(entity, VersionedEntity):
            raise ValueError("Entity must implement VersionedEntity")

        with self._lock:
            existing = self.find_by_id(entity.id)
            if existing and existing.version != entity.version:
                raise ConcurrencyError(
                    f"Entity {entity.id} was modified by another process"
                )
            
            entity.version += 1
            entity.last_modified = datetime.utcnow()
            self.save(entity)

class CachingMixin:
    """Mixin for caching functionality."""
    
    def __init__(self, cache_timeout: int = 300):
        """
        Initialize caching mixin.
        
        Args:
            cache_timeout: Cache timeout in seconds
        """
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_timeout = cache_timeout

    def _get_from_cache(self, entity_id: str) -> Optional[T]:
        """
        Get entity from cache if not expired.
        
        Args:
            entity_id: ID of entity to retrieve
            
        Returns:
            Entity if found in cache and not expired, None otherwise
        """
        if entity_id in self._cache:
            timestamp = self._cache_timestamps[entity_id]
            if (datetime.utcnow() - timestamp).total_seconds() < self._cache_timeout:
                return self._cache[entity_id]
            else:
                del self._cache[entity_id]
                del self._cache_timestamps[entity_id]
        return None

    def _add_to_cache(self, entity: T) -> None:
        """
        Add entity to cache.
        
        Args:
            entity: Entity to cache
        """
        entity_id = self._get_entity_id(entity)
        self._cache[entity_id] = entity
        self._cache_timestamps[entity_id] = datetime.utcnow()

    def _clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._cache_timestamps.clear()

    def _get_entity_id(self, entity: T) -> str:
        """
        Get entity ID.
        
        Args:
            entity: Entity to get ID from
            
        Returns:
            String representation of entity ID
        """
        if hasattr(entity, 'id'):
            return str(entity.id)
        elif hasattr(entity, 'request_id'):
            return str(entity.request_id)
        elif hasattr(entity, 'machine_id'):
            return str(entity.machine_id)
        elif hasattr(entity, 'template_id'):
            return str(entity.template_id)
        raise ValueError("Entity has no recognizable ID field")

class OptimisticLockingMixin:
    """Mixin for optimistic locking functionality."""
    
    def __init__(self):
        self._lock = threading.Lock()
        super().__init__()  # Call parent class's __init__

    @contextmanager
    def _optimistic_lock(self):
        """Context manager for optimistic locking."""
        try:
            with self._lock:
                yield
        except Exception as e:
            raise ConcurrencyError(f"Optimistic lock failed: {str(e)}")