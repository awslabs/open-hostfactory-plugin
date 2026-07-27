"""Unit tests for bulk query handler construction and include-* branches.

Complements test_bulk_handlers.py (which bypasses __init__ via object.__new__)
by exercising the real __init__ wiring of GetMultipleRequestsHandler and the
include_machines / include_requests enrichment branches in
application/queries/bulk_handlers.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orb.application.dto.bulk_queries import (
    GetMultipleMachinesQuery,
    GetMultipleRequestsQuery,
)
from orb.application.queries.bulk_handlers import (
    GetMultipleMachinesHandler,
    GetMultipleRequestsHandler,
)


def _make_request_dto(request_id: str = "req-a"):
    from datetime import datetime, timezone

    from orb.application.dto.responses import RequestDTO

    return RequestDTO.model_validate(
        {
            "request_id": request_id,
            "status": "complete",
            "requested_count": 1,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
    )


def _make_machine_dto(machine_id: str = "mc-a"):
    from orb.application.machine.dto import MachineDTO

    return MachineDTO.model_validate(
        {
            "machine_id": machine_id,
            "name": "i-test",
            "status": "running",
            "instance_type": "t3.small",
            "private_ip": "10.0.0.1",
            "result": "executing",
        }
    )


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetMultipleRequestsInit:
    async def test_init_wires_services_and_include_machines(self):
        with (
            patch("orb.application.services.request_query_service.RequestQueryService") as MockQS,
            patch("orb.application.factories.request_dto_factory.RequestDTOFactory") as MockFactory,
        ):
            qs = MockQS.return_value
            qs.get_request = AsyncMock(return_value=MagicMock())
            qs.get_machines_for_request = AsyncMock(return_value=["m1"])
            MockFactory.return_value.create_from_domain.return_value = _make_request_dto()

            handler = GetMultipleRequestsHandler(
                uow_factory=MagicMock(),
                logger=MagicMock(),
                error_handler=MagicMock(),
                container=MagicMock(),
            )

            result = await handler.execute_query(
                GetMultipleRequestsQuery(request_ids=["req-a"], include_machines=True)
            )

        qs.get_machines_for_request.assert_awaited_once()
        assert result.found_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetMultipleMachinesIncludeRequests:
    """include_requests branch enriches each machine with its owning request."""

    def _handler(self) -> GetMultipleMachinesHandler:
        handler = object.__new__(GetMultipleMachinesHandler)
        handler.logger = MagicMock()
        handler.error_handler = MagicMock()
        handler.uow_factory = MagicMock()
        handler._container = MagicMock()
        handler._query_service = MagicMock()
        handler._dto_factory = MagicMock()
        return handler

    async def test_include_requests_fetches_owning_request(self):
        handler = self._handler()
        machine = MagicMock(machine_id="mc-a", request_id="req-a")
        handler._query_service.get_machine = AsyncMock(return_value=machine)
        handler._dto_factory.create_from_domain.return_value = _make_machine_dto()

        with patch("orb.application.services.request_query_service.RequestQueryService") as MockRQS:
            MockRQS.return_value.get_request = AsyncMock(return_value=MagicMock())

            result = await handler.execute_query(
                GetMultipleMachinesQuery(machine_ids=["mc-a"], include_requests=True)
            )

        MockRQS.return_value.get_request.assert_awaited_once_with("req-a")
        assert result.found_count == 1

    async def test_include_requests_skipped_when_no_request_id(self):
        handler = self._handler()
        machine = MagicMock(machine_id="mc-a", request_id=None)
        handler._query_service.get_machine = AsyncMock(return_value=machine)
        handler._dto_factory.create_from_domain.return_value = _make_machine_dto()

        result = await handler.execute_query(
            GetMultipleMachinesQuery(machine_ids=["mc-a"], include_requests=True)
        )

        # DTO built with request=None; no crash and machine is found.
        assert result.found_count == 1
