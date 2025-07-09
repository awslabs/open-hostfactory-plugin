"""Unified configuration management for the application."""
from __future__ import annotations
import logging
import os
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Type, TypeVar, cast, List, TYPE_CHECKING

from src.domain.base.exceptions import ConfigurationError
from src.config.loader import ConfigurationLoader
from src.config.schemas.provider_strategy_schema import ProviderMode

# Import config classes for runtime use
from src.config import (
    AppConfig,
    ProviderConfig,
    LoggingConfig,
    TemplateConfig,
    EventsConfig,
    StorageConfig,
    NamingConfig,
    RequestConfig,
    ResourceConfig,
    DatabaseConfig,
    StatusValuesConfig,
    LimitsConfig,
    CircuitBreakerConfig
)

# Use TYPE_CHECKING for imports that are only needed for type hints
if TYPE_CHECKING:
    from src.config.loader import ConfigurationLoader
    from src.config.schemas.provider_strategy_schema import ProviderConfig, ProviderInstanceConfig

T = TypeVar('T')
logger = logging.getLogger(__name__)

class ConfigurationManager:
    """
    Unified configuration manager that serves as the single source of truth.
    
    This class provides a unified interface for accessing configuration with:
    - Type safety through dataclasses
    - Support for legacy and new configuration formats
    - Environment variable overrides
    - Configuration validation
    - Lazy loading for performance
    
    It uses ConfigurationLoader to load configuration from multiple sources.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration manager with lazy loading."""
        self._config_file = config_file
        self._lock = threading.RLock()
        self._app_config: Optional['AppConfig'] = None
        self._loader: Optional['ConfigurationLoader'] = None
        self._config_cache: Dict[Type, Any] = {}
        
    @property
    def loader(self) -> 'ConfigurationLoader':
        """Lazy load configuration loader."""
        if self._loader is None:
            from src.config.loader import ConfigurationLoader
            self._loader = ConfigurationLoader()
        return self._loader
    
    @property
    def app_config(self) -> 'AppConfig':
        """Lazy load application configuration."""
        if self._app_config is None:
            with self._lock:
                if self._app_config is None:
                    self._app_config = self._load_app_config()
        return self._app_config
    
    def _load_app_config(self) -> 'AppConfig':
        """Load application configuration from sources."""
        from src.config import AppConfig
        
        # Load configuration from file if provided
        if self._config_file and os.path.exists(self._config_file):
            config_data = self.loader.load_from_file(self._config_file)
        else:
            # Load from default locations
            config_data = self.loader.load_configuration()
        
        # Apply environment variable overrides
        config_data = self.loader.apply_environment_overrides(config_data)
        
        # Create and validate configuration
        return AppConfig.from_dict(config_data)
    
    def get_typed(self, config_type: Type[T]) -> T:
        """Get typed configuration with caching."""
        if config_type not in self._config_cache:
            with self._lock:
                if config_type not in self._config_cache:
                    self._config_cache[config_type] = self._create_typed_config(config_type)
        return self._config_cache[config_type]
    
    def _create_typed_config(self, config_type: Type[T]) -> T:
        """Create typed configuration instance."""
        # Map config types to app_config attributes
        type_mapping = {
            'ProviderConfig': 'provider',
            'LoggingConfig': 'logging',
            'TemplateConfig': 'template',
            'EventsConfig': 'events',
            'StorageConfig': 'storage',
            'NamingConfig': 'naming',
            'RequestConfig': 'request',
            'ResourceConfig': 'resource',
            'DatabaseConfig': 'database',
            'StatusValuesConfig': 'status_values',
            'LimitsConfig': 'limits',
            'CircuitBreakerConfig': 'circuit_breaker',
            'ServerConfig': 'server'
        }
        
        config_name = config_type.__name__
        if config_name in type_mapping:
            attr_name = type_mapping[config_name]
            return getattr(self.app_config, attr_name)
        else:
            raise ValueError(f"Unknown configuration type: {config_name}")
    
    def get_storage_strategy(self) -> str:
        """Get storage strategy with caching."""
        return self.app_config.storage.strategy
    
    def get_provider_type(self) -> str:
        """Get provider type with caching."""
        return self.app_config.provider.type
    
    def reload(self) -> None:
        """Reload configuration from sources."""
        with self._lock:
            self._app_config = None
            self._config_cache.clear()
            # Force reload on next access
    
    def get_provider_config(self) -> Optional['ProviderConfig']:
        """Get provider configuration."""
        try:
            from src.config.schemas.provider_strategy_schema import ProviderConfig
            
            # Check if provider config exists in app config
            if hasattr(self.app_config, 'unified_provider') and self.app_config.unified_provider:
                return ProviderConfig.from_dict(self.app_config.unified_provider)
            return None
        except (ImportError, AttributeError):
            return None

    # Singleton instance with thread safety
    _instance: Optional[ConfigurationManager] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> ConfigurationManager:
        """Thread-safe singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize configuration manager.
        
        Args:
            config_path: Optional path to configuration file
        """
        # Only initialize once
        if hasattr(self, 'initialized'):
            return
            
        self.initialized = True
        
        # Load configuration
        self.raw_config = ConfigurationLoader.load(config_path)
        
        # Create typed configuration
        self._app_config = ConfigurationLoader.create_app_config(self.raw_config)
        
        logger.info("Configuration loaded successfully")

    @property
    def config(self) -> AppConfig:
        """Get typed application configuration."""
        if not hasattr(self, '_app_config') or self._app_config is None:
            raise ConfigurationError("Manager", "Configuration not initialized")
        return self._app_config

    def get_raw_config(self) -> Dict[str, Any]:
        """Get raw configuration dictionary."""
        return ConfigurationLoader._deep_copy(self.raw_config)
        
    def get_app_config(self) -> Dict[str, Any]:
        """
        Get structured application configuration.
        
        Returns the raw configuration dictionary for backward compatibility.
        This method is used by repository factories and other components.
        """
        return self.get_raw_config()
        
    def get_app_config(self) -> Dict[str, Any]:
        """Get application configuration dictionary.
        
        This is an alias for get_raw_config() for backward compatibility.
        """
        return self.get_raw_config()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.
        
        Args:
            key: Configuration key (dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.raw_config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
                
        return value
        
    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Get boolean configuration value.
        
        Args:
            key: Configuration key (dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Boolean configuration value
        """
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'y', 'on')
        if isinstance(value, int):
            return value != 0
        return bool(value)
        
    def get_int(self, key: str, default: int = 0) -> int:
        """
        Get integer configuration value.
        
        Args:
            key: Configuration key (dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Integer configuration value
        """
        value = self.get(key, default)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        if isinstance(value, float):
            return int(value)
        return default
        
    def get_float(self, key: str, default: float = 0.0) -> float:
        """
        Get float configuration value.
        
        Args:
            key: Configuration key (dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Float configuration value
        """
        value = self.get(key, default)
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return default
        return default
        
    def get_str(self, key: str, default: str = '') -> str:
        """
        Get string configuration value.
        
        Args:
            key: Configuration key (dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            String configuration value
        """
        value = self.get(key, default)
        if value is None:
            return default
        return str(value)
        
    def get_list(self, key: str, default: Optional[List[Any]] = None) -> List[Any]:
        """
        Get list configuration value.
        
        Args:
            key: Configuration key (dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            List configuration value
        """
        default = default or []
        value = self.get(key, default)
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [value]
        return default
        
    def get_dict(self, key: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get dictionary configuration value.
        
        Args:
            key: Configuration key (dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Dictionary configuration value
        """
        default = default or {}
        value = self.get(key, default)
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default
        return default

    def get_typed(self, config_class: Type[T]) -> T:
        """
        Get typed configuration object.
        
        Args:
            config_class: Configuration class
            
        Returns:
            Typed configuration object
            
        Raises:
            ConfigurationError: If configuration not found
        """
        if not self.app_config:
            raise ConfigurationError("Manager", "Configuration not initialized")
        # Import AWS config from provider directory
        try:
            from src.providers.aws.configuration.config import AWSProviderConfig
            aws_config = self.app_config.provider.aws if self.app_config.provider.type == 'aws' else None
        except ImportError:
            AWSProviderConfig = None
            aws_config = None
            
        # Direct mapping to Pydantic models
        config_mapping = {
            AppConfig: self.app_config,
            ProviderConfig: self.app_config.provider,
            LoggingConfig: self.app_config.logging,
            EventsConfig: self.app_config.events,
            StorageConfig: self.app_config.storage,
            NamingConfig: self.app_config.naming,
            ResourceConfig: self.app_config.resource,
            StatusValuesConfig: self.app_config.naming.statuses,
            LimitsConfig: self.app_config.naming.limits,
            RequestConfig: self.app_config.request,
            DatabaseConfig: self.app_config.database,
            CircuitBreakerConfig: self.app_config.circuit_breaker
        }
        
        # Add ServerConfig
        from src.config.schemas.server_schema import ServerConfig
        config_mapping[ServerConfig] = self.app_config.server
        
        # Add AWSProviderConfig if available
        if AWSProviderConfig:
            config_mapping[AWSProviderConfig] = aws_config
        
        if config_class == TemplateConfig:
            if not self.app_config.template:
                raise ConfigurationError("Template", "Template configuration not available")
            return cast(T, self.app_config.template)
        
        if config_class in config_mapping:
            return cast(T, config_mapping[config_class])
            
        raise ConfigurationError("Manager", f"Unknown configuration class: {config_class.__name__}")

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        keys = key.split('.')
        current = self.raw_config
        
        for i, k in enumerate(keys):
            if i == len(keys) - 1:
                current[k] = value
            else:
                current = current.setdefault(k, {})

        # Recreate typed configuration
        self.app_config = ConfigurationLoader.create_app_config(self.raw_config)

    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple configuration values.
        
        Args:
            updates: Dictionary of updates
        """
        ConfigurationLoader._merge_config(self.raw_config, updates)
        self._app_config = ConfigurationLoader.create_app_config(self.raw_config)

    def resolve_path(self, path_type: str, default_path: str, config_path: Optional[str] = None) -> str:
        """
        Resolve a path based on HF_PROVIDER_* environment variables, config, or defaults.
        
        Args:
            path_type: Type of path ('work', 'conf', 'log', 'events', 'snapshots')
            default_path: Default path to use as last resort
            config_path: Path from configuration file (optional)
            
        Returns:
            Resolved path
        """
        # Check environment variables first
        if path_type == 'work' and 'HF_PROVIDER_WORKDIR' in os.environ:
            path = os.environ['HF_PROVIDER_WORKDIR']
            logger.debug(f"Using HF_PROVIDER_WORKDIR for {path_type} path: {path}")
            return path
        elif path_type == 'conf' and 'HF_PROVIDER_CONFDIR' in os.environ:
            path = os.environ['HF_PROVIDER_CONFDIR']
            logger.debug(f"Using HF_PROVIDER_CONFDIR for {path_type} path: {path}")
            return path
        elif path_type == 'log' and 'HF_PROVIDER_LOGDIR' in os.environ:
            path = os.environ['HF_PROVIDER_LOGDIR']
            logger.debug(f"Using HF_PROVIDER_LOGDIR for {path_type} path: {path}")
            return path
        elif path_type == 'events' and 'HF_PROVIDER_EVENTSDIR' in os.environ:
            path = os.environ['HF_PROVIDER_EVENTSDIR']
            logger.debug(f"Using HF_PROVIDER_EVENTSDIR for {path_type} path: {path}")
            return path
        elif path_type == 'snapshots' and 'HF_PROVIDER_SNAPSHOTSDIR' in os.environ:
            path = os.environ['HF_PROVIDER_SNAPSHOTSDIR']
            logger.debug(f"Using HF_PROVIDER_SNAPSHOTSDIR for {path_type} path: {path}")
            return path
        
        # Check config path next
        if config_path:
            logger.debug(f"Using config-defined path for {path_type}: {config_path}")
            return config_path
        
        # Fall back to default
        logger.debug(f"Using default path for {path_type}: {default_path}")
        return default_path

    def resolve_file(self, file_type: str, filename: str, default_dir: Optional[str] = None, 
                     explicit_path: Optional[str] = None) -> str:
        """
        Resolve a configuration file path with consistent priority:
        1. Explicit path (if provided and contains directory)
        2. HF_PROVIDER_*DIR + filename (if file exists)
        3. Default directory + filename
        
        Args:
            file_type: Type of file ('conf', 'template', 'legacy', 'log', 'work', 'events', 'snapshots')
            filename: Name of the file
            default_dir: Default directory (optional, will use resolve_path if not provided)
            explicit_path: Explicit path provided by user (optional)
            
        Returns:
            Resolved file path
        """
        logger.debug(f"Resolving file: type={file_type}, filename={filename}, explicit_path={explicit_path}")
        
        # 1. If explicit path provided and contains directory, use it directly
        if explicit_path and os.path.dirname(explicit_path):
            logger.debug(f"Using explicit path with directory: {explicit_path}")
            return explicit_path
        
        # If explicit_path is just a filename, use it as the filename
        if explicit_path and not os.path.dirname(explicit_path):
            filename = explicit_path
            logger.debug(f"Using explicit filename: {filename}")
        
        # 2. Try environment variable directory + filename
        env_dir = None
        env_var_name = None
        
        if file_type in ['conf', 'template', 'legacy']:
            env_dir = os.environ.get('HF_PROVIDER_CONFDIR')
            env_var_name = 'HF_PROVIDER_CONFDIR'
        elif file_type == 'log':
            env_dir = os.environ.get('HF_PROVIDER_LOGDIR')
            env_var_name = 'HF_PROVIDER_LOGDIR'
        elif file_type == 'work':
            env_dir = os.environ.get('HF_PROVIDER_WORKDIR')
            env_var_name = 'HF_PROVIDER_WORKDIR'
        elif file_type == 'events':
            env_dir = os.environ.get('HF_PROVIDER_EVENTSDIR')
            env_var_name = 'HF_PROVIDER_EVENTSDIR'
        elif file_type == 'snapshots':
            env_dir = os.environ.get('HF_PROVIDER_SNAPSHOTSDIR')
            env_var_name = 'HF_PROVIDER_SNAPSHOTSDIR'
        
        if env_dir:
            env_path = os.path.join(env_dir, filename)
            if os.path.exists(env_path):
                logger.debug(f"Found file using {env_var_name}: {env_path}")
                return env_path
            else:
                logger.debug(f"File not found in {env_var_name} directory: {env_path}")
        
        # 3. Fall back to default directory + filename
        if default_dir is None:
            # Map file types to path types for resolve_path
            path_type_mapping = {
                'conf': 'conf',
                'template': 'conf',
                'legacy': 'conf',
                'log': 'log',
                'work': 'work',
                'events': 'events',
                'snapshots': 'snapshots'
            }
            
            path_type = path_type_mapping.get(file_type, 'conf')
            default_dir = self.resolve_path(path_type, 'config' if path_type == 'conf' else path_type)
        
        fallback_path = os.path.join(default_dir, filename)
        logger.debug(f"Using fallback path: {fallback_path}")
        return fallback_path
    
    def get_work_dir(self, default_path: Optional[str] = None, config_path: Optional[str] = None) -> str:
        """
        Get work directory path.
        
        Args:
            default_path: Default path to use as last resort
            config_path: Path from configuration file (optional)
            
        Returns:
            Resolved work directory path
        """
        # If default_path is not provided, use the default_storage_path from StorageConfig
        if default_path is None:
            try:
                storage_config = self.get_typed(StorageConfig)
                default_path = storage_config.default_storage_path
            except Exception:
                default_path = "data"
                
        path = self.resolve_path('work', default_path, config_path)
        # Ensure directory exists
        Path(path).mkdir(parents=True, exist_ok=True)
        return path
        
    def get_conf_dir(self, default_path: Optional[str] = None, config_path: Optional[str] = None) -> str:
        """
        Get configuration directory path.
        
        Args:
            default_path: Default path to use as last resort
            config_path: Path from configuration file (optional)
            
        Returns:
            Resolved configuration directory path
        """
        # If default_path is not provided, use a default value
        if default_path is None:
            default_path = "config"
                
        path = self.resolve_path('conf', default_path, config_path)
        # Ensure directory exists
        Path(path).mkdir(parents=True, exist_ok=True)
        return path
        
    def get_log_dir(self, default_path: Optional[str] = None, config_path: Optional[str] = None) -> str:
        """
        Get log directory path.
        
        Args:
            default_path: Default path to use as last resort
            config_path: Path from configuration file (optional)
            
        Returns:
            Resolved log directory path
        """
        # If default_path is not provided, use a default value
        if default_path is None:
            try:
                logging_config = self.get_typed(LoggingConfig)
                if logging_config.file_path:
                    # Extract directory from file path
                    default_path = os.path.dirname(logging_config.file_path)
                else:
                    default_path = "logs"
            except Exception:
                default_path = "logs"
                
        path = self.resolve_path('log', default_path, config_path)
        # Ensure directory exists
        Path(path).mkdir(parents=True, exist_ok=True)
        return path
    
    def get_events_dir(self, default_path: Optional[str] = None, config_path: Optional[str] = None) -> str:
        """
        Get events directory path.
        
        Args:
            default_path: Default path to use as last resort
            config_path: Path from configuration file (optional)
            
        Returns:
            Resolved events directory path
        """
        # If default_path is not provided, use the default_events_path from EventsConfig
        if default_path is None:
            try:
                events_config = self.get_typed(EventsConfig)
                default_path = events_config.default_events_path
            except Exception:
                default_path = "events"
                
        path = self.resolve_path('events', default_path, config_path)
        # Ensure directory exists
        Path(path).mkdir(parents=True, exist_ok=True)
        return path
        
    def get_snapshots_dir(self, default_path: Optional[str] = None, config_path: Optional[str] = None) -> str:
        """
        Get snapshots directory path.
        
        Args:
            default_path: Default path to use as last resort
            config_path: Path from configuration file (optional)
            
        Returns:
            Resolved snapshots directory path
        """
        # If default_path is not provided, use the default_snapshots_path from EventsConfig
        if default_path is None:
            try:
                events_config = self.get_typed(EventsConfig)
                default_path = events_config.default_snapshots_path
            except Exception:
                default_path = "snapshots"
                
        path = self.resolve_path('snapshots', default_path, config_path)
        # Ensure directory exists
        Path(path).mkdir(parents=True, exist_ok=True)
        return path
    
    def get_provider_config(self) -> ProviderConfig:
        """Get provider configuration."""
        if not self.app_config:
            raise ConfigurationError("Manager", "Configuration not initialized")
        return self.app_config.provider
    
    
    def get_handler_factory(self) -> 'HandlerFactory':
        """
        Get handler factory for the configured provider.
        
        Returns:
            Handler factory instance
            
        Raises:
            ConfigurationError: If provider type is unsupported
        """
        provider_config = self.get_provider_config()
        
        if provider_config.type == 'aws':
            if provider_config.aws is None:
                raise ConfigurationError("Provider", "AWS provider configuration is missing")
            return AWSHandlerFactory(provider_config.aws)
        
        raise ConfigurationError("Provider", f"Unsupported provider type: {provider_config.type}")
    
    # ============================================================================
    # Unified Provider Configuration Methods - Added for Provider Strategy Support
    # ============================================================================
    
    def get_unified_provider_config(self) -> 'ProviderConfig':
        """
        Get unified provider configuration with automatic migration.
        
        Returns:
            ProviderConfig instance
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        from .schemas.provider_strategy_schema import ProviderConfig
        from .migration import ConfigurationMigrator
        
        try:
            provider_data = self.raw_config.get('provider', {})
            
            # Check if already in unified format
            if 'providers' in provider_data:
                logger.debug("Using existing unified provider configuration")
                return ProviderConfig(**provider_data)
            
            # Migrate legacy format
            logger.info("Migrating legacy provider configuration to unified format")
            migrator = ConfigurationMigrator(logger)
            migrated_config = migrator.migrate_to_unified_format(self.raw_config)
            
            # Validate migration
            if not migrator.validate_migration(self.raw_config, migrated_config):
                raise ConfigurationError("Provider", "Configuration migration validation failed")
            
            # Update raw config with migrated version (in memory only)
            migrated_provider_data = migrated_config.get('provider', {})
            provider_config = ProviderConfig(**migrated_provider_data)
            
            # Log migration summary
            summary = migrator.get_migration_summary(self.raw_config, migrated_config)
            logger.info(f"Configuration migration completed: {summary}")
            
            return provider_config
            
        except Exception as e:
            raise ConfigurationError("Provider", f"Failed to get unified provider configuration: {str(e)}")
    
    def is_provider_strategy_enabled(self) -> bool:
        """
        Check if provider strategy is enabled.
        
        Returns:
            True if provider strategy is enabled (always True now)
        """
        try:
            provider_config = self.get_unified_provider_config()
            return provider_config.get_mode() != ProviderMode.NONE
        except Exception:
            return False
    
    def is_multi_provider_mode(self) -> bool:
        """
        Check if multi-provider mode is enabled.
        
        Returns:
            True if multi-provider mode is enabled
        """
        try:
            provider_config = self.get_unified_provider_config()
            return provider_config.is_multi_provider_mode()
        except Exception:
            return False
    
    def get_provider_mode(self) -> str:
        """
        Get current provider mode.
        
        Returns:
            Provider mode string ('single', 'multi', 'legacy', 'none')
        """
        try:
            provider_config = self.get_unified_provider_config()
            return provider_config.get_mode().value
        except Exception:
            return 'none'
    
    def get_active_provider_names(self) -> List[str]:
        """
        Get list of active provider names.
        
        Returns:
            List of active provider names
        """
        try:
            provider_config = self.get_unified_provider_config()
            active_providers = provider_config.get_active_providers()
            return [provider.name for provider in active_providers]
        except Exception:
            return []
    
    def get_provider_instance_config(self, provider_name: str) -> Optional['ProviderInstanceConfig']:
        """
        Get configuration for specific provider instance.
        
        Args:
            provider_name: Name of provider instance
            
        Returns:
            ProviderInstanceConfig if found, None otherwise
        """
        try:
            provider_config = self.get_unified_provider_config()
            return provider_config.get_provider_by_name(provider_name)
        except Exception:
            return None
    
    def save_unified_provider_config(self, provider_config: 'ProviderConfig') -> None:
        """
        Save unified provider configuration to raw config.
        
        Args:
            provider_config: ProviderConfig to save
        """
        try:
            # Convert to dict and update raw config
            provider_dict = provider_config.model_dump(exclude_none=True)
            self.raw_config['provider'] = provider_dict
            
            # Recreate typed configuration
            self.app_config = ConfigurationLoader.create_app_config(self.raw_config)
            
            logger.info("Unified provider configuration saved successfully")
            
        except Exception as e:
            raise ConfigurationError("Provider", f"Failed to save unified provider configuration: {str(e)}")
    
    def migrate_to_unified_format(self, save_to_file: bool = False, backup_original: bool = True) -> Dict[str, Any]:
        """
        Migrate current configuration to unified format.
        
        Args:
            save_to_file: Whether to save migrated configuration to file
            backup_original: Whether to backup original configuration
            
        Returns:
            Migration summary
        """
        from .migration import ConfigurationMigrator
        
        try:
            migrator = ConfigurationMigrator(logger)
            
            # Backup original if requested
            if backup_original and save_to_file:
                backup_path = f"{self.config_path}.backup"
                self.save(backup_path)
                logger.info(f"Original configuration backed up to {backup_path}")
            
            # Migrate configuration
            migrated_config = migrator.migrate_to_unified_format(self.raw_config)
            
            # Validate migration
            if not migrator.validate_migration(self.raw_config, migrated_config):
                raise ConfigurationError("Provider", "Configuration migration validation failed")
            
            # Update in-memory configuration
            self.raw_config = migrated_config
            self.app_config = ConfigurationLoader.create_app_config(self.raw_config)
            
            # Save to file if requested
            if save_to_file and hasattr(self, 'config_path'):
                self.save(self.config_path)
                logger.info("Migrated configuration saved to file")
            
            # Get migration summary
            summary = migrator.get_migration_summary(self.raw_config, migrated_config)
            logger.info(f"Configuration migration completed successfully: {summary}")
            
            return summary
            
        except Exception as e:
            raise ConfigurationError("Provider", f"Failed to migrate configuration: {str(e)}")
    
    def save(self, config_path: str) -> None:
        """
        Save current configuration to file.
        
        Args:
            config_path: Path to save configuration
            
        Raises:
            ConfigurationError: If save fails
        """
        try:
            import json
            
            path = Path(config_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with path.open('w') as f:
                json.dump(self.raw_config, f, indent=2)
                logger.info(f"Saved configuration to {config_path}")

        except Exception as e:
            raise ConfigurationError("File", f"Failed to save configuration: {str(e)}")

def get_config_manager(config_path: Optional[str] = None) -> ConfigurationManager:
    """
    Get the configuration manager singleton instance.
    
    This function creates ConfigurationManager directly without DI container interference.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Configuration manager instance
    """
    # Create ConfigurationManager directly, bypassing any DI container logic
    # Use object.__new__ to avoid __init__ interception by injectable decorator
    config_manager = object.__new__(ConfigurationManager)
    
    # Call the original __init__ method directly
    ConfigurationManager.__init__(config_manager, config_path)
    
    return config_manager
    
    return config_manager
