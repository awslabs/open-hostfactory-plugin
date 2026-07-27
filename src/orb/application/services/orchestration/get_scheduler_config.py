"""Orchestrator for getting scheduler configuration."""

from __future__ import annotations

from orb.application.ports.query_bus_port import QueryBusPort
from orb.application.queries.scheduler import GetSchedulerConfigurationQuery
from orb.application.services.orchestration.base import OrchestratorBase
from orb.application.services.orchestration.dtos import (
    GetSchedulerConfigInput,
    GetSchedulerConfigOutput,
)
from orb.domain.base.ports.logging_port import LoggingPort


class GetSchedulerConfigOrchestrator(
    OrchestratorBase[GetSchedulerConfigInput, GetSchedulerConfigOutput]
):
    """Orchestrator for retrieving scheduler configuration."""

    def __init__(self, query_bus: QueryBusPort, logger: LoggingPort) -> None:
        self._query_bus = query_bus
        self._logger = logger

    async def execute(self, input: GetSchedulerConfigInput) -> GetSchedulerConfigOutput:  # type: ignore[return]
        self._logger.info("GetSchedulerConfigOrchestrator: executing")
        query = GetSchedulerConfigurationQuery()
        response = await self._dispatch("GetSchedulerConfig", self._query_bus.execute(query))
        config = response.model_dump() if hasattr(response, "model_dump") else {}
        return GetSchedulerConfigOutput(config=config)
