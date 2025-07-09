"""System-level commands for administrative operations."""
from typing import Optional, Dict, Any
from src.application.dto.base import BaseCommand


class MigrateRepositoryCommand(BaseCommand):
    """Command to migrate repository data between storage types."""
    
    source_type: str
    target_type: str
    batch_size: int = 100
    create_backup: bool = True
    options: Optional[Dict[str, Any]] = None


# ============================================================================
# Provider Configuration Management Commands
# ============================================================================

class ReloadProviderConfigCommand(BaseCommand):
    """Command to reload provider configuration from file."""
    
    config_path: Optional[str] = None


class MigrateProviderConfigCommand(BaseCommand):
    """Command to migrate provider configuration to unified format."""
    
    save_to_file: bool = False
    backup_original: bool = True
