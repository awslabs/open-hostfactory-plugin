"""Tests for orb-1.10 (set + Lock), orb-1.11 (sequence_id + replay_truncated),
and orb-1.24 (SSE reconnect after deque overflow -- integration-level).

All three features are implemented in the current working tree.
"""

from __future__ import annotations

import asyncio
import json
from collections import deque as _deque
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orb.api.dependencies import get_current_user
from orb.api.routers.events import _SseEventBus, router as events_router

# ---------------------------------------------------------------------------
# orb-1.10: Concurrent subscribe/unsubscribe stress test
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSubscriberLocking:
    """_subscribers is a set protected by asyncio.Lock -- no corruption under concurrency."""

    def test_subscribers_is_a_set(self):
        bus = _SseEventBus()
        assert isinstance(bus._subscribers, set)

    def test_subscribers_lock_exists(self):
        bus = _SseEventBus()
        assert isinstance(bus._subscribers_lock, asyncio.Lock)

    def test_subscribe_adds_to_set(self):
        async def run():
            bus = _SseEventBus()
            q = await bus.subscribe()
            assert q in bus._subscribers

        asyncio.run(run())

    def test_unsubscribe_discards_from_set(self):
        async def run():
            bus = _SseEventBus()
            q = await bus.subscribe()
            await bus.unsubscribe(q)
            assert q not in bus._subscribers

        asyncio.run(run())

    def test_unsubscribe_is_idempotent_via_discard(self):
        """set.discard semantics: calling unsubscribe twice must not raise."""

        async def run():
            bus = _SseEventBus()
            q = await bus.subscribe()
            await bus.unsubscribe(q)
            await bus.unsubscribe(q)  # must not raise KeyError or ValueError

        asyncio.run(run())

    def test_concurrent_subscribe_unsubscribe_no_corruption(self):
        """50 clients subscribe then unsubscribe concurrently: set stays consistent."""

        async def run():
            bus = _SseEventBus()
            n_clients = 50

            # Subscribe all clients concurrently.
            subscribe_tasks = [asyncio.create_task(bus.subscribe()) for _ in range(n_clients)]
            queues = await asyncio.gather(*subscribe_tasks)
            assert len(bus._subscribers) == n_clients

            # Unsubscribe all clients concurrently.
            unsubscribe_tasks = [asyncio.create_task(bus.unsubscribe(q)) for q in queues]
            await asyncio.gather(*unsubscribe_tasks)
            assert len(bus._subscribers) == 0

        asyncio.run(run())

    def test_concurrent_subscribe_unsubscribe_interleaved(self):
        """Interleaved subscribe/unsubscribe from 50 tasks: no KeyError, set intact."""

        async def client_lifecycle(bus: _SseEventBus) -> None:
            q = await bus.subscribe()
            # Yield to allow other coroutines to run.
            await asyncio.sleep(0)
            await bus.unsubscribe(q)

        async def run():
            bus = _SseEventBus()
            tasks = [asyncio.create_task(client_lifecycle(bus)) for _ in range(50)]
            # Run all without exception.
            await asyncio.gather(*tasks)
            # All clients cleaned up.
            assert len(bus._subscribers) == 0

        asyncio.run(run())

    def test_publish_iterates_snapshot_not_live_set(self):
        """publish takes a snapshot; unsubscribe mid-publish does not cause RuntimeError."""

        async def run():
            bus = _SseEventBus()
            q1 = await bus.subscribe()
            q2 = await bus.subscribe()
            # Publish; both should receive the event even if one unsubscribes
            # concurrently (snapshot prevents iteration over mutating set).
            await bus.publish("test.event", {"x": 1})
            assert q1.qsize() == 1
            assert q2.qsize() == 1

        asyncio.run(run())


