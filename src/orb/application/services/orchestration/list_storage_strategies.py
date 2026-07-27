"""Orchestrator for listing storage strategies."""

from __future__ import annotations

from orb.application.ports.query_bus_port import QueryBusPort
from orb.application.queries.storage import ListStorageStrategiesQuery
from orb.application.services.orchestration.base import OrchestratorBase
from orb.application.services.orchestration.dtos import (
    ListStorageStrategiesInput,
    ListStorageStrategiesOutput,
)
from orb.domain.base.ports.logging_port import LoggingPort


class ListStorageStrategiesOrchestrator(
    OrchestratorBase[ListStorageStrategiesInput, ListStorageStrategiesOutput]
):
    """Orchestrator for listing storage strategies."""

    def __init__(self, query_bus: QueryBusPort, logger: LoggingPort) -> None:
        self._query_bus = query_bus
        self._logger = logger

    async def execute(self, input: ListStorageStrategiesInput) -> ListStorageStrategiesOutput:  # type: ignore[return]
        self._logger.info("ListStorageStrategiesOrchestrator: executing")
        query = ListStorageStrategiesQuery()
        response = await self._dispatch("ListStorageStrategies", self._query_bus.execute(query))
        strategies = [s.model_dump() for s in response.strategies]
        return ListStorageStrategiesOutput(
            strategies=strategies,
            current_strategy=response.current_strategy,
            count=len(strategies),
        )
