"""Machine-related commands for CQRS implementation."""

from typing import Any

from orb.application.dto.base import BaseCommand


class UpdateMachineStatusCommand(BaseCommand):
    """Command to update machine status."""

    machine_id: str
    status: str
    metadata: dict[str, Any] = {}


class CleanupMachineResourcesCommand(BaseCommand):
    """Command to cleanup machine resources."""

    machine_ids: list[str]
    force_cleanup: bool = False
    metadata: dict[str, Any] = {}


class UpdateMachineProviderDataCommand(BaseCommand):
    """Merge a partial dict into a machine's provider_data.

    Existing keys not present in *updates* are preserved.  The caller
    supplies only the keys it wants to add or overwrite.
    """

    machine_id: str
    updates: dict[str, Any]
