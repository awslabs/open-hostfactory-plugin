"""System-level commands for administrative operations."""

from typing import Any, Dict, Optional

from src.application.dto.base import BaseCommand

# ============================================================================
# Provider Configuration Management Commands
# ============================================================================


class ReloadProviderConfigCommand(BaseCommand):
    """Command to reload provider configuration from file."""

    config_path: Optional[str] = None
