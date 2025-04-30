# src/infrastructure/persistence/sqlite_repository.py
from typing import Dict, Any, List, Optional, Type, TypeVar
from datetime import datetime, timedelta
import sqlite3
import json
import os
from contextlib import contextmanager
import threading
from src.infrastructure.persistence.base_repository import BaseRepository, OptimisticLockingMixin, CachingMixin
from src.infrastructure.persistence.exceptions import StorageError, ConcurrencyError

T = TypeVar('T')

class SQLiteRepository(BaseRepository[T], OptimisticLockingMixin, CachingMixin):
    """
    SQLite implementation of repository.
    
    Handles persistence of entities in SQLite with support for:
    - Automatic schema management
    - Transaction support
    - Optimistic locking
    - Automatic backups
    - Audit logging
    - Migration support
    - Index management
    """

    def __init__(self, 
                 entity_class: Type[T],
                 collection_name: str,
                 db_path: str,
                 backup_enabled: bool = True,
                 max_backups: int = 5,
                 enable_wal: bool = True):
        """
        Initialize SQLite repository.
        
        Args:
            entity_class: Class type of the entities to store
            collection_name: Name of the collection (used for table naming)
            db_path: Path to SQLite database file
            backup_enabled: Whether to enable automatic backups
            max_backups: Maximum number of backup files to keep
            enable_wal: Whether to enable Write-Ahead Logging
        """
        # Initialize all parent classes
        BaseRepository.__init__(self)
        OptimisticLockingMixin.__init__(self)
        CachingMixin.__init__(self)
        
        self._entity_class = entity_class
        self._collection_name = collection_name
        self._db_path = os.path.expandvars(db_path)
        self._backup_enabled = backup_enabled
        self._max_backups = max_backups
        self._backup_dir = os.path.join(os.path.dirname(self._db_path), 'backups')
        
        # Thread-local storage for connections
        self._local = threading.local()
        
        # Ensure database directory exists
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        if backup_enabled:
            os.makedirs(self._backup_dir, exist_ok=True)
        
        # Initialize database
        self._init_database(enable_wal)

    @contextmanager
    def _get_connection(self, autocommit: bool = True):
        """
        Get a database connection with automatic closing.
        
        Args:
            autocommit: Whether to automatically commit after each operation
        """
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self._db_path)
            self._local.connection.row_factory = sqlite3.Row
            
            if autocommit:
                self._local.connection.isolation_level = None
            
            # Enable foreign keys
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        
        try:
            yield self._local.connection
        except Exception as e:
            self._local.connection.rollback()
            raise StorageError(f"Database error: {str(e)}")

    def _init_database(self, enable_wal: bool) -> None:
        """Initialize database schema and configuration."""
        with self._get_connection() as conn:
            # Enable WAL mode if requested
            if enable_wal:
                conn.execute("PRAGMA journal_mode=WAL")
            
            # Create main entity table
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._collection_name} (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    status TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes
            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self._collection_name}_status 
                ON {self._collection_name}(status)
            """)
            
            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self._collection_name}_updated 
                ON {self._collection_name}(updated_at)
            """)

            # Create audit log table
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._collection_name}_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    data TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (entity_id) REFERENCES {self._collection_name}(id)
                )
            """)

            conn.commit()

    def save(self, entity: T) -> None:
        """Save an entity with optimistic locking and audit logging."""
        with self._get_connection(autocommit=False) as conn:
            try:
                cursor = conn.cursor()
                entity_id = self._get_entity_id(entity)
                entity_data = json.dumps(self._serialize_entity(entity))
                now = datetime.utcnow()

                # Extract status for indexing if available
                status = None
                if hasattr(entity, 'status'):
                    status = entity.status.value if hasattr(entity.status, 'value') else str(entity.status)

                # Check if entity exists
                cursor.execute(
                    f"SELECT version FROM {self._collection_name} WHERE id = ?",
                    (entity_id,)
                )
                existing = cursor.fetchone()

                if existing:
                    # Update existing entity with version check
                    current_version = existing[0]
                    if hasattr(entity, 'version') and entity.version != current_version:
                        raise ConcurrencyError(f"Entity {entity_id} was modified by another process")

                    new_version = current_version + 1
                    cursor.execute(
                        f"""
                        UPDATE {self._collection_name}
                        SET data = ?, version = ?, status = ?, updated_at = ?
                        WHERE id = ? AND version = ?
                        """,
                        (entity_data, new_version, status, now, entity_id, current_version)
                    )

                    # Save audit record
                    self._save_audit_record(cursor, entity_id, "UPDATE", entity_data, new_version)
                else:
                    # Insert new entity
                    cursor.execute(
                        f"""
                        INSERT INTO {self._collection_name} 
                        (id, data, version, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (entity_id, entity_data, 1, status, now, now)
                    )

                    # Save audit record
                    self._save_audit_record(cursor, entity_id, "INSERT", entity_data, 1)

                conn.commit()

                # Update cache
                self._add_to_cache(entity)

            except sqlite3.Error as e:
                conn.rollback()
                raise StorageError(f"Database error: {str(e)}")

    def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find an entity by ID with caching."""
        # Check cache first
        cached = self._get_from_cache(entity_id)
        if cached:
            return cached

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT data FROM {self._collection_name} WHERE id = ?",
                (str(entity_id),)
            )
            row = cursor.fetchone()

            if row:
                entity = self._deserialize_entity(json.loads(row[0]))
                self._add_to_cache(entity)
                return entity

            return None

    def find_all(self) -> List[T]:
        """Find all entities."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT data FROM {self._collection_name}")
            return [
                self._deserialize_entity(json.loads(row[0]))
                for row in cursor.fetchall()
            ]

    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """Find entities matching criteria using SQL."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query dynamically
            conditions = []
            params = []
            
            for key, value in criteria.items():
                if key == 'status':
                    conditions.append("status = ?")
                    params.append(value)
                else:
                    conditions.append(f"json_extract(data, '$.{key}') = ?")
                    params.append(json.dumps(value) if isinstance(value, (dict, list)) else value)

            query = f"SELECT data FROM {self._collection_name}"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            cursor.execute(query, params)
            return [
                self._deserialize_entity(json.loads(row[0]))
                for row in cursor.fetchall()
            ]

    def batch_save(self, entities: List[T]) -> None:
        """Save multiple entities in a batch transaction."""
        with self._get_connection(autocommit=False) as conn:
            try:
                cursor = conn.cursor()
                now = datetime.utcnow()

                for entity in entities:
                    entity_id = self._get_entity_id(entity)
                    entity_data = json.dumps(self._serialize_entity(entity))
                    status = None
                    if hasattr(entity, 'status'):
                        status = entity.status.value if hasattr(entity.status, 'value') else str(entity.status)

                    cursor.execute(
                        f"""
                        INSERT INTO {self._collection_name} 
                        (id, data, version, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                        data = excluded.data,
                        version = version + 1,
                        status = excluded.status,
                        updated_at = excluded.updated_at
                        """,
                        (entity_id, entity_data, 1, status, now, now)
                    )

                    # Save audit record
                    self._save_audit_record(cursor, entity_id, "BATCH_SAVE", entity_data, 1)

                conn.commit()

                # Update cache
                for entity in entities:
                    self._add_to_cache(entity)

            except sqlite3.Error as e:
                conn.rollback()
                raise StorageError(f"Database error during batch save: {str(e)}")

    def batch_delete(self, entity_ids: List[str]) -> None:
        """Delete multiple entities in a batch transaction."""
        with self._get_connection(autocommit=False) as conn:
            try:
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(entity_ids))
                
                # Save audit records before deletion
                cursor.execute(
                    f"SELECT id, data, version FROM {self._collection_name} WHERE id IN ({placeholders})",
                    entity_ids
                )
                for row in cursor.fetchall():
                    self._save_audit_record(cursor, row[0], "DELETE", row[1], row[2])

                # Perform deletion
                cursor.execute(
                    f"DELETE FROM {self._collection_name} WHERE id IN ({placeholders})",
                    entity_ids
                )

                conn.commit()

                # Remove from cache
                for entity_id in entity_ids:
                    if entity_id in self._cache:
                        del self._cache[entity_id]
                        del self._cache_timestamps[entity_id]

            except sqlite3.Error as e:
                conn.rollback()
                raise StorageError(f"Database error during batch delete: {str(e)}")

    def create_backup(self) -> str:
        """Create a backup of the database."""
        if not self._backup_enabled:
            raise StorageError("Backups are not enabled")

        try:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(
                self._backup_dir,
                f"{os.path.basename(self._db_path)}_{timestamp}.bak"
            )

            with self._get_connection() as conn:
                backup = sqlite3.connect(backup_path)
                conn.backup(backup)
                backup.close()

            self._cleanup_old_backups()
            return backup_path

        except Exception as e:
            raise StorageError(f"Failed to create backup: {str(e)}")

    def restore_from_backup(self, backup_path: str) -> None:
        """Restore database from a backup."""
        if not os.path.exists(backup_path):
            raise StorageError(f"Backup file not found: {backup_path}")

        try:
            # Create a new connection to the backup
            backup = sqlite3.connect(backup_path)
            
            with self._get_connection() as conn:
                backup.backup(conn)
            
            backup.close()
            self._clear_cache()

        except Exception as e:
            raise StorageError(f"Failed to restore from backup: {str(e)}")

    def _save_audit_record(self, cursor: sqlite3.Cursor, entity_id: str, operation: str, data: str, version: int) -> None:
        """Save an audit record."""
        cursor.execute(
            f"""
            INSERT INTO {self._collection_name}_audit 
            (entity_id, operation, data, version)
            VALUES (?, ?, ?, ?)
            """,
            (entity_id, operation, data, version)
        )

    def get_audit_log(self, 
                     entity_id: Optional[str] = None,
                     start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get audit log entries with filtering."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = f"SELECT * FROM {self._collection_name}_audit WHERE 1=1"
            params = []

            if entity_id:
                query += " AND entity_id = ?"
                params.append(entity_id)

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())

            query += " ORDER BY timestamp DESC"

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_entities(self, max_age_hours: int = 24) -> None:
        """Clean up old entities based on age."""
        with self._get_connection(autocommit=False) as conn:
            try:
                cursor = conn.cursor()
                cutoff_time = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()

                # Get entities to delete
                cursor.execute(
                    f"SELECT id, data, version FROM {self._collection_name} WHERE created_at < ?",
                    (cutoff_time,)
                )
                
                # Save audit records and delete
                for row in cursor.fetchall():
                    self._save_audit_record(cursor, row[0], "CLEANUP", row[1], row[2])
                    
                    # Remove from cache
                    if row[0] in self._cache:
                        del self._cache[row[0]]
                        del self._cache_timestamps[row[0]]

                # Delete old entities
                cursor.execute(
                    f"DELETE FROM {self._collection_name} WHERE created_at < ?",
                    (cutoff_time,)
                )

                conn.commit()

            except sqlite3.Error as e:
                conn.rollback()
                raise StorageError(f"Failed to cleanup old entities: {str(e)}")

    def vacuum_database(self) -> None:
        """Optimize database by removing unused space."""
        with self._get_connection() as conn:
            try:
                conn.execute("VACUUM")
            except sqlite3.Error as e:
                raise StorageError(f"Failed to vacuum database: {str(e)}")

    def _cleanup_old_backups(self) -> None:
        """Clean up old backup files keeping only the most recent ones."""
        if not self._backup_enabled:
            return

        try:
            backups = sorted([
                f for f in os.listdir(self._backup_dir)
                if f.startswith(os.path.basename(self._db_path))
            ])
            
            while len(backups) > self._max_backups:
                os.remove(os.path.join(self._backup_dir, backups.pop(0)))

        except Exception as e:
            self._logger.warning(f"Failed to cleanup old backups: {str(e)}")

    def _serialize_entity(self, entity: T) -> Dict[str, Any]:
        """Convert entity to dictionary format."""
        if hasattr(entity, 'to_dict'):
            return entity.to_dict()
        return vars(entity)

    def _deserialize_entity(self, data: Dict[str, Any]) -> T:
        """Convert dictionary to entity."""
        if hasattr(self._entity_class, 'from_dict'):
            return self._entity_class.from_dict(data)
        return self._entity_class(**data)