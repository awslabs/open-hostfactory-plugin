"""ResponseFormattingService over real scheduler strategies.

The companion :mod:`test_response_formatting_service` module exercises the
service against a ``MagicMock`` scheduler — it proves the service's own
delegation and pagination-stamping logic in isolation. This module instead
wires the service to the two *real* scheduler strategies (``default`` and
``hostfactory``) so every format method is proven against the wire shapes the
strategies actually emit.

Because the service is the single seam every interface (SDK, CLI, MCP, REST)
routes response formatting through, proving each method here proves wire-format
correctness for all callers at once — no interface has to re-verify the shape.
Field-name divergence between the two strategies (``request_id`` vs
``requestId``) is intentional and asserted directly so a regression that
collapses the two vocabularies fails loud.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from orb.application.dto.interface_response import InterfaceResponse
from orb.application.dto.template import TemplateDTO
from orb.application.machine.dto import MachineDTO
from orb.application.request.dto import RequestDTO
from orb.interface.response_formatting_service import ResponseFormattingService

# ---------------------------------------------------------------------------
# Strategy fixtures — the two real strategies, each wrapped in a service.
# ---------------------------------------------------------------------------

DEFAULT = "default"
HOSTFACTORY = "hostfactory"


def _make_service(scheduler_name: str) -> ResponseFormattingService:
    if scheduler_name == HOSTFACTORY:
        from orb.infrastructure.scheduler.hostfactory.hostfactory_strategy import (
            HostFactorySchedulerStrategy,
        )

        return ResponseFormattingService(HostFactorySchedulerStrategy(logger=MagicMock()))
    from orb.infrastructure.scheduler.default.default_strategy import DefaultSchedulerStrategy

    return ResponseFormattingService(DefaultSchedulerStrategy(logger=MagicMock()))


@pytest.fixture(params=[DEFAULT, HOSTFACTORY])
def service(request: Any) -> ResponseFormattingService:
    """A ResponseFormattingService over each real scheduler strategy in turn."""
    return _make_service(request.param)


@pytest.fixture
def scheduler_name(request: Any) -> str:
    """The strategy name for the current ``service`` param, for shape assertions."""
    return request.node.callspec.params["service"]


# ---------------------------------------------------------------------------
# Input builders.
# ---------------------------------------------------------------------------


def _make_request_dto(status: str = "complete") -> RequestDTO:
    return RequestDTO(
        request_id="req-1",
        status=status,
        requested_count=1,
        created_at=datetime.now(timezone.utc),
    )


def _make_machine_dto() -> MachineDTO:
    return MachineDTO(
        machine_id="m-1",
        name="worker-1",
        status="running",
        instance_type="t3.medium",
        private_ip="10.0.0.1",
        result="succeed",
    )


def _make_template_dto() -> TemplateDTO:
    return TemplateDTO(
        template_id="t-1",
        max_instances=2,
        machine_types={"t3.medium": 2},
    )


def _machine_dict() -> dict[str, Any]:
    return {
        "machine_id": "m-1",
        "name": "worker-1",
        "status": "running",
        "instance_type": "t3.medium",
        "private_ip": "10.0.0.1",
        "provider_type": "aws",
    }


# ---------------------------------------------------------------------------
# format_request_operation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatRequestOperation:
    def test_returns_interface_response_with_dict_body(self, service):
        result = service.format_request_operation(
            {"request_id": "req-1", "status": "complete"}, "complete"
        )
        assert isinstance(result, InterfaceResponse)
        assert isinstance(result.data, dict)

    def test_problem_status_yields_non_zero_exit_code(self, service):
        result = service.format_request_operation(
            {"request_id": "req-1", "status": "failed"}, "failed"
        )
        assert result.exit_code == 1

    def test_success_status_yields_zero_exit_code(self, service):
        result = service.format_request_operation(
            {"request_id": "req-1", "status": "complete"}, "complete"
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# format_request_status
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatRequestStatus:
    def test_returns_requests_list(self, service):
        result = service.format_request_status([_make_request_dto()])
        assert isinstance(result, InterfaceResponse)
        assert isinstance(result.data["requests"], list)
        assert len(result.data["requests"]) == 1

    def test_pagination_stamped_when_supplied(self, service):
        result = service.format_request_status(
            [_make_request_dto()], total_count=5, next_cursor="cursor-1"
        )
        assert result.data["total_count"] == 5
        assert result.data["next_cursor"] == "cursor-1"

    def test_no_pagination_kwargs_leaves_payload_clean(self, service):
        """Single/HF getRequestStatus path: no pagination fields injected."""
        result = service.format_request_status([_make_request_dto()])
        assert "next_cursor" not in result.data
        assert "total_count" not in result.data

    def test_id_field_name_diverges_by_strategy(self, service, scheduler_name):
        """default emits snake_case request_id; HF emits camelCase requestId.

        The divergence is a deliberate wire-contract difference — asserting it
        here catches any change that accidentally unifies the two vocabularies.
        """
        req = service.format_request_status([_make_request_dto()]).data["requests"][0]
        if scheduler_name == HOSTFACTORY:
            assert "requestId" in req
            assert "request_id" not in req
        else:
            assert "request_id" in req
            assert "requestId" not in req


# ---------------------------------------------------------------------------
# format_return_requests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatReturnRequests:
    def test_empty_list_yields_response(self, service):
        result = service.format_return_requests([])
        assert isinstance(result, InterfaceResponse)
        assert isinstance(result.data, dict)

    def test_populated_request_produces_dict_body(self, service):
        result = service.format_return_requests(
            [
                {
                    "request_id": "rr-1",
                    "status": "complete",
                    "grace_period": 120,
                    "machines": [{"machine_id": "m-1", "name": "worker-1"}],
                }
            ]
        )
        assert isinstance(result.data, dict)


# ---------------------------------------------------------------------------
# format_machine_list / format_machine_detail / format_machine_operation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatMachineList:
    def test_returns_machines_list(self, service):
        result = service.format_machine_list([_make_machine_dto()])
        assert isinstance(result, InterfaceResponse)
        assert isinstance(result.data["machines"], list)
        assert len(result.data["machines"]) == 1

    def test_pagination_stamped_when_supplied(self, service):
        result = service.format_machine_list(
            [_make_machine_dto()], total_count=3, next_cursor="pg2"
        )
        assert result.data["total_count"] == 3
        assert result.data["next_cursor"] == "pg2"

    def test_no_pagination_kwargs_leaves_payload_clean(self, service):
        result = service.format_machine_list([_make_machine_dto()])
        assert "next_cursor" not in result.data
        assert "total_count" not in result.data


@pytest.mark.unit
class TestFormatMachineDetail:
    def test_returns_machine_body(self, service):
        result = service.format_machine_detail(_machine_dict())
        assert isinstance(result, InterfaceResponse)
        assert result.data["name"] == "worker-1"


@pytest.mark.unit
class TestFormatMachineOperation:
    def test_no_error_yields_zero_exit_code(self, service):
        result = service.format_machine_operation(_machine_dict())
        assert result.exit_code == 0

    def test_error_key_yields_non_zero_exit_code_for_default(self, service, scheduler_name):
        """Exit code follows the ``error`` key the strategy leaves in the body.

        The default strategy passes the source dict through, so an ``error`` key
        surfaces and drives exit code 1. HostFactory's detail formatter extracts
        a fixed HF field set and drops ``error`` entirely, so no error signal
        reaches the exit-code check — its body is HF-spec-shaped, not an error
        envelope. Both behaviours are asserted so the seam's exit-code contract
        is pinned per strategy.
        """
        payload = {**_machine_dict(), "error": "not found"}
        result = service.format_machine_operation(payload)
        if scheduler_name == HOSTFACTORY:
            assert result.exit_code == 0
            assert "error" not in result.data
        else:
            assert result.exit_code == 1


# ---------------------------------------------------------------------------
# format_template_list / format_template_detail / format_template_mutation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatTemplateList:
    def test_returns_templates_list(self, service):
        result = service.format_template_list([_make_template_dto()])
        assert isinstance(result, InterfaceResponse)
        assert isinstance(result.data["templates"], list)
        assert len(result.data["templates"]) == 1

    def test_pagination_stamped_when_supplied(self, service):
        result = service.format_template_list(
            [_make_template_dto()], total_count=1, next_cursor="c1"
        )
        assert result.data["total_count"] == 1
        assert result.data["next_cursor"] == "c1"

    def test_no_pagination_kwargs_leaves_payload_clean(self, service):
        result = service.format_template_list([_make_template_dto()])
        assert "next_cursor" not in result.data


@pytest.mark.unit
class TestFormatTemplateDetail:
    def test_returns_template_body(self, service):
        result = service.format_template_detail(_make_template_dto())
        assert isinstance(result, InterfaceResponse)
        # Either vocabulary carries the id — assert the identifier survives.
        assert result.data.get("template_id") == "t-1" or result.data.get("templateId") == "t-1"


@pytest.mark.unit
class TestFormatTemplateMutation:
    def test_id_field_name_diverges_by_strategy(self, service, scheduler_name):
        result = service.format_template_mutation({"template_id": "t-1", "status": "created"})
        assert isinstance(result, InterfaceResponse)
        if scheduler_name == HOSTFACTORY:
            assert result.data["templateId"] == "t-1"
            assert result.data["validationErrors"] == []
        else:
            assert result.data["template_id"] == "t-1"
            assert result.data["validation_errors"] == []


# ---------------------------------------------------------------------------
# format_system_status / format_provider_detail / format_storage_test
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatSystemStatus:
    def test_dict_input_extracts_status(self, service):
        result = service.format_system_status({"status": "ok", "version": "1.2.3"})
        assert isinstance(result, InterfaceResponse)
        assert result.data["status"] == "ok"


@pytest.mark.unit
class TestFormatProviderDetail:
    def test_extracts_provider_fields(self, service):
        result = service.format_provider_detail({"name": "aws", "type": "aws", "enabled": True})
        assert isinstance(result, InterfaceResponse)
        assert result.data["name"] == "aws"
        assert result.data["type"] == "aws"


@pytest.mark.unit
class TestFormatStorageTest:
    def test_success_sets_exit_code_0(self, service):
        result = service.format_storage_test({"status": "success"})
        assert result.exit_code == 0
        assert result.data["success"] is True

    def test_failure_sets_exit_code_1(self, service):
        result = service.format_storage_test({"status": "error"})
        assert result.exit_code == 1
        assert result.data["success"] is False


# ---------------------------------------------------------------------------
# Cross-strategy shape divergence (single assertion pinning the contract).
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_request_status_field_names_diverge_across_strategies():
    """The two strategies must NOT converge on one id vocabulary.

    default -> request_id (snake_case); hostfactory -> requestId (camelCase).
    Both are wrapped by the same ResponseFormattingService, so this pins the
    intentional divergence at the shared seam.
    """
    default_req = (
        _make_service(DEFAULT).format_request_status([_make_request_dto()]).data["requests"][0]
    )
    hf_req = (
        _make_service(HOSTFACTORY).format_request_status([_make_request_dto()]).data["requests"][0]
    )
    assert "request_id" in default_req and "requestId" not in default_req
    assert "requestId" in hf_req and "request_id" not in hf_req
