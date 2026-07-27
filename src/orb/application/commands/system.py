"""System-level commands for administrative operations."""

from typing import Any, Optional

from pydantic import ConfigDict

from orb.application.dto.base import BaseCommand

# ============================================================================
# Provider Configuration Management Commands
# ============================================================================


class ReloadProviderConfigCommand(BaseCommand):
    """Command to reload provider configuration from file.

    CQRS: Commands should not return data. Results are stored in mutable fields.
    """

    config_path: Optional[str] = None

    # Mutable result fields for CQRS compliance
    result: Optional[dict[str, Any]] = None

    model_config = ConfigDict(frozen=False)


class RefreshTemplatesCommand(BaseCommand):
    """Command to refresh templates from all sources.

    CQRS: Commands should not return data. Results are stored in mutable fields.
    """

    provider_name: Optional[str] = None

    # Mutable result fields for CQRS compliance
    result: Optional[dict[str, Any]] = None

    model_config = ConfigDict(frozen=False)


class SetConfigurationCommand(BaseCommand):
    """Command to set configuration value.

    CQRS: Commands should not return data. Results are stored in mutable fields.
    """

    key: str
    value: str
    # Persist the change to the loaded config file. Defaults to True because a
    # CLI process exits immediately after running, so an in-memory-only set
    # would be lost the moment the command returns.
    persist: bool = True

    # Mutable result fields for CQRS compliance
    result: Optional[dict[str, Any]] = None

    model_config = ConfigDict(frozen=False)
