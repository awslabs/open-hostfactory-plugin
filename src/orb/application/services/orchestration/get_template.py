"""Orchestrator for getting a single template."""

from __future__ import annotations

from orb.application.dto.queries import GetTemplateQuery
from orb.application.ports.command_bus_port import CommandBusPort
from orb.application.ports.query_bus_port import QueryBusPort
from orb.application.services.orchestration.base import OrchestratorBase
from orb.application.services.orchestration.dtos import GetTemplateInput, GetTemplateOutput
from orb.domain.base.exceptions import EntityNotFoundError
from orb.domain.base.ports.logging_port import LoggingPort


class GetTemplateOrchestrator(OrchestratorBase[GetTemplateInput, GetTemplateOutput]):
    """Orchestrator for retrieving a single template by ID."""

    def __init__(
        self, command_bus: CommandBusPort, query_bus: QueryBusPort, logger: LoggingPort
    ) -> None:
        self._command_bus = command_bus
        self._query_bus = query_bus
        self._logger = logger

    async def execute(self, input: GetTemplateInput) -> GetTemplateOutput:  # type: ignore[return]
        self._logger.info(
            "GetTemplateOrchestrator: template_id=%s provider=%s",
            input.template_id,
            input.provider_name,
        )

        # EntityNotFoundError is a legitimate business outcome here (template
        # absent → template=None), so it is caught and mapped rather than
        # logged as an error. Any other failure is logged and re-raised,
        # matching the OrchestratorBase._dispatch contract.
        try:
            query = GetTemplateQuery(
                template_id=input.template_id,
                provider_name=input.provider_name,
            )
            result = await self._query_bus.execute(query)
            return GetTemplateOutput(template=result)
        except EntityNotFoundError:
            return GetTemplateOutput(template=None)
        except Exception as exc:
            self._logger.error("GetTemplate failed: %s", exc)
            raise
