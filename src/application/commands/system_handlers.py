"""System command handlers for administrative operations."""
from typing import Dict, Any
from src.application.interfaces.command_handler import CommandHandler
from src.application.commands.system import MigrateRepositoryCommand, ReloadProviderConfigCommand, MigrateProviderConfigCommand
from src.domain.base.dependency_injection import injectable
from src.domain.base.ports import LoggingPort, ContainerPort


@injectable
class MigrateRepositoryHandler(CommandHandler[MigrateRepositoryCommand, Dict[str, Any]]):
    """Handler for repository migration operations."""
    
    def __init__(self, logger: LoggingPort, container: ContainerPort):
        """
        Initialize migrate repository handler.
        
        Args:
            logger: Logging port for operation logging
            container: Container port for dependency access
        """
        self.logger = logger
        self.container = container
    
    
    def handle(self, command: MigrateRepositoryCommand) -> Dict[str, Any]:
        """
        Handle repository migration command.
        
        Args:
            command: Migration command with source/target types and options
            
        Returns:
            Migration result with statistics and status
        """
        self.logger.info(f"Starting repository migration from {command.source_type} to {command.target_type}")
        
        try:
            # Get repository migrator from container
            from src.infrastructure.persistence.repository_migrator import RepositoryMigrator
            migrator = RepositoryMigrator(self.container.get_container())
            
            # Execute migration using existing infrastructure
            result = migrator.migrate(
                source_type=command.source_type,
                target_type=command.target_type,
                batch_size=command.batch_size,
                create_backup=command.create_backup
            )
            
            # Add command metadata to result
            result.update({
                "command_id": command.command_id,
                "requested_options": command.options,
                "status": result.get("status", "completed")
            })
            
            self.logger.info(f"Repository migration completed: {result.get('total_migrated', 0)} records migrated")
            return result
            
        except Exception as e:
            self.logger.error(f"Repository migration failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "command_id": command.command_id,
                "source_type": command.source_type,
                "target_type": command.target_type
            }


# ============================================================================
# Provider Configuration Management Handlers
# ============================================================================

@injectable
class ReloadProviderConfigHandler(CommandHandler[ReloadProviderConfigCommand, Dict[str, Any]]):
    """Handler for reloading provider configuration."""
    
    def __init__(self, logger: LoggingPort, container: ContainerPort):
        """
        Initialize reload provider config handler.
        
        Args:
            logger: Logging port for operation logging
            container: Container port for dependency access
        """
        self.logger = logger
        self.container = container
    
    
    def handle(self, command: ReloadProviderConfigCommand) -> Dict[str, Any]:
        """
        Handle provider configuration reload command.
        
        Args:
            command: Reload command with optional config path
            
        Returns:
            Reload result with status and configuration information
        """
        self.logger.info(f"Reloading provider configuration from: {command.config_path or 'default location'}")
        
        try:
            # Get configuration manager from container
            from src.domain.base.ports import ConfigurationPort
            config_manager = self.container.get(ConfigurationPort)
            
            # Reload configuration (implementation depends on ConfigurationManager capabilities)
            if hasattr(config_manager, 'reload'):
                config_manager.reload(command.config_path)
            else:
                # Fallback: create new configuration manager instance using factory
                from src.config.manager import get_config_manager
                new_config_manager = get_config_manager(command.config_path)
                
            # Get updated provider information
            if hasattr(config_manager, 'get_provider_config'):
                unified_config = config_manager.get_provider_config()
                provider_mode = unified_config.get_mode().value
                active_providers = [p.name for p in unified_config.get_active_providers()]
            else:
                provider_mode = "legacy"
                active_providers = []
            
            result = {
                "status": "success",
                "message": "Provider configuration reloaded successfully",
                "config_path": command.config_path,
                "provider_mode": provider_mode,
                "active_providers": active_providers,
                "command_id": command.command_id
            }
            
            self.logger.info("Provider configuration reload completed successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Provider configuration reload failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "command_id": command.command_id,
                "config_path": command.config_path
            }


@injectable
class MigrateProviderConfigHandler(CommandHandler[MigrateProviderConfigCommand, Dict[str, Any]]):
    """Handler for migrating provider configuration to unified format."""
    
    def __init__(self, logger: LoggingPort, container: ContainerPort):
        """
        Initialize migrate provider config handler.
        
        Args:
            logger: Logging port for operation logging
            container: Container port for dependency access
        """
        self.logger = logger
        self.container = container
    
    
    def handle(self, command: MigrateProviderConfigCommand) -> Dict[str, Any]:
        """
        Handle provider configuration migration command.
        
        Args:
            command: Migration command with options
            
        Returns:
            Migration result with status and summary
        """
        self.logger.info(f"Migrating provider configuration (save={command.save_to_file}, backup={command.backup_original})")
        
        try:
            # Get configuration manager from container
            from src.domain.base.ports import ConfigurationPort
            config_manager = self.container.get(ConfigurationPort)
            
            # Perform migration using ConfigurationManager
            if hasattr(config_manager, 'migrate_to_unified_format'):
                migration_summary = config_manager.migrate_to_unified_format(
                    save_to_file=command.save_to_file,
                    backup_original=command.backup_original
                )
            else:
                # Fallback: use migration utility directly
                from src.config.migration import ConfigurationMigrator
                migrator = ConfigurationMigrator(self.logger)
                
                # Get current configuration
                raw_config = config_manager.get_raw_config() if hasattr(config_manager, 'get_raw_config') else {}
                
                # Migrate configuration
                migrated_config = migrator.migrate_to_unified_format(raw_config)
                migration_summary = migrator.get_migration_summary(raw_config, migrated_config)
            
            result = {
                "status": "success",
                "message": "Provider configuration migration completed",
                "migration_summary": migration_summary,
                "save_to_file": command.save_to_file,
                "backup_original": command.backup_original,
                "command_id": command.command_id
            }
            
            self.logger.info("Provider configuration migration completed successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Provider configuration migration failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "command_id": command.command_id,
                "save_to_file": command.save_to_file,
                "backup_original": command.backup_original
            }
