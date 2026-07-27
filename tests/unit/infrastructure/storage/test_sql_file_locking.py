"""Tests for SQLite storage concurrent-write serialization.

Parallels ``test_json_file_locking.py`` for the SQL/SQLite backend. Verifies
that:
(a) Two sequential saves of DIFFERENT records to the same database both survive.
(b) Two threads concurrently saving different records both persist (no clobber /
    lost-update).

Unlike the JSON backend — which reimplements cross-process serialization with an
fcntl.flock on a sibling lock file — SQLite serializes writers natively via its
built-in database-level file locking. These tests exercise that path against a
FILE-backed SQLite database in ``tmp_path`` (a ``:memory:`` database is
per-connection and cannot be shared across threads, so it would not exercise the
shared-database locking behaviour under test).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from orb.infrastructure.storage.sql.strategy import SQLStorageStrategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLUMNS = {
    "id": "TEXT PRIMARY KEY",
    "name": "TEXT",
    "value": "INTEGER",
}


def _make_strategy(tmp_path: Path, table_name: str = "entities") -> SQLStorageStrategy:
    """Return a strategy backed by a file-based SQLite DB in tmp_path.

    A file (not ``:memory:``) is required so every thread's connection opens the
    same physical database and SQLite's file locking serializes their writes.
    """
    db_path = str(tmp_path / "test_data.db")
    return SQLStorageStrategy(
        config={"type": "sqlite", "name": db_path},
        table_name=table_name,
        columns=_COLUMNS,
    )


# ---------------------------------------------------------------------------
# (a) No-clobber: two sequential saves of different records both persist
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNoClobberSequential:
    """Two saves of different records must both persist — sequential baseline."""

    def test_two_sequential_saves_both_survive(self, tmp_path: Path) -> None:
        """Save record A, then save record B: both must be readable afterwards."""
        strategy = _make_strategy(tmp_path)

        strategy.save("record-A", {"id": "record-A", "name": "alpha", "value": 1})
        strategy.save("record-B", {"id": "record-B", "name": "beta", "value": 2})

        result = strategy.find_all()
        assert "record-A" in result, "record-A was clobbered"
        assert "record-B" in result, "record-B was clobbered"
        assert result["record-A"]["name"] == "alpha"
        assert result["record-B"]["name"] == "beta"

    def test_update_record_does_not_drop_other_records(self, tmp_path: Path) -> None:
        """Updating one record must not remove pre-existing records."""
        strategy = _make_strategy(tmp_path)

        strategy.save("rec-1", {"id": "rec-1", "name": "first", "value": 1})
        strategy.save("rec-2", {"id": "rec-2", "name": "second", "value": 2})
        # Now update rec-1 — rec-2 must survive
        strategy.save("rec-1", {"id": "rec-1", "name": "updated", "value": 1})

        result = strategy.find_all()
        assert "rec-1" in result, "rec-1 missing after update"
        assert "rec-2" in result, "rec-2 was clobbered by update of rec-1"
        assert result["rec-1"]["name"] == "updated"
        assert result["rec-2"]["name"] == "second"


# ---------------------------------------------------------------------------
# (b) Threaded concurrency: two threads saving different records both survive
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestThreadedConcurrency:
    """SQLite file locking + the in-process lock must prevent write clobber."""

    def test_two_threads_save_different_records_both_survive(self, tmp_path: Path) -> None:
        """Two threads concurrently saving different records must both persist."""
        strategy = _make_strategy(tmp_path)
        errors: list[Exception] = []

        def save_record(entity_id: str, value: int) -> None:
            try:
                for _ in range(5):
                    strategy.save(
                        entity_id,
                        {"id": entity_id, "name": entity_id, "value": value},
                    )
                    time.sleep(0)  # yield to the other thread
            except Exception as exc:  # collected for assertion after join
                errors.append(exc)

        t1 = threading.Thread(target=save_record, args=("thread-A", 100))
        t2 = threading.Thread(target=save_record, args=("thread-B", 200))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors, f"Thread errors: {errors}"
        result = strategy.find_all()
        assert "thread-A" in result, "thread-A record missing after concurrent saves"
        assert "thread-B" in result, "thread-B record missing after concurrent saves"
        assert result["thread-A"]["value"] == 100
        assert result["thread-B"]["value"] == 200

    def test_many_threads_distinct_records_all_survive(self, tmp_path: Path) -> None:
        """N threads each writing a distinct record: every record must persist."""
        strategy = _make_strategy(tmp_path)
        errors: list[Exception] = []
        thread_count = 8

        def save_record(index: int) -> None:
            entity_id = f"rec-{index}"
            try:
                strategy.save(entity_id, {"id": entity_id, "name": entity_id, "value": index})
            except Exception as exc:  # collected for assertion after join
                errors.append(exc)

        threads = [threading.Thread(target=save_record, args=(i,)) for i in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        result = strategy.find_all()
        for i in range(thread_count):
            assert f"rec-{i}" in result, f"rec-{i} missing after concurrent saves"