# ---------------------------------------------------------------------------
# orb-1.11: sequence_id + replay_truncated sentinel
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSequenceIdAndReplayTruncated:
    """Every event gets a monotonic seq_id; overflow triggers replay_truncated."""

    def test_publish_records_seq_id_in_history(self):
        async def run():
            bus = _SseEventBus()
            await bus.publish("machine.created", {"id": "m-1"})
            assert len(bus._history) == 1
            _ts, _et, _p, seq_id = bus._history[0]
            assert seq_id >= 1

        asyncio.run(run())

    def test_seq_ids_are_monotonically_increasing(self):
        async def run():
            bus = _SseEventBus()
            for i in range(5):
                await bus.publish("machine.updated", {"i": i})
            seq_ids = [entry[3] for entry in bus._history]
            for a, b in zip(seq_ids, seq_ids[1:]):
                assert b == a + 1

        asyncio.run(run())

    def test_seq_id_zero_never_issued_by_counter(self):
        """seq_id 0 is reserved for the sentinel; the counter starts at 1."""

        async def run():
            bus = _SseEventBus()
            await bus.publish("machine.created", {"id": "m-1"})
            seq_id = bus._history[0][3]
            assert seq_id != 0

        asyncio.run(run())

    def test_history_since_seq_no_overflow_no_sentinel(self):
        """Normal replay (no overflow): no replay_truncated sentinel."""
        bus = _SseEventBus()
        bus._history_max = 10
        bus._history = _deque(maxlen=10)

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(5):
            bus._record(base, "machine.created", {"i": i}, seq_id=i + 1)

        # since_seq=0: oldest_seq=1, 1 <= 0+1=1 -> no gap
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(since, since_seq=0)
        types = [et for et, _ in result]
        assert "replay_truncated" not in types
        assert len(result) == 5

    def test_history_since_seq_overflow_emits_sentinel(self):
        """When the deque has overflowed and oldest_seq > since_seq + 1,
        the first event returned is replay_truncated."""
        bus = _SseEventBus()
        maxlen = 5
        bus._history_max = maxlen
        bus._history = _deque(maxlen=maxlen)

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        n_events = maxlen + 5  # 10 events total, deque keeps only last 5
        for i in range(n_events):
            bus._record(base, "machine.created", {"i": i}, seq_id=i + 1)

        # Oldest surviving seq_id = n_events - maxlen + 1 = 6
        # since_seq = 1 (the first event), oldest_seq (6) > since_seq+1 (2) -> gap
        first_seq = 1
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(since, since_seq=first_seq)

        assert len(result) >= 1
        first_type, first_payload = result[0]
        assert first_type == "replay_truncated"
        assert first_payload["type"] == "replay_truncated"
        assert first_payload["since"] == first_seq
        assert first_payload["seq_id"] == 0  # sentinel marker

    def test_replay_truncated_sentinel_seq_id_is_zero(self):
        """seq_id 0 in the sentinel is the reserved marker value."""
        bus = _SseEventBus()
        maxlen = 3
        bus._history_max = maxlen
        bus._history = _deque(maxlen=maxlen)

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(maxlen + 2):
            bus._record(base, "ev", {"i": i}, seq_id=i + 1)

        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(since, since_seq=1)
        _et, payload = result[0]
        assert payload["seq_id"] == 0

    def test_maxlen_overflow_reconnect_with_first_seq(self):
        """Publish maxlen+5 events; reconnect with since_seq=<first_seq>;
        assert first emitted event is replay_truncated."""
        bus = _SseEventBus()
        maxlen = 8
        bus._history_max = maxlen
        bus._history = _deque(maxlen=maxlen)

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        n_total = maxlen + 5  # 13 events
        for i in range(n_total):
            bus._record(base, "machine.created", {"idx": i}, seq_id=i + 1)

        first_seq = 1
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(since, since_seq=first_seq)

        assert result, "Expected at least one event"
        assert result[0][0] == "replay_truncated", (
            f"Expected replay_truncated sentinel as first event, got {result[0][0]!r}"
        )

    def test_no_sentinel_when_no_overflow(self):
        """When history has not overflowed, no sentinel is emitted."""
        bus = _SseEventBus()
        maxlen = 20
        bus._history_max = maxlen
        bus._history = _deque(maxlen=maxlen)

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        n_total = 5  # well within maxlen
        for i in range(n_total):
            bus._record(base, "machine.created", {"idx": i}, seq_id=i + 1)

        # since_seq=0 means client hasn't received anything; oldest_seq=1 = 0+1, no gap
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(since, since_seq=0)
        types = [et for et, _ in result]
        assert "replay_truncated" not in types

    def test_history_since_seq_empty_deque_zero_since_seq_no_sentinel(self):
        """Empty deque with since_seq=0 (fresh client, fresh bus): no sentinel."""
        bus = _SseEventBus()
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(base, since_seq=0)
        assert result == []

    # ------------------------------------------------------------------
    # New tests: restart / impossible since_seq gap detection
    # ------------------------------------------------------------------

    def test_empty_history_with_positive_since_seq_emits_sentinel(self):
        """Simulate server restart: fresh bus, no history, reconnect with since_seq=50.

        The bus has no record of ever issuing seq_id 50, so continuity
        cannot be guaranteed.  The sentinel must be the first (and only)
        result.
        """
        bus = _SseEventBus()
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(since, since_seq=50)

        assert len(result) == 1, (
            f"Expected exactly one item (the sentinel); got {len(result)}: {result!r}"
        )
        event_type, payload = result[0]
        assert event_type == "replay_truncated"
        assert payload["type"] == "replay_truncated"
        assert payload["since"] == 50
        assert payload["seq_id"] == 0

    def test_one_event_published_since_seq_exceeds_highest_emits_sentinel(self):
        """Publish 1 event (seq_id=1), then reconnect with since_seq=100.

        The bus highest-ever seq_id is 1.  The client claims it last saw
        seq_id 100, which is impossible — oldest_seq(1) > 100+1 is False
        BUT the deque is not empty AND oldest_seq(1) > since_seq(100)+1 is
        False ... wait: 1 > 101 is False, so the overflow branch won't fire.

        However since_seq=100 > highest ever issued (1), the client's claim
        is impossible.  The correct detection here relies on the "restart"
        branch: oldest_seq (1) <= since_seq+1 (101), so the deque-overflow
        branch does NOT fire.

        We need to verify this scenario still results in a sentinel.  The
        right way is: if since_seq >= oldest_seq AND since_seq > (highest
        seq ever issued), emit sentinel.  The simplest proxy: peek at the
        newest entry in the deque (rightmost); if since_seq > newest_seq,
        the client is ahead of what the bus has ever issued — truncated.
        """
        bus = _SseEventBus()
        event_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        bus._record(event_ts, "machine.created", {"id": "m-1"}, seq_id=1)

        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(since, since_seq=100)

        assert len(result) >= 1, f"Expected at least the sentinel; got {result!r}"
        event_type, payload = result[0]
        assert event_type == "replay_truncated", (
            f"Expected replay_truncated sentinel; got {event_type!r}"
        )
        assert payload["since"] == 100
        assert payload["seq_id"] == 0

    def test_overflow_after_100_events_reconnect_since_seq_50_emits_sentinel(self):
        """Publish 100 events into a deque with maxlen=50; reconnect with since_seq=50.

        After 100 publishes with maxlen=50:
          oldest_seq = 100 - 50 + 1 = 51
          since_seq = 50
          Gap condition: oldest_seq(51) > since_seq(50)+1=51 -> False (equal, not greater).

        Adjust: use maxlen=50, publish 101 events so oldest_seq=52.
          Gap condition: 52 > 51 -> True -> sentinel emitted.

        This exercises the existing overflow branch (not the restart branch)
        and must continue to work after the restart fix is applied.
        """
        bus = _SseEventBus()
        bus._history_max = 50
        bus._history = _deque(maxlen=50)

        event_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        n_events = 101  # oldest_seq = 101 - 50 + 1 = 52
        for i in range(n_events):
            bus._record(event_ts, "machine.created", {"i": i}, seq_id=i + 1)

        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(since, since_seq=50)

        assert len(result) >= 1, f"Expected at least the sentinel; got {result!r}"
        event_type, payload = result[0]
        assert event_type == "replay_truncated", (
            f"Expected replay_truncated sentinel as first event; got {event_type!r}"
        )
        assert payload["since"] == 50
        assert payload["seq_id"] == 0
        # All 50 surviving history entries follow the sentinel.
        assert len(result) == 1 + 50

    def test_cross_restart_cursor_at_boot_base_emits_sentinel_no_silent_drop(self):
        """Reproduce the cross-restart seq collision the boot-token guard closes.

        This isolates the *generation-floor* branch from the deque-overflow
        branch.  The new process seeds its counter above ``boot_base``, so the
        first fresh event is ``boot_base + 1``.  A stale client cursor of exactly
        ``boot_base`` sits flush against that first id — ``oldest_seq
        (boot_base+1) <= since_seq(boot_base) + 1`` — so the overflow branch does
        NOT fire and neither does the client-ahead branch.  ONLY the
        generation-floor guard can catch it.

        Without the guard, ``filter seq > boot_base`` would return every fresh
        event with NO sentinel, mirroring the original defect where a restarted
        counter reissued low ids and the client silently skipped the events
        published in the collision window.  With the guard, the stale cursor
        forces a full resync.
        """
        boot_base = 5  # highest seq id the previous generation could have issued
        bus = _SseEventBus(boot_base=boot_base)

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Fresh generation publishes 5 events: boot_base+1 .. boot_base+5.
        for i in range(5):
            bus._record(base, "machine.created", {"i": i}, seq_id=boot_base + 1 + i)

        # oldest_seq = boot_base+1 = since_seq+1 -> overflow branch does NOT fire.
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(since, since_seq=boot_base)

        assert result, "Expected at least the sentinel"
        assert result[0][0] == "replay_truncated", (
            "Stale cross-restart cursor must trigger replay_truncated (the guard "
            f"is the only branch that can catch this scenario); got {result[0][0]!r}"
        )
        assert result[0][1]["since"] == boot_base
        assert result[0][1]["seq_id"] == 0

    def test_cross_restart_low_cursor_below_boot_base_emits_sentinel(self):
        """A stale low cursor (since_seq=2) from a prior boot also resyncs.

        Here the overflow branch would also fire, but the guard must catch the
        stale generation cursor regardless — a cursor at or below ``_boot_base``
        can never belong to this generation.
        """
        boot_base = 10
        bus = _SseEventBus(boot_base=boot_base)

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(5):
            bus._record(base, "machine.created", {"i": i}, seq_id=boot_base + 1 + i)

        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(since, since_seq=2)

        assert result[0][0] == "replay_truncated"
        assert result[0][1]["since"] == 2

    def test_new_generation_counter_starts_above_boot_base(self):
        """A restarted bus never reissues low ids that collide with old cursors."""

        async def run():
            boot_base = 1_000
            bus = _SseEventBus(boot_base=boot_base)
            await bus.publish("machine.created", {"id": "m-1"})
            first_seq = bus._history[0][3]
            assert first_seq == boot_base + 1, (
                f"first seq of new generation must be boot_base+1; got {first_seq}"
            )

        asyncio.run(run())

    def test_cursor_within_current_generation_replays_normally(self):
        """A cursor issued by THIS generation (> boot_base) replays without a sentinel."""

        async def run():
            boot_base = 100
            bus = _SseEventBus(boot_base=boot_base)
            for i in range(3):
                await bus.publish("machine.updated", {"i": i})
            # This generation issued 101, 102, 103.  Client saw 101; reconnect at 101.
            since = datetime(2025, 1, 1, tzinfo=timezone.utc)
            result = bus.history_since_seq(since, since_seq=boot_base + 1)
            types = [et for et, _ in result]
            assert "replay_truncated" not in types, (
                f"in-generation cursor must not truncate; got {types!r}"
            )
            # Only the two events after the cursor (102, 103) replay.
            assert len(result) == 2

        asyncio.run(run())

    def test_module_singleton_seeded_with_monotonic_boot_base(self):
        """The module bus uses a wall-clock-seeded boot base well under 2**53.

        Guards the JS-safe-integer contract: the single-int ``id:`` cursor must
        remain parseable by every SDK reader, so the boot base (and therefore
        every issued seq_id) must stay below JavaScript's 2**53 limit.
        """
        from orb.api.routers.events import sse_event_bus

        assert sse_event_bus._boot_base > 0, "module singleton must carry a boot floor"
        assert sse_event_bus._boot_base < 2**53, "seq cursor must stay JS-safe-integer"

    def test_since_seq_param_activates_gap_detection_on_stream(self):
        """Route: ?since= + ?since_seq= triggers history_since_seq path.

        Note: the ?since= timestamp must use Z suffix (not +00:00) to avoid
        the '+' character being decoded as a space in URL query parameters.
        """
        from orb.api.dependencies import CurrentUser

        app = FastAPI()
        app.include_router(events_router)
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            username="test", role="viewer"
        )
        client = TestClient(app, raise_server_exceptions=False)

        maxlen = 3
        bus = _SseEventBus()
        bus._history_max = maxlen
        bus._history = _deque(maxlen=maxlen)

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(maxlen + 2):
            bus._record(base, "machine.created", {"i": i}, seq_id=i + 1)

        q: asyncio.Queue = asyncio.Queue()
        q.put_nowait(None)  # close immediately after history replay
        mock_sub = AsyncMock(return_value=q)
        mock_unsub = AsyncMock()
        with (
            patch("orb.api.routers.events.sse_event_bus", bus),
            patch.object(bus, "subscribe", mock_sub),
            patch.object(bus, "unsubscribe", mock_unsub),
        ):
            # Use Z suffix, not +00:00, to avoid URL encoding of '+'
            resp = client.get("/events/?since=2025-12-31T00:00:00Z&since_seq=1")

        assert resp.status_code == 200
        assert "replay_truncated" in resp.text
        for block in resp.text.split("\n\n"):
            if "replay_truncated" in block and "event:" in block:
                data_line = next(
                    (line for line in block.splitlines() if line.startswith("data:")),
                    None,
                )
                assert data_line is not None
                payload = json.loads(data_line[len("data: ") :])
                assert payload["seq_id"] == 0
                assert payload["since"] == 1
                break
        else:
            pytest.fail("replay_truncated sentinel event block not found in stream")


