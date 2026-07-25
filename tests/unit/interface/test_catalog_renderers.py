"""Unit tests for the catalog's per-operation render closures.

The operation catalog declares a small number of hand-written render closures
whose bodies carry real branching: the sync-machine renderer overlays a sync
outcome onto a machine-detail body, the machine/template detail renderers fall
back to an error body when the output DTO carries no entity, and
``bind_from_mapping`` filters a raw mapping down to an input DTO's fields. These
tests exercise those branches directly through a real
:class:`ResponseFormattingService` over a real default scheduler strategy, the
same rendering seam the interface adapters use.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from orb.application.machine.dto import MachineDTO
from orb.application.services.orchestration.dtos import (
    GetMachineOutput,
    GetTemplateOutput,
    SyncMachineOutput,
)
from orb.interface.catalog import (
    OPERATION_CATALOG,
    _render_get_template,
    _render_machine_detail,
    _render_sync_machine,
    bind_from_mapping,
)
from orb.interface.response_formatting_service import ResponseFormattingService


@pytest.fixture
def rfs() -> ResponseFormattingService:
    """A real ResponseFormattingService over a real default scheduler strategy."""
    from orb.infrastructure.scheduler.default.default_strategy import DefaultSchedulerStrategy

    strategy = DefaultSchedulerStrategy(logger=MagicMock())
    return ResponseFormattingService(strategy)


def _make_machine() -> MachineDTO:
    return MachineDTO(
        machine_id="machine-001",
        name="test-machine",
        status="running",
        instance_type="t3.medium",
        private_ip="10.0.0.1",
        result="succeed",
    )


def _make_template() -> Any:
    template = MagicMock()
    template.to_dict.return_value = {
        "template_id": "tmpl-001",
        "max_machines": 1,
        "machine_types": {"t3.medium": 1},
    }
    return template


# ---------------------------------------------------------------------------
# _render_sync_machine
# ---------------------------------------------------------------------------


def test_sync_machine_success_overlays_synced_true_without_error(
    rfs: ResponseFormattingService,
) -> None:
    """A successful sync overlays ``synced=True`` and adds no ``sync_error`` key."""
    out = SyncMachineOutput(machine=_make_machine(), synced=True)

    response = _render_sync_machine(rfs, out)

    assert response.data["synced"] is True
    assert "sync_error" not in response.data
    # The machine-detail body is preserved underneath the overlay.
    detail = rfs.format_machine_detail(_make_machine().to_dict())
    assert response.data["machine_id"] == detail.data["machine_id"]
    assert response.exit_code == detail.exit_code


def test_sync_machine_failure_overlays_synced_false_and_sync_error(
    rfs: ResponseFormattingService,
) -> None:
    """A failed sync overlays ``synced=False`` and carries the provider error."""
    out = SyncMachineOutput(machine=_make_machine(), synced=False, error="provider timeout")

    response = _render_sync_machine(rfs, out)

    assert response.data["synced"] is False
    assert response.data["sync_error"] == "provider timeout"


def test_sync_machine_missing_machine_renders_error(rfs: ResponseFormattingService) -> None:
    """No machine on the output DTO renders the not-found error body."""
    out = SyncMachineOutput(machine=None, synced=False)

    response = _render_sync_machine(rfs, out)

    assert response.data["success"] is False
    assert response.data["error"] == "Machine not found"


# ---------------------------------------------------------------------------
# _render_machine_detail / _render_get_template None branches
# ---------------------------------------------------------------------------


def test_render_machine_detail_missing_machine_renders_error(
    rfs: ResponseFormattingService,
) -> None:
    """A GetMachineOutput without a machine renders the not-found error body."""
    response = _render_machine_detail(rfs, GetMachineOutput(machine=None))

    assert response.data["success"] is False
    assert response.data["error"] == "Machine not found"


def test_render_machine_detail_present_machine_renders_detail(
    rfs: ResponseFormattingService,
) -> None:
    """A GetMachineOutput with a machine renders the machine-detail body."""
    response = _render_machine_detail(rfs, GetMachineOutput(machine=_make_machine()))

    assert response.data.get("error") != "Machine not found"
    assert response.data["machine_id"] == "machine-001"


def test_render_get_template_missing_template_renders_error(
    rfs: ResponseFormattingService,
) -> None:
    """A GetTemplateOutput without a template renders the not-found error body."""
    response = _render_get_template(rfs, GetTemplateOutput(template=None))

    assert response.data["success"] is False
    assert response.data["error"] == "Template not found"


def test_render_get_template_present_template_renders_detail(
    rfs: ResponseFormattingService,
) -> None:
    """A GetTemplateOutput with a template renders the template detail body."""
    response = _render_get_template(rfs, GetTemplateOutput(template=_make_template()))

    assert response.data.get("error") != "Template not found"
    assert response.data.get("template_id") == "tmpl-001"


# ---------------------------------------------------------------------------
# bind_from_mapping
# ---------------------------------------------------------------------------


def test_bind_from_mapping_filters_unknown_keys() -> None:
    """Keys that do not name a field on the input DTO are dropped before binding."""
    entry = OPERATION_CATALOG["list_machines"]

    dto = bind_from_mapping(
        entry,
        {"status": "running", "limit": 5, "not_a_field": "ignored", "sort": "-name"},
    )

    assert dto.status == "running"
    assert dto.limit == 5
    assert dto.sort == "-name"
    # The unknown key was filtered out rather than raising a TypeError.
    assert not hasattr(dto, "not_a_field")
