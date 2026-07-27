"""Unit tests for application/commands/machine_handlers.py.

Covers UpdateMachineStatusHandler, CleanupMachineResourcesHandler and
UpdateMachineProviderDataHandler: happy path, not-found/error paths, and
verification that the correct repository/provider port methods are called.

Domain aggregates (Machine) are used as real objects; only abstract ports
(MachineRepository, ProviderRegistryService, event/logging/error ports) are
mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from orb.application.commands.machine_handlers import (
    CleanupMachineResourcesHandler,
    UpdateMachineProviderDataHandler,
    UpdateMachineStatusHandler,
)
from orb.application.machine.commands import (
    CleanupMachineResourcesCommand,
    UpdateMachineProviderDataCommand,
    UpdateMachineStatusCommand,
)
from orb.domain.base.exceptions import ApplicationError
from orb.domain.base.operations import OperationResult
from orb.domain.machine.aggregate import Machine
from orb.domain.machine.exceptions import MachineNotFoundError
from orb.domain.machine.machine_status import MachineStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_machine(
    machine_id: str = "i-abc123",
    status: MachineStatus = MachineStatus.RUNNING,
    provider_name: str = "aws",
    provider_data: dict | None = None,
) -> Machine:
    return Machine(
        machine_id=machine_id,
        template_id="tpl-1",
        provider_type="aws",
        provider_name=provider_name,
        provider_api="RunInstances",
        instance_type="t3.small",
        image_id="ami-1",
        status=status,
        provider_data=provider_data or {},
    )


def _make_repo(machine: Machine | None) -> MagicMock:
    repo = MagicMock()
    repo.find_by_id.return_value = machine
    return repo


def _ports() -> dict:
    return {
        "event_publisher": MagicMock(),
        "logger": MagicMock(),
        "error_handler": MagicMock(),
    }


# ---------------------------------------------------------------------------
# UpdateMachineStatusHandler
# ---------------------------------------------------------------------------


class TestUpdateMachineStatusHandler:
    @pytest.mark.asyncio
    async def test_looks_up_machine_and_saves(self):
        machine = _make_machine(status=MachineStatus.RUNNING)
        repo = _make_repo(machine)
        handler = UpdateMachineStatusHandler(machine_repository=repo, **_ports())

        await handler.handle(UpdateMachineStatusCommand(machine_id="i-abc123", status="stopping"))

        repo.find_by_id.assert_called_once_with("i-abc123")
        repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_accepts_enum_status(self):
        machine = _make_machine(status=MachineStatus.RUNNING)
        repo = _make_repo(machine)
        handler = UpdateMachineStatusHandler(machine_repository=repo, **_ports())

        await handler.handle(
            UpdateMachineStatusCommand(machine_id="i-abc123", status=MachineStatus.STOPPING)
        )

        repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_saves_machine_with_updated_status(self):
        # Machine is immutable: update_status returns a new machine and does not
        # mutate the original. The handler must persist the returned instance,
        # so the machine handed to save() must carry the NEW status.
        machine = _make_machine(status=MachineStatus.RUNNING)
        repo = _make_repo(machine)
        handler = UpdateMachineStatusHandler(machine_repository=repo, **_ports())

        await handler.handle(UpdateMachineStatusCommand(machine_id="i-abc123", status="stopping"))

        repo.save.assert_called_once()
        saved = repo.save.call_args.args[0]
        assert saved.status == MachineStatus.STOPPING

    @pytest.mark.asyncio
    async def test_publishes_status_changed_event(self):
        # update_status attaches a MachineStatusChangedEvent to the returned
        # aggregate; save() extracts it and the handler must publish it.
        machine = _make_machine(status=MachineStatus.RUNNING)
        repo = _make_repo(machine)
        sentinel_event = object()
        repo.save.return_value = [sentinel_event]
        ports = _ports()
        handler = UpdateMachineStatusHandler(machine_repository=repo, **ports)

        await handler.handle(UpdateMachineStatusCommand(machine_id="i-abc123", status="stopping"))

        ports["event_publisher"].publish.assert_called_once_with(sentinel_event)

    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        repo = _make_repo(None)
        handler = UpdateMachineStatusHandler(machine_repository=repo, **_ports())

        with pytest.raises(MachineNotFoundError):
            await handler.handle(
                UpdateMachineStatusCommand(machine_id="i-missing", status="stopping")
            )
        repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_machine_id_fails_validation(self):
        repo = _make_repo(None)
        handler = UpdateMachineStatusHandler(machine_repository=repo, **_ports())

        with pytest.raises(ValueError):
            await handler.handle(UpdateMachineStatusCommand(machine_id="", status="stopping"))

    @pytest.mark.asyncio
    async def test_missing_status_fails_validation(self):
        repo = _make_repo(None)
        handler = UpdateMachineStatusHandler(machine_repository=repo, **_ports())

        with pytest.raises(ValueError):
            await handler.handle(UpdateMachineStatusCommand(machine_id="i-abc123", status=""))


# ---------------------------------------------------------------------------
# CleanupMachineResourcesHandler
# ---------------------------------------------------------------------------


class TestCleanupMachineResourcesHandler:
    def _handler(self, repo: MagicMock, registry: MagicMock) -> CleanupMachineResourcesHandler:
        return CleanupMachineResourcesHandler(
            machine_repository=repo,
            provider_registry_service=registry,
            **_ports(),
        )

    @pytest.mark.asyncio
    async def test_dispatches_cleanup_and_terminalises(self):
        machine = _make_machine(status=MachineStatus.RUNNING)
        repo = _make_repo(machine)
        registry = MagicMock()

        async def _execute(provider_name, operation):
            return OperationResult.success_result(data={})

        registry.execute_operation = _execute
        handler = self._handler(repo, registry)

        await handler.handle(CleanupMachineResourcesCommand(machine_ids=["i-abc123"]))

        repo.save.assert_called_once()
        saved = repo.save.call_args.args[0]
        assert saved.status == MachineStatus.TERMINATED

    @pytest.mark.asyncio
    async def test_missing_machine_skipped(self):
        repo = _make_repo(None)
        registry = MagicMock()
        registry.execute_operation = MagicMock()
        handler = self._handler(repo, registry)

        await handler.handle(CleanupMachineResourcesCommand(machine_ids=["i-missing"]))

        registry.execute_operation.assert_not_called()
        repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_terminal_machine_skipped_without_force(self):
        machine = _make_machine(status=MachineStatus.TERMINATED)
        repo = _make_repo(machine)
        registry = MagicMock()
        registry.execute_operation = MagicMock()
        handler = self._handler(repo, registry)

        await handler.handle(CleanupMachineResourcesCommand(machine_ids=["i-abc123"]))

        registry.execute_operation.assert_not_called()
        repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_terminal_machine_cleaned_with_force(self):
        machine = _make_machine(status=MachineStatus.TERMINATED)
        repo = _make_repo(machine)
        registry = MagicMock()

        async def _execute(provider_name, operation):
            return OperationResult.success_result(data={})

        registry.execute_operation = _execute
        handler = self._handler(repo, registry)

        await handler.handle(
            CleanupMachineResourcesCommand(machine_ids=["i-abc123"], force_cleanup=True)
        )

        repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_provider_failure_raises_without_force(self):
        machine = _make_machine(status=MachineStatus.RUNNING)
        repo = _make_repo(machine)
        registry = MagicMock()

        async def _execute(provider_name, operation):
            return OperationResult.error_result(error_message="boom")

        registry.execute_operation = _execute
        handler = self._handler(repo, registry)

        with pytest.raises(ApplicationError):
            await handler.handle(CleanupMachineResourcesCommand(machine_ids=["i-abc123"]))
        repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_provider_exception_raises_without_force(self):
        machine = _make_machine(status=MachineStatus.RUNNING)
        repo = _make_repo(machine)
        registry = MagicMock()

        async def _execute(provider_name, operation):
            raise RuntimeError("registry down")

        registry.execute_operation = _execute
        handler = self._handler(repo, registry)

        with pytest.raises(ApplicationError):
            await handler.handle(CleanupMachineResourcesCommand(machine_ids=["i-abc123"]))
        repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_provider_exception_terminalises_with_force(self):
        machine = _make_machine(status=MachineStatus.RUNNING)
        repo = _make_repo(machine)
        registry = MagicMock()

        async def _execute(provider_name, operation):
            raise RuntimeError("registry down")

        registry.execute_operation = _execute
        handler = self._handler(repo, registry)

        await handler.handle(
            CleanupMachineResourcesCommand(machine_ids=["i-abc123"], force_cleanup=True)
        )

        repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_machine_ids_fails_validation(self):
        repo = _make_repo(None)
        registry = MagicMock()
        handler = self._handler(repo, registry)

        with pytest.raises(ValueError):
            await handler.handle(CleanupMachineResourcesCommand(machine_ids=[]))


# ---------------------------------------------------------------------------
# UpdateMachineProviderDataHandler
# ---------------------------------------------------------------------------


class TestUpdateMachineProviderDataHandler:
    @pytest.mark.asyncio
    async def test_merges_provider_data_and_saves(self):
        machine = _make_machine(provider_data={"a": 1, "b": 2})
        repo = _make_repo(machine)
        handler = UpdateMachineProviderDataHandler(machine_repository=repo, **_ports())

        await handler.handle(
            UpdateMachineProviderDataCommand(machine_id="i-abc123", updates={"b": 3, "c": 4})
        )

        repo.save.assert_called_once()
        saved = repo.save.call_args.args[0]
        assert saved.provider_data == {"a": 1, "b": 3, "c": 4}

    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        repo = _make_repo(None)
        handler = UpdateMachineProviderDataHandler(machine_repository=repo, **_ports())

        with pytest.raises(MachineNotFoundError):
            await handler.handle(
                UpdateMachineProviderDataCommand(machine_id="i-missing", updates={"a": 1})
            )
        repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_machine_id_fails_validation(self):
        repo = _make_repo(None)
        handler = UpdateMachineProviderDataHandler(machine_repository=repo, **_ports())

        with pytest.raises(ValueError):
            await handler.handle(UpdateMachineProviderDataCommand(machine_id="", updates={"a": 1}))
