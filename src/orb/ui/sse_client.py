"""Minimal SSE client over httpx — async generator yielding (event, data) tuples.

Reflex apps run inside an asyncio event loop, so we use httpx's stream API
to keep the connection open and parse each event as it arrives. This file
intentionally has no external dependencies beyond httpx.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx


async def stream_sse(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    url_builder: Callable[[int | None], str] | None = None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Yield ``(event_type, data)`` tuples from a server-sent-events stream.

    Skips ``heartbeat`` events. Parses ``data:`` payload as JSON. If
    payload is not valid JSON, yields the raw string under data={"raw": "..."}.
    Auto-reconnects on transport error with a 1s backoff (max 30s).

    Reconnect replay (Last-Event-ID): the server tags every real event with an
    SSE ``id:`` line carrying its monotonic ``seq_id``. This client tracks the
    last id it saw and, on reconnect, asks *url_builder* to produce a URL that
    resumes from it (``?since_seq=<last id>``) so events missed during the blip
    are replayed instead of silently lost. Without a *url_builder* the same
    ``url`` is re-opened (legacy behaviour — no replay), preserving the original
    single-argument call contract.

    The ``replay_truncated`` sentinel (seq_id 0) is yielded through like any
    other event; the caller reacts to it (e.g. full refresh) and it is never
    adopted as a resume cursor because the server omits its ``id:`` line.
    """
    backoff = 1.0
    timeout = timeout or httpx.Timeout(None)  # SSE streams stay open
    last_event_id: int | None = None
    while True:
        # Rebuild the URL each connect so a reconnect carries the resume cursor.
        connect_url = url_builder(last_event_id) if url_builder is not None else url
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("GET", connect_url, headers=headers or {}) as resp:
                    if resp.status_code != 200:
                        # endpoint missing / unauthorised — back off
                        raise httpx.HTTPStatusError(
                            f"SSE returned {resp.status_code}", request=resp.request, response=resp
                        )
                    backoff = 1.0  # reset on successful connect
                    event_type = "message"
                    event_id: int | None = None
                    data_buf: list[str] = []
                    async for line in resp.aiter_lines():
                        if line == "":
                            # dispatch event
                            if data_buf:
                                raw = "\n".join(data_buf)
                                data_buf = []
                                # Advance the resume cursor from this event's
                                # id: line. The server never tags heartbeats or
                                # the replay_truncated sentinel with an id, so
                                # only real events move last_event_id forward and
                                # the sentinel is never adopted as a cursor.
                                if event_id is not None:
                                    last_event_id = event_id
                                event_id = None
                                if event_type == "heartbeat":
                                    event_type = "message"
                                    continue
                                try:
                                    data = json.loads(raw)
                                except Exception:
                                    data = {"raw": raw}
                                yield event_type, data
                            event_type = "message"
                            event_id = None
                            continue
                        if line.startswith(":"):
                            continue  # comment / keep-alive
                        if line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            data_buf.append(line[5:].lstrip())
                        elif line.startswith("id:"):
                            raw_id = line[3:].strip()
                            try:
                                event_id = int(raw_id)
                            except ValueError:
                                event_id = None
        except (httpx.HTTPError, httpx.TransportError):
            await asyncio.sleep(min(backoff, 30))
            backoff = min(backoff * 2, 30)
            continue