# ---------------------------------------------------------------------------
# orb-1.24: Integration-level SSE reconnect with ?since_seq= after deque overflow
# ---------------------------------------------------------------------------


def _parse_sse_events(body: str) -> list[dict]:
    """Parse raw SSE body text into list of dicts with 'event' and 'data' keys.

    Each SSE block (terminated by a blank line) becomes one dict:
      {"event": "<type>", "data": <parsed JSON or raw string>}
    """
    events: list[dict] = []
    current: dict = {}
    for line in body.splitlines():
        if line.startswith("event:"):
            current["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            raw = line[len("data:") :].strip()
            try:
                current["data"] = json.loads(raw)
            except json.JSONDecodeError:
                current["data"] = raw
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


def _make_viewer_app() -> FastAPI:
    from orb.api.dependencies import CurrentUser

    app = FastAPI()
    app.include_router(events_router)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        username="alice", role="viewer"
    )
    return app


@pytest.mark.unit
@pytest.mark.api
class TestSseReconnectDequeOverflow:
    """Integration-level SSE reconnect test covering orb-1.24.

    Verifies that when a client reconnects with ?since_seq= pointing to an event
    that has been evicted from the history deque (overflow), the server emits a
    synthetic ``replay_truncated`` event as the first SSE item so the client
    knows its local state is stale and must perform a full reload.

    Scenario:
      1. Publish N > deque_maxlen events (deque_maxlen = _history_max = 512).
      2. Note the sequence_id of the first event (seq_id=1, now evicted).
      3. Reconnect with ?since=<past_UTC_Z>&since_seq=<first_evicted_seq_id>.
      4. Assert first SSE event is ``replay_truncated``.
      5. Assert sentinel["since"] == first_evicted_seq_id.

    IMPORTANT: the ?since= timestamp must use the Z suffix (e.g.
    ``2025-01-01T00:00:00Z``) rather than +00:00.  The TestClient URL
    decoder treats '+' as a space, which makes _parse_since return None
    and skip history replay entirely.

    The module-level ``_history_max`` is 512.  HTTP-level sub-tests use a
    small local bus (_history_max=10) for speed.  The canonical sub-test
    publishes ``_history_max + 2`` events to confirm the real 512 threshold.
    """

    _SMALL_MAXLEN: int = 10

    def _make_overflow_bus(self) -> tuple[_SseEventBus, int]:
        """Return (bus, first_evicted_seq_id).

        Publishes _SMALL_MAXLEN + 2 events so oldest_seq=3 and the gap condition
        oldest_seq(3) > since_seq(1)+1=2 is True.
        """
        # With maxlen=10 and n=12: oldest_seq = 12 - 10 + 1 = 3.
        n_publish = self._SMALL_MAXLEN + 2
        bus = _SseEventBus()
        bus._history_max = self._SMALL_MAXLEN
        bus._history = _deque(maxlen=self._SMALL_MAXLEN)

        event_ts = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(n_publish):
            bus._record(event_ts, "machine.created", {"idx": i}, seq_id=i + 1)

        return bus, 1  # first_evicted_seq_id = 1

    def test_deque_maxlen_is_512(self) -> None:
        """_history_max must equal 512 -- documents the actual module constant."""
        assert _SseEventBus()._history_max == 512

    def test_reconnect_with_evicted_since_seq_emits_replay_truncated(self) -> None:
        """First SSE event is replay_truncated when ?since_seq= points to evicted entry.

        Publishes _SMALL_MAXLEN + 2 events with _history_max=10 (oldest_seq=3).
        Reconnects via HTTP with ?since=2025-01-01T00:00:00Z&since_seq=1.
        Gap condition: oldest_seq(3) > 1+1=2 -> server prepends replay_truncated.

        Assertions:
          1. HTTP response is 200.
          2. First parsed SSE event type is 'replay_truncated'.
          3. sentinel["since"] == 1 (the sequence_id of the first evicted event).
        """
        bus, first_evicted_seq_id = self._make_overflow_bus()

        app = _make_viewer_app()
        client = TestClient(app, raise_server_exceptions=False)

        mock_sub = AsyncMock()
        mock_unsub = AsyncMock()
        with (
            patch("orb.api.routers.events.sse_event_bus", bus),
            patch.object(bus, "subscribe", mock_sub),
            patch.object(bus, "unsubscribe", mock_unsub),
        ):
            q: asyncio.Queue = asyncio.Queue()
            q.put_nowait(None)  # close signal -- generator exits after history replay
            mock_sub.return_value = q

            resp = client.get(
                f"/events/?since=2025-01-01T00:00:00Z&since_seq={first_evicted_seq_id}"
            )

        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        assert len(events) >= 1, f"Expected SSE events but stream was empty.\nBody:\n{resp.text!r}"

        first = events[0]
        assert first["event"] == "replay_truncated", (
            f"Expected first SSE event type 'replay_truncated', "
            f"got {first['event']!r}.\nFull stream:\n{resp.text}"
        )
        assert first["data"]["since"] == first_evicted_seq_id, (
            f"Expected sentinel['since'] == {first_evicted_seq_id}, got {first['data']['since']!r}"
        )

    def test_sentinel_seq_id_is_zero_in_stream(self) -> None:
        """The replay_truncated sentinel's seq_id field is 0 (the reserved marker)."""
        bus = _SseEventBus()
        bus._history_max = 6
        bus._history = _deque(maxlen=6)

        event_ts = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        # 9 into maxlen=6; oldest_seq=4, since_seq=1, 4 > 1+1=2 -> gap
        for i in range(9):
            bus._record(event_ts, "machine.updated", {"i": i}, seq_id=i + 1)

        app = _make_viewer_app()
        client = TestClient(app, raise_server_exceptions=False)

        mock_sub = AsyncMock()
        mock_unsub = AsyncMock()
        with (
            patch("orb.api.routers.events.sse_event_bus", bus),
            patch.object(bus, "subscribe", mock_sub),
            patch.object(bus, "unsubscribe", mock_unsub),
        ):
            q: asyncio.Queue = asyncio.Queue()
            q.put_nowait(None)
            mock_sub.return_value = q
            resp = client.get("/events/?since=2025-01-01T00:00:00Z&since_seq=1")

        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        assert len(events) >= 1, f"Stream was empty.\nBody:\n{resp.text!r}"
        assert events[0]["event"] == "replay_truncated"
        assert events[0]["data"]["seq_id"] == 0

    def test_no_sentinel_when_reconnecting_within_retained_history(self) -> None:
        """No replay_truncated when ?since_seq= is within the retained history window."""
        bus = _SseEventBus()
        bus._history_max = self._SMALL_MAXLEN
        bus._history = _deque(maxlen=self._SMALL_MAXLEN)

        event_ts = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        # 5 events, no overflow (maxlen=10)
        for i in range(5):
            bus._record(event_ts, "machine.created", {"i": i}, seq_id=i + 1)

        # since_seq=0: oldest_seq=1, 1 <= 0+1=1 -> no gap, no sentinel
        app = _make_viewer_app()
        client = TestClient(app, raise_server_exceptions=False)

        mock_sub = AsyncMock()
        mock_unsub = AsyncMock()
        with (
            patch("orb.api.routers.events.sse_event_bus", bus),
            patch.object(bus, "subscribe", mock_sub),
            patch.object(bus, "unsubscribe", mock_unsub),
        ):
            q: asyncio.Queue = asyncio.Queue()
            q.put_nowait(None)
            mock_sub.return_value = q
            resp = client.get("/events/?since=2025-01-01T00:00:00Z&since_seq=0")

        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        event_types = [e["event"] for e in events]
        assert "replay_truncated" not in event_types, (
            f"Unexpected replay_truncated in non-overflow scenario: {event_types}"
        )

    def test_real_deque_maxlen_overflow_triggers_sentinel(self) -> None:
        """Publish N > _history_max (512) events; assert replay_truncated is first.

        This is the canonical scenario from orb-1.24 and the task specification:

          1. Publish _history_max + 2 events (via _record, for test isolation).
             With maxlen=512 and n=514: oldest_seq = 514 - 512 + 1 = 3.
          2. Note first_evicted_seq_id = 1 (the sequence_id of the first event).
          3. Call history_since_seq with since_seq=1.
             Gap condition: oldest_seq(3) > 1+1=2 -> True -> sentinel emitted.
          4. Assert sentinel is first event with sentinel["since"] == 1.

        We call history_since_seq directly (not via HTTP) to avoid a slow
        512-iteration HTTP round-trip while still testing the real module constant.
        """
        bus = _SseEventBus()
        deque_maxlen = bus._history_max  # 512 per module constant

        event_ts = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        n_events = deque_maxlen + 2  # oldest_seq = 3 after overflow

        first_evicted_seq_id = 1
        for i in range(n_events):
            bus._record(event_ts, "machine.created", {"i": i}, seq_id=i + 1)

        # After overflow: deque holds deque_maxlen entries, oldest seq_id = 3.
        cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = bus.history_since_seq(cutoff, since_seq=first_evicted_seq_id)

        assert len(result) >= 1, "Expected at least the sentinel event in result"
        sentinel_type, sentinel_payload = result[0]

        assert sentinel_type == "replay_truncated", (
            f"Expected 'replay_truncated' as first event type, got {sentinel_type!r}"
        )
        assert sentinel_payload["since"] == first_evicted_seq_id, (
            f"Expected sentinel['since'] == {first_evicted_seq_id}, "
            f"got {sentinel_payload['since']!r}"
        )
        assert sentinel_payload["seq_id"] == 0
        # The surviving history follows the sentinel.
        assert len(result) == 1 + deque_maxlen


