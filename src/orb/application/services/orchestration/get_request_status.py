"""Orchestrator for getting request status."""

from __future__ import annotations

import asyncio

from orb.application.dto.queries import SyncAndGetRequestQuery, SyncAndListActiveRequestsQuery
from orb.application.ports.command_bus_port import CommandBusPort
from orb.application.ports.query_bus_port import QueryBusPort
from orb.application.services.orchestration.base import (
    TERMINAL_STATUSES as _TERMINAL_STATUSES,
    OrchestratorBase,
)
from orb.application.services.orchestration.dtos import (
    GetRequestStatusInput,
    GetRequestStatusOutput,
    Paginated,
)
from orb.domain.base.exceptions import EntityNotFoundError
from orb.domain.base.ports.logging_port import LoggingPort

# Interval between status polls when ``wait=True``. Wall-clock time is tracked
# against ``timeout_seconds`` so the total wait never exceeds the caller's cap.
_POLL_INTERVAL_SECONDS = 2


class GetRequestStatusOrchestrator(OrchestratorBase[GetRequestStatusInput, GetRequestStatusOutput]):
    """Orchestrator for retrieving request status."""

    def __init__(
        self, command_bus: CommandBusPort, query_bus: QueryBusPort, logger: LoggingPort
    ) -> None:
        self._command_bus = command_bus
        self._query_bus = query_bus
        self._logger = logger

    async def execute(self, input: GetRequestStatusInput) -> GetRequestStatusOutput:  # type: ignore[return]
        self._logger.info("GetRequestStatusOrchestrator: all=%s", input.all_requests)

        if input.all_requests:
            query = SyncAndListActiveRequestsQuery(all_resources=True, limit=None)
            results = await self._dispatch(
                "GetRequestStatus.listActive", self._query_bus.execute(query)
            )
            items = results.items if isinstance(results, Paginated) else (results or [])
            return GetRequestStatusOutput(requests=[self._to_dict(r) for r in items])

        if input.wait and input.request_ids:
            request_dicts = await self._poll_until_terminal(input)
            return GetRequestStatusOutput(requests=request_dicts)

        return GetRequestStatusOutput(requests=await self._fetch_once(input))

    async def _fetch_once(self, input: GetRequestStatusInput) -> list[dict]:
        """Fetch a single status snapshot for every requested ID.

        Bulk per-request path: a single bad ID must NOT fail the whole batch,
        so each request is queried independently and any failure is folded
        into that request's own result dict rather than re-raised. This is a
        deliberate divergence from the single-dispatch _dispatch() re-raise
        pattern used elsewhere — multi-ID callers rely on partial results.
        Every failure is still logged before being captured (see below).
        """
        request_dicts = []
        for request_id in input.request_ids:
            try:
                # When the caller asks for verbose status (the default for
                # GET /requests/{id}/status and the explicit batch-sync
                # endpoint), bypass the read-through cache. The whole point
                # of those calls is to refresh state from the provider —
                # serving a cached DTO defeats it and leaves the request
                # stuck on stale IN_PROGRESS even after a successful sync.
                # Non-verbose callers (lightweight list rows, etc.) can
                # still hit the cache for speed.
                query = SyncAndGetRequestQuery(  # type: ignore[assignment]
                    request_id=request_id,
                    verbose=input.verbose,
                    skip_cache=bool(input.verbose),
                )
                result = await self._query_bus.execute(query)
                request_dicts.append(self._to_dict(result))
            except EntityNotFoundError as exc:
                # A genuinely non-existent request. Tag it with an explicit
                # ``not_found`` flag so single-ID callers can distinguish it
                # from an existing request that merely errored during sync.
                # A real RequestDTO never carries a "not_found" key, so this
                # flag is an unambiguous synthetic-only discriminator.
                self._logger.info("Request %s not found: %s", request_id, exc)
                request_dicts.append(
                    {"request_id": request_id, "not_found": True, "error": str(exc)}
                )
            except Exception as exc:
                # The request may well exist but its provider sync failed
                # (e.g. ProviderContractError, infra error). Emit an error
                # entry WITHOUT the not_found flag so batch callers still see
                # a per-ID partial failure and single-ID callers do not 404 a
                # request that actually exists.
                self._logger.error("Failed to get status for %s: %s", request_id, exc)
                request_dicts.append({"request_id": request_id, "error": str(exc)})

        return request_dicts

    async def _poll_until_terminal(self, input: GetRequestStatusInput) -> list[dict]:
        """Poll every requested ID until all reach a terminal state or timeout.

        Wall-clock time is tracked from the first poll against
        ``input.timeout_seconds``; the last snapshot is returned when the cap is
        reached even if some requests are still non-terminal, so callers always
        get the freshest known state.
        """
        elapsed = 0
        request_dicts = await self._fetch_once(input)
        while not self._all_terminal(request_dicts) and elapsed < input.timeout_seconds:
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            elapsed += _POLL_INTERVAL_SECONDS
            request_dicts = await self._fetch_once(input)
        return request_dicts

    @staticmethod
    def _all_terminal(request_dicts: list[dict]) -> bool:
        """Return True once every entry is terminal, errored, or not found."""
        for entry in request_dicts:
            if entry.get("not_found") or entry.get("error"):
                continue
            status = str(entry.get("status", "")).lower()
            if status not in _TERMINAL_STATUSES:
                return False
        return True

    @staticmethod
    def _to_dict(obj: object) -> dict:
        if hasattr(obj, "to_dict"):
            return obj.to_dict()  # type: ignore[union-attr]
        if hasattr(obj, "model_dump"):
            return obj.model_dump()  # type: ignore[union-attr]
        return dict(obj) if isinstance(obj, dict) else {"data": str(obj)}
