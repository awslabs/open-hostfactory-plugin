"""Unit tests for GetMachineHealthHandler (stored + live-refresh paths)."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from orb.application.dto.queries import GetMachineHealthQuery
from orb.application.queries.machine_query_handlers import GetMachineHealthHandler
from orb.domain.base.exceptions import EntityNotFoundError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_machine(
    machine_id="m-001",
    status_val="running",
    provider_name="aws",
    provider_data=None,
):
    m = MagicMock()
    m.machine_id = machine_id
    m.provider_name = provider_name
    m.provider_data = provider_data or {}
    status = MagicMock()
    status.value = status_val
    m.status = status
    return m


def _make_uow_factory(machine_get=None):
    uow = MagicMock()
    uow.machines.get_by_id.return_value = machine_get

    @contextmanager
    def _create():
        yield uow

    factory = MagicMock()
    factory.create_unit_of_work.side_effect = _create
    return factory


def _handler(machine=None, registry=None):
    return GetMachineHealthHandler(
        uow_factory=_make_uow_factory(machine_get=machine),
        logger=MagicMock(),
        error_handler=MagicMock(),
        provider_registry_service=registry or MagicMock(),
    )


# ---------------------------------------------------------------------------
# Stored path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStoredPath:
    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        h = _handler(machine=None)
        with pytest.raises(EntityNotFoundError):
            await h.execute_query(GetMachineHealthQuery(machine_id="m-missing"))

    @pytest.mark.asyncio
    async def test_no_health_checks_yields_not_available(self):
        machine = _make_machine(status_val="running", provider_data={})
        h = _handler(machine=machine)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001"))
        assert result.machine_id == "m-001"
        assert result.overall_status == "running"
        assert result.system_status == "not_available"
        assert result.instance_status == "not_available"
        assert result.last_check is None

    @pytest.mark.asyncio
    async def test_coarse_stored_health_sets_overall(self):
        machine = _make_machine(
            provider_data={"health_checks": {"status": "impaired", "source": "describe_instances"}}
        )
        h = _handler(machine=machine)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001"))
        assert result.overall_status == "impaired"
        # No per-dimension keys stored -> both remain not_available.
        assert result.system_status == "not_available"
        assert result.instance_status == "not_available"

    @pytest.mark.asyncio
    async def test_per_dimension_stored_health(self):
        machine = _make_machine(
            provider_data={
                "health_checks": {
                    "status": "ok",
                    "system": {"status": True, "details": {"status": "ok"}},
                    "instance": {"status": False, "details": {"status": "impaired"}},
                }
            }
        )
        h = _handler(machine=machine)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001"))
        assert result.system_status == "ok"
        assert result.instance_status == "impaired"


# ---------------------------------------------------------------------------
# Refresh path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRefreshPath:
    @pytest.mark.asyncio
    async def test_live_refresh_maps_provider_result(self):
        machine = _make_machine(status_val="running", provider_data={})
        registry = MagicMock()
        provider_result = MagicMock()
        provider_result.success = True
        provider_result.data = {
            "system": {"status": True, "details": {"status": "ok"}},
            "instance": {"status": True, "details": {"status": "ok"}},
        }
        registry.execute_operation = AsyncMock(return_value=provider_result)

        h = _handler(machine=machine, registry=registry)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001", refresh=True))

        assert result.system_status == "ok"
        assert result.instance_status == "ok"
        assert result.overall_status == "ok"

        # The provider was dispatched a GET_MACHINE_HEALTH operation.
        provider_name, operation = registry.execute_operation.call_args[0]
        assert provider_name == "aws"
        assert operation.operation_type.value == "get_machine_health"
        assert operation.parameters["machine"] is machine

    @pytest.mark.asyncio
    async def test_live_refresh_impaired_when_any_dimension_not_ok(self):
        machine = _make_machine(provider_data={})
        registry = MagicMock()
        provider_result = MagicMock()
        provider_result.success = True
        provider_result.data = {
            "system": {"status": True, "details": {"status": "ok"}},
            "instance": {"status": False, "details": {"status": "impaired"}},
        }
        registry.execute_operation = AsyncMock(return_value=provider_result)

        h = _handler(machine=machine, registry=registry)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001", refresh=True))
        assert result.overall_status == "impaired"

    @pytest.mark.asyncio
    async def test_live_refresh_failure_falls_back_to_stored(self):
        machine = _make_machine(
            status_val="running",
            provider_data={"health_checks": {"status": "ok"}},
        )
        registry = MagicMock()
        registry.execute_operation = AsyncMock(side_effect=RuntimeError("provider down"))

        h = _handler(machine=machine, registry=registry)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001", refresh=True))
        # Falls back to the persisted snapshot.
        assert result.overall_status == "ok"
        assert result.system_status == "not_available"

    @pytest.mark.asyncio
    async def test_live_refresh_all_unknown_dimensions_yields_not_available(self):
        machine = _make_machine(provider_data={})
        registry = MagicMock()
        provider_result = MagicMock()
        provider_result.success = True
        # A successful provider result whose dimensions are all unrecognised:
        # no dimension resolves, so overall health stays not_available rather
        # than being fabricated as ok.
        provider_result.data = {"system": None, "instance": None}
        registry.execute_operation = AsyncMock(return_value=provider_result)

        h = _handler(machine=machine, registry=registry)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001", refresh=True))
        assert result.overall_status == "not_available"
        assert result.system_status == "not_available"
        assert result.instance_status == "not_available"

    @pytest.mark.asyncio
    async def test_live_refresh_transient_failure_dim_is_not_available(self):
        machine = _make_machine(provider_data={})
        registry = MagicMock()
        provider_result = MagicMock()
        provider_result.success = True
        # A transient provider error surfaces as a returned dimension dict with
        # details.reason and no status string. This must read as unknown, not
        # be collapsed into a fabricated "impaired" indistinguishable from a
        # genuinely impaired instance.
        provider_result.data = {
            "system": {"status": False, "details": {"reason": "Network error: timeout"}},
            "instance": {"status": True, "details": {"status": "ok"}},
        }
        registry.execute_operation = AsyncMock(return_value=provider_result)

        h = _handler(machine=machine, registry=registry)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001", refresh=True))
        assert result.system_status == "not_available"
        assert result.instance_status == "ok"

    @pytest.mark.asyncio
    async def test_live_refresh_all_transient_failures_yield_not_available(self):
        machine = _make_machine(provider_data={})
        registry = MagicMock()
        provider_result = MagicMock()
        provider_result.success = True
        # Both dimensions carry only a reason: nothing is known, so overall
        # health is not_available rather than "impaired".
        provider_result.data = {
            "system": {"status": False, "details": {"reason": "Network error"}},
            "instance": {"status": False, "details": {"reason": "Network error"}},
        }
        registry.execute_operation = AsyncMock(return_value=provider_result)

        h = _handler(machine=machine, registry=registry)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001", refresh=True))
        assert result.system_status == "not_available"
        assert result.instance_status == "not_available"
        assert result.overall_status == "not_available"

    @pytest.mark.asyncio
    async def test_live_refresh_non_dict_data_falls_back_to_stored(self):
        machine = _make_machine(
            status_val="running",
            provider_data={"health_checks": {"status": "ok"}},
        )
        registry = MagicMock()
        provider_result = MagicMock()
        provider_result.success = True
        # A successful result whose payload is not a dict is unusable, so the
        # handler falls back to the stored snapshot.
        provider_result.data = ["unexpected"]
        registry.execute_operation = AsyncMock(return_value=provider_result)

        h = _handler(machine=machine, registry=registry)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001", refresh=True))
        assert result.overall_status == "ok"

    @pytest.mark.asyncio
    async def test_live_refresh_none_result_falls_back_to_stored(self):
        machine = _make_machine(
            status_val="running",
            provider_data={"health_checks": {"status": "ok"}},
        )
        registry = MagicMock()
        registry.execute_operation = AsyncMock(return_value=None)

        h = _handler(machine=machine, registry=registry)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001", refresh=True))
        assert result.overall_status == "ok"

    @pytest.mark.asyncio
    async def test_live_refresh_unsuccessful_result_falls_back(self):
        machine = _make_machine(provider_data={})
        registry = MagicMock()
        provider_result = MagicMock()
        provider_result.success = False
        provider_result.data = None
        registry.execute_operation = AsyncMock(return_value=provider_result)

        h = _handler(machine=machine, registry=registry)
        result = await h.execute_query(GetMachineHealthQuery(machine_id="m-001", refresh=True))
        assert result.system_status == "not_available"
        assert result.instance_status == "not_available"
