"""Orchestrator for listing scheduler strategies."""

from __future__ import annotations

from orb.application.ports.query_bus_port import QueryBusPort
from orb.application.queries.scheduler import ListSchedulerStrategiesQuery
from orb.application.services.orchestration.base import OrchestratorBase
from orb.application.services.orchestration.dtos import (
    ListSchedulerStrategiesInput,
    ListSchedulerStrategiesOutput,
)
from orb.domain.base.ports.logging_port import LoggingPort


class ListSchedulerStrategiesOrchestrator(
    OrchestratorBase[ListSchedulerStrategiesInput, ListSchedulerStrategiesOutput]
):
    """Orchestrator for listing scheduler strategies."""

    def __init__(self, query_bus: QueryBusPort, logger: LoggingPort) -> None:
        self._query_bus = query_bus
        self._logger = logger

    async def execute(self, input: ListSchedulerStrategiesInput) -> ListSchedulerStrategiesOutput:  # type: ignore[return]
        self._logger.info("ListSchedulerStrategiesOrchestrator: executing")
        query = ListSchedulerStrategiesQuery()
        response = await self._dispatch("ListSchedulerStrategies", self._query_bus.execute(query))
        strategies = [s.model_dump() for s in response.strategies]
        return ListSchedulerStrategiesOutput(
            strategies=strategies,
            current_strategy=response.current_strategy,
            count=len(strategies),
        )