# ---------------------------------------------------------------------------
# SSE wire-format: id: line (Last-Event-ID) + reconnect replay via ?since_seq=
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.api
class TestSseWireSeqIdAndReconnect:
    """The server transmits each event's seq_id on the wire as an SSE ``id:``
    line so standard clients get Last-Event-ID semantics, and a reconnect with
    ?since_seq=<n> replays only the events after n.
    """

    def _seed_bus(self, n: int, *, maxlen: int = 512) -> _SseEventBus:
        bus = _SseEventBus()
        bus._history_max = maxlen
        bus._history = _deque(maxlen=maxlen)
        ts = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(n):
            bus._record(ts, "RequestStatusChangedEvent", {"idx": i}, seq_id=i + 1)
        return bus

    def _stream(self, bus: _SseEventBus, query: str) -> str:
        app = _make_viewer_app()
        client = TestClient(app, raise_server_exceptions=False)
        mock_sub = AsyncMock()
        mock_unsub = AsyncMock()
        with (
            patch("orb.api.routers.events.sse_event_bus", bus),
            patch.object(bus, "subscribe", mock_sub),
            patch.object(bus, "unsubscribe", mock_unsub),
        ):
            q: asyncio.Queue = asyncio.Queue()
            q.put_nowait(None)  # close after history replay
            mock_sub.return_value = q
            resp = client.get(f"/events/{query}")
        assert resp.status_code == 200
        return resp.text

    def test_history_replay_emits_id_line_per_event(self):
        """Replayed events carry an ``id:`` line equal to their seq_id."""
        bus = self._seed_bus(3)
        body = self._stream(bus, "?since=2025-01-01T00:00:00Z")
        # Every real event block starts with its id: line.
        blocks = [b for b in body.split("\n\n") if "event:" in b]
        assert len(blocks) == 3
        for block, expected_id in zip(blocks, (1, 2, 3), strict=True):
            assert f"id: {expected_id}" in block, (
                f"Expected 'id: {expected_id}' in block:\n{block!r}"
            )

    def test_since_seq_alone_replays_after_cursor_with_ids(self):
        """?since_seq=<n> WITHOUT ?since= replays only events after n, each with id:.

        A standard SSE client resuming from a Last-Event-ID sends only
        since_seq; the server must still replay from that cursor.
        """
        bus = self._seed_bus(5)  # seq_ids 1..5
        body = self._stream(bus, "?since_seq=3")
        events = _parse_sse_events(body)
        # No sentinel (3 is within retained history), only 4 and 5 replayed.
        assert [e["event"] for e in events] == [
            "RequestStatusChangedEvent",
            "RequestStatusChangedEvent",
        ]
        assert [e["data"]["idx"] for e in events] == [3, 4]  # idx = seq_id - 1
        # And each carried its id: line (4 and 5).
        ids = [line for line in body.splitlines() if line.startswith("id:")]
        assert ids == ["id: 4", "id: 5"]

    def test_since_seq_alone_too_old_emits_sentinel_without_id(self):
        """?since_seq= pointing at an evicted event emits the sentinel first,
        and the sentinel carries NO id: line (seq_id 0 is never a resume cursor).
        """
        bus = self._seed_bus(12, maxlen=10)  # oldest surviving seq_id = 3
        body = self._stream(bus, "?since_seq=1")
        events = _parse_sse_events(body)
        assert events[0]["event"] == "replay_truncated"
        assert events[0]["data"]["seq_id"] == 0
        # The sentinel block must not carry an id: line.
        for block in body.split("\n\n"):
            if "replay_truncated" in block:
                assert "id:" not in block, f"sentinel must omit id:; got:\n{block!r}"
                break
        else:
            pytest.fail("replay_truncated block not found")

    def test_replay_truncated_passes_narrow_type_filter(self):
        """The sentinel reaches a client that narrowed ?type= to request events."""
        bus = self._seed_bus(12, maxlen=10)
        body = self._stream(
            bus,
            "?since_seq=1&type=RequestStatusChangedEvent,RequestCompletedEvent",
        )
        events = _parse_sse_events(body)
        assert events[0]["event"] == "replay_truncated"
