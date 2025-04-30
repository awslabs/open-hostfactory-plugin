# src/infrastructure/persistence/json_repository.py
import json
import os
import fcntl
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Type, TypeVar
from contextlib import contextmanager

from src.infrastructure.persistence.base_repository import BaseRepository
from src.infrastructure.persistence.exceptions import StorageError, ConcurrencyError
from src.domain.core.exceptions import ConfigurationError
from src.infrastructure.persistence.base_repository import OptimisticLockingMixin, CachingMixin

T = TypeVar('T')  # Generic type for entities

class JSONRepository(BaseRepository[T], OptimisticLockingMixin, CachingMixin):
    """
    JSON file implementation of repository.
    
    Handles persistence of entities in JSON files with support for:
    - Single file or split file storage
    - File locking for thread safety
    - Optimistic locking for concurrency control
    - Caching for performance optimization
    - Batch operations support
    - Query and filtering capabilities
    
    Storage structure for single file (request_database.json):
    {
        "requests": {
            "req-123": { request_data },
            "req-456": { request_data }
        },
        "machines": {
            "i-abc": { machine_data },
            "i-def": { machine_data }
        }
    }
    
    Storage structure for split files:
    requests.json:
    {
        "requests": {
            "req-123": { request_data },
            "req-456": { request_data }
        }
    }
    
    machines.json:
    {
        "machines": {
            "i-abc": { machine_data },
            "i-def": { machine_data }
        }
    }
    """

    def __init__(self,
                 entity_class: Type[T],
                 storage_path: str,
                 is_single_file: bool,
                 collection_name: str):
        """
        Initialize JSON repository.
        
        Args:
            entity_class: Class type of entities to store
            storage_path: Path to JSON storage file
            is_single_file: Whether to use single file storage
            collection_name: Name of the collection (requests/machines)
        """
        OptimisticLockingMixin.__init__(self)
        CachingMixin.__init__(self)
        
        self._entity_class = entity_class
        self._storage_path = storage_path
        self._is_single_file = is_single_file
        self._collection_name = collection_name
        self._logger = logging.getLogger(__name__)
        
        # Ensure storage exists
        self._ensure_storage()

    @contextmanager
    def _file_lock(self, mode: str = 'r+'):
        """
        File locking context manager.
        
        Args:
            mode: File open mode
                
        Yields:
            File object with lock acquired
            
        Ensures:
            Lock is always released
        """
        if not os.path.exists(self._storage_path):
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            with open(self._storage_path, 'w') as f:
                if self._is_single_file:
                    json.dump({
                        "requests": {},
                        "machines": {}
                    }, f, indent=2)
                else:
                    json.dump({
                        self._collection_name: {}
                    }, f, indent=2)

        with open(self._storage_path, mode) as f:
            try:
                # Get exclusive lock
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                
                # Verify file structure
                try:
                    data = json.load(f)
                    if self._is_single_file:
                        if not all(k in data for k in ["requests", "machines"]):
                            data = {
                                "requests": {},
                                "machines": {}
                            }
                            f.seek(0)
                            f.truncate()
                            json.dump(data, f, indent=2)
                    else:
                        if self._collection_name not in data:
                            data[self._collection_name] = {}
                            f.seek(0)
                            f.truncate()
                            json.dump(data, f, indent=2)
                except json.JSONDecodeError:
                    # File is empty or corrupted, initialize with empty structure
                    data = {
                        "requests": {},
                        "machines": {}
                    } if self._is_single_file else {self._collection_name: {}}
                    f.seek(0)
                    f.truncate()
                    json.dump(data, f, indent=2)

                yield f

            finally:
                # Always release lock
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _ensure_storage(self) -> None:
        """
        Ensure storage file exists with proper structure.
        
        Raises:
            StorageError: If storage initialization fails
        """
        try:
            with self._file_lock('r+') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {} if not self._is_single_file else {
                        "requests": {},
                        "machines": {}
                    }
                    if not self._is_single_file:
                        data[self._collection_name] = {}
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2)
        except Exception as e:
            raise StorageError(f"Failed to initialize storage: {str(e)}")

    def save(self, entity: T) -> None:
        """
        Save an entity with optimistic locking and caching.
        
        Args:
            entity: Entity to save
            
        Raises:
            StorageError: If save operation fails
            ConcurrencyError: If optimistic locking fails
        """
        try:
            entity_id = self._get_entity_id(entity)
            entity_data = self._serialize_entity(entity)
            now = datetime.utcnow()

            with self._file_lock('r+') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {} if not self._is_single_file else {
                        "requests": {},
                        "machines": {}
                    }
                    if not self._is_single_file:
                        data[self._collection_name] = {}

                # Get the collection to work with
                collection = data[self._collection_name] if self._is_single_file else data

                # Check if entity exists
                if str(entity_id) in collection:
                    # For existing entities, perform optimistic locking
                    with self._optimistic_lock():
                        current = collection[str(entity_id)]
                        if current.get('version', 0) != entity_data.get('version', 0):
                            raise ConcurrencyError(f"Entity {entity_id} was modified")
                        
                        # Update version
                        entity_data['version'] = (current.get('version', 0) + 1)
                else:
                    # For new entities, no need for optimistic locking
                    entity_data['version'] = 1

                # Update the entity
                collection[str(entity_id)] = entity_data

                # Write back to file
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2)

            # Update cache
            self._add_to_cache(entity)

        except Exception as e:
            raise StorageError(f"Failed to save entity: {str(e)}")

    def find_by_id(self, entity_id: str) -> Optional[T]:
        """
        Find an entity by ID with caching.
        
        Args:
            entity_id: ID of entity to find
            
        Returns:
            Entity if found, None otherwise
            
        Raises:
            StorageError: If read operation fails
        """
        # Check cache first
        cached = self._get_from_cache(entity_id)
        if cached:
            return cached

        try:
            with self._file_lock('r') as f:
                data = json.load(f)
                
                if self._is_single_file:
                    collection = "requests" if self._collection_name == "requests" else "machines"
                    entity_data = data[collection].get(str(entity_id))
                else:
                    entity_data = data[self._collection_name].get(str(entity_id))

                if entity_data:
                    entity = self._entity_class.from_dict(entity_data)
                    self._add_to_cache(entity)
                    return entity
                return None

        except Exception as e:
            raise StorageError(f"Failed to find entity: {str(e)}")

    def find_all(self) -> List[T]:
        """
        Find all entities.
        
        Returns:
            List of all entities
            
        Raises:
            StorageError: If read operation fails
        """
        try:
            with self._file_lock('r') as f:
                data = json.load(f)
                
                if self._is_single_file:
                    collection = "requests" if self._collection_name == "requests" else "machines"
                    entities_data = data[collection].values()
                else:
                    entities_data = data[self._collection_name].values()

                return [self._entity_class.from_dict(entity_data) 
                       for entity_data in entities_data]

        except Exception as e:
            raise StorageError(f"Failed to find entities: {str(e)}")

    def delete(self, entity_id: str) -> None:
        """
        Delete an entity.
        
        Args:
            entity_id: ID of entity to delete
            
        Raises:
            StorageError: If delete operation fails
        """
        try:
            with self._file_lock('r+') as f:
                data = json.load(f)
                
                if self._is_single_file:
                    collection = "requests" if self._collection_name == "requests" else "machines"
                    if str(entity_id) in data[collection]:
                        del data[collection][str(entity_id)]
                else:
                    if str(entity_id) in data[self._collection_name]:
                        del data[self._collection_name][str(entity_id)]

                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2)

            # Remove from cache
            self._remove_from_cache(entity_id)

        except Exception as e:
            raise StorageError(f"Failed to delete entity: {str(e)}")

    def exists(self, entity_id: str) -> bool:
        """
        Check if an entity exists.
        
        Args:
            entity_id: ID of entity to check
            
        Returns:
            bool: True if entity exists, False otherwise
            
        Raises:
            StorageError: If read operation fails
        """
        try:
            with self._file_lock('r') as f:
                data = json.load(f)
                
                if self._is_single_file:
                    collection = "requests" if self._collection_name == "requests" else "machines"
                    return str(entity_id) in data[collection]
                return str(entity_id) in data[self._collection_name]

        except Exception as e:
            raise StorageError(f"Failed to check entity existence: {str(e)}")

    def batch_save(self, entities: List[T]) -> None:
        """
        Save multiple entities in a batch operation.
        
        Args:
            entities: List of entities to save
            
        Raises:
            StorageError: If batch save operation fails
        """
        try:
            with self._optimistic_lock():
                with self._file_lock('r+') as f:
                    data = json.load(f)
                    
                    if self._is_single_file:
                        collection = "requests" if self._collection_name == "requests" else "machines"
                        for entity in entities:
                            entity_data = entity.to_dict()
                            entity_id = self._get_entity_id(entity)
                            data[collection][entity_id] = entity_data
                            self._add_to_cache(entity)
                    else:
                        for entity in entities:
                            entity_data = entity.to_dict()
                            entity_id = self._get_entity_id(entity)
                            data[self._collection_name][entity_id] = entity_data
                            self._add_to_cache(entity)
                    
                    f.seek(0)
                    f.truncate()
                    json.dump(data, f, indent=2)

        except Exception as e:
            raise StorageError(f"Failed to batch save entities: {str(e)}")

    def batch_delete(self, entity_ids: List[str]) -> None:
        """
        Delete multiple entities in a batch operation.
        
        Args:
            entity_ids: List of entity IDs to delete
            
        Raises:
            StorageError: If batch delete operation fails
        """
        try:
            with self._file_lock('r+') as f:
                data = json.load(f)
                
                if self._is_single_file:
                    collection = "requests" if self._collection_name == "requests" else "machines"
                    for entity_id in entity_ids:
                        if str(entity_id) in data[collection]:
                            del data[collection][str(entity_id)]
                            self._remove_from_cache(entity_id)
                else:
                    for entity_id in entity_ids:
                        if str(entity_id) in data[self._collection_name]:
                            del data[self._collection_name][str(entity_id)]
                            self._remove_from_cache(entity_id)

                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2)

        except Exception as e:
            raise StorageError(f"Failed to batch delete entities: {str(e)}")

    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """
        Find entities matching specified criteria.
        
        Args:
            criteria: Dictionary of field-value pairs to match
            
        Returns:
            List of matching entities
            
        Raises:
            StorageError: If query operation fails
        """
        try:
            entities = self.find_all()
            return [
                entity for entity in entities
                if all(
                    self._match_criterion(getattr(entity, k, None), v)
                    for k, v in criteria.items()
                )
            ]
        except Exception as e:
            raise StorageError(f"Failed to find entities by criteria: {str(e)}")

    def _match_criterion(self, value: Any, criterion: Any) -> bool:
        """Match a single criterion against a value."""
        if hasattr(value, 'value'):  # Handle enum values
            return value.value == criterion
        return value == criterion

    def _serialize_entity(self, entity: T) -> Dict[str, Any]:
        """
        Convert entity to dictionary format.
        
        Args:
            entity: Entity to serialize
            
        Returns:
            Dictionary representation of entity
        """
        if hasattr(entity, 'to_dict'):
            return entity.to_dict()
        return vars(entity)

    def _deserialize_entity(self, data: Dict[str, Any]) -> T:
        """
        Convert dictionary to entity.
        
        Args:
            data: Dictionary data to convert
            
        Returns:
            Entity instance
        """
        if hasattr(self._entity_class, 'from_dict'):
            return self._entity_class.from_dict(data)
        return self._entity_class(**data)