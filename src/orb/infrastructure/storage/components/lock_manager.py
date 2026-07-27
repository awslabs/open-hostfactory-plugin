"""Locking components for thread-safe storage operations."""

import threading
from collections.abc import Generator
from contextlib import contextmanager

from orb.infrastructure.logging.logger import get_logger


class ReaderWriterLock:
    """
    Reader-writer lock implementation.

    Allows multiple readers to access the resource simultaneously,
    but only one writer at a time, with no readers present.

    IN-PROCESS ONLY: this lock is built on ``threading`` primitives, so it
    serializes readers/writers only among threads of the *same* process. It
    provides no guarantee across separate processes or hosts — a second
    process holds its own independent lock instance and will not observe this
    one. For cross-process write serialization the storage backend itself must
    provide it (the JSON backend uses ``fcntl.flock`` on a sibling lock file;
    SQLite relies on its built-in database-level file locking).
    """

    def __init__(self) -> None:
        """Initialize reader-writer lock."""
        self._readers = 0
        self._writers = 0
        self._read_ready = threading.Condition(threading.RLock())
        self._write_ready = threading.Condition(threading.RLock())
        self.logger = get_logger(__name__)

    def acquire_read(self) -> None:
        """Acquire read lock."""
        with self._read_ready:
            while self._writers > 0:
                self._read_ready.wait()
            self._readers += 1
            self.logger.debug("Read lock acquired. Active readers: %s", self._readers)

    def release_read(self) -> None:
        """Release read lock."""
        with self._read_ready:
            self._readers -= 1
            self.logger.debug("Read lock released. Active readers: %s", self._readers)
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self) -> None:
        """Acquire write lock."""
        with self._write_ready:
            while self._writers > 0 or self._readers > 0:
                self._write_ready.wait()
            self._writers += 1
            self.logger.debug("Write lock acquired")

    def release_write(self) -> None:
        """Release write lock."""
        with self._write_ready:
            self._writers -= 1
            self.logger.debug("Write lock released")
            self._write_ready.notify_all()
            with self._read_ready:
                self._read_ready.notify_all()

    @contextmanager
    def read_lock(self) -> Generator[None, None, None]:
        """Context manager for read lock."""
        self.acquire_read()
        try:
            yield
        finally:
            self.release_read()

    @contextmanager
    def write_lock(self) -> Generator[None, None, None]:
        """Context manager for write lock."""
        self.acquire_write()
        try:
            yield
        finally:
            self.release_write()


class LockManager:
    """
    High-level locking manager for storage operations.

    Provides different locking strategies based on storage type and requirements.

    IN-PROCESS ONLY: every strategy exposed here (``reader_writer``, ``simple``,
    ``none``) is backed by ``threading`` primitives. The acquired locks
    serialize writes among threads WITHIN a single process; they do NOT
    serialize across processes or hosts. Cross-process safety must come from
    the underlying storage backend, not from this manager:

    * JSON backend — wraps its read-modify-write cycle in an ``fcntl.flock``
      exclusive lock on a sibling ``.lock`` file (single-host only).
    * SQLite backend — relies on SQLite's built-in database-level file locking,
      which already serializes writers across processes on the same host.
    * PostgreSQL / MySQL backend — the database server serializes concurrent
      writers; this manager only reduces contention among in-process threads.
    """

    def __init__(self, lock_type: str = "reader_writer") -> None:
        """
        Initialize lock manager.

        Args:
            lock_type: Type of lock to use ("reader_writer", "simple", "none")
        """
        self.lock_type = lock_type
        self.logger = get_logger(__name__)

        self._rw_lock: ReaderWriterLock | None = None
        self._simple_lock: threading.RLock | None = None

        if lock_type == "reader_writer":
            self._rw_lock = ReaderWriterLock()
        elif lock_type == "simple":
            self._simple_lock = threading.RLock()
        elif lock_type == "none":
            pass
        else:
            raise ValueError(f"Unknown lock type: {lock_type}")

    @contextmanager
    def read_lock(self) -> Generator[None, None, None]:
        """Acquire read lock for read operations."""
        if self.lock_type == "reader_writer" and self._rw_lock is not None:
            with self._rw_lock.read_lock():
                yield
        elif self.lock_type == "simple" and self._simple_lock is not None:
            with self._simple_lock:
                yield
        else:  # none
            yield

    @contextmanager
    def write_lock(self) -> Generator[None, None, None]:
        """Acquire write lock for write operations."""
        if self.lock_type == "reader_writer" and self._rw_lock is not None:
            with self._rw_lock.write_lock():
                yield
        elif self.lock_type == "simple" and self._simple_lock is not None:
            with self._simple_lock:
                yield
        else:  # none
            yield

    @contextmanager
    def exclusive_lock(self) -> Generator[None, None, None]:
        """Acquire exclusive lock (alias for write_lock)."""
        with self.write_lock():
            yield
