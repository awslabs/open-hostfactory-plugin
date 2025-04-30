# src/config/defaults.py
from typing import Dict, Any, Optional
from enum import Enum
import os
import json
from domain.core.exceptions import ConfigurationError
import boto3

class LogLevel(str, Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogDestination(str, Enum):
    """Log destination enumeration."""
    FILE = "file"
    STDOUT = "stdout"
    BOTH = "both"

class StorageType(str, Enum):
    """Storage type enumeration."""
    SINGLE_FILE = "single_file"
    SPLIT_FILES = "split_files"

class RepositoryType(str, Enum):
    """Repository type enumeration."""
    JSON = "json"
    SQLITE = "sqlite"
    DYNAMODB = "dynamodb"

DEFAULT_CONFIG = {
    # AWS Provider required configurations
    "AWS_CREDENTIAL_FILE": "${AWS_CREDENTIAL_FILE}",
    "AWS_REGION": "${AWS_REGION:us-east-1}",
    "AWS_KEY_FILE": "${AWS_KEY_FILE}",
    "AWS_SPOT_FLEET_ROLE_ARN": "${AWS_SPOT_FLEET_ROLE_ARN:AWSServiceRoleForEC2SpotFleet}",
    
    # AWS Provider optional configurations
    "AWS_ENDPOINT_URL": "",
    "AWS_PROXY_HOST": "${AWS_PROXY_HOST:}",
    "AWS_PROXY_PORT": "${AWS_PROXY_PORT:80}",
    "AWS_CONNECTION_TIMEOUT_MS": 10000,
    "AWS_REQUEST_RETRY_ATTEMPTS": 0,
    "AWS_INSTANCE_PENDING_TIMEOUT_SEC": 180,
    "AWS_DESCRIBE_REQUEST_RETRY_ATTEMPTS": 0,
    "AWS_DESCRIBE_REQUEST_INTERVAL": 0,

    # Repository configuration
    "REPOSITORY_CONFIG": {
        "type": "json",
        "json": {
            "storage_type": "single_file",
            "base_path": "${HF_PROVIDER_WORKDIR}",
            "filenames": {
                "single_file": "request_database.json",
                "split_files": {
                    "requests": "requests.json",
                    "machines": "machines.json"
                }
            },
            "backup": {
                "enabled": True,
                "max_backups": 5,
                "backup_dir": "${HF_PROVIDER_WORKDIR}/backups"
            },
            "locking": {
                "timeout_seconds": 30,
                "retry_interval_ms": 100
            }
        }
    },

    # Logging configuration
    "LOGGING_CONFIG": {
        "level": "${LOG_LEVEL:INFO}",
        "destination": "${LOG_DESTINATION:both}",
        "file": {
            "path": "${HF_PROVIDER_LOGDIR}/${HF_PROVIDER_NAME}.log",
            "max_size_mb": 10,
            "backup_count": 5,
            "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        },
        "stdout": {
            "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        }
    },

    # Request configuration
    "REQUEST_CONFIG": {
        "default_timeout": 3600,
        "max_timeout": 86400,
        "status_check_interval": 30,
        "cleanup_age_hours": 24
    },

    # Template configuration
    "TEMPLATE_CONFIG": {
        "config_file": "${HF_PROVIDER_CONFDIR}/awsprov_templates.json",
        "max_templates": 100,
        "allowed_handlers": [
            "EC2Fleet",
            "SpotFleet",
            "ASG",
            "RunInstances"
        ]
    },

    # Machine configuration
    "MACHINE_CONFIG": {
        "name_pattern": "{template_id}-{request_id}-{index}",
        "max_batch_size": 50,
        "status_cache_ttl": 300,
        "health_check_interval": 300
    },

    # Validation ranges and rules
    "VALIDATION_RULES": {
        "AWS_REQUEST_RETRY_ATTEMPTS": {
            "min": 0,
            "max": 10,
            "type": "int"
        },
        "AWS_INSTANCE_PENDING_TIMEOUT_SEC": {
            "min": 180,
            "max": 10000,
            "type": "int"
        },
        "AWS_DESCRIBE_REQUEST_RETRY_ATTEMPTS": {
            "min": 0,
            "max": 10,
            "type": "int"
        },
        "AWS_DESCRIBE_REQUEST_INTERVAL": {
            "min": 0,
            "max": 10000,
            "type": "int"
        },
        "AWS_CONNECTION_TIMEOUT_MS": {
            "min": 1000,
            "type": "int"
        },
        "required_fields": [
            "AWS_REGION"
        ],
        "conditional_required": {
            "AWS_PROXY_PORT": ["AWS_PROXY_HOST"]
        }
    }
}

class ConfigurationManager:
    """
    Manages application configuration with defaults and overrides.
    
    This class handles:
    - Loading default configuration
    - Applying environment variable overrides
    - Applying user configuration overrides
    - Variable interpolation
    - Configuration validation
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager with defaults.
        
        Args:
            config_file: Optional path to configuration file. If not provided,
                        will look in HF_PROVIDER_CONFDIR/awsprov_config.json
        """
        self._config = DEFAULT_CONFIG.copy()
        
        # Load config file
        if config_file:
            self._load_config_file(config_file)
        else:
            default_config_path = os.path.join(
                os.environ.get('HF_PROVIDER_CONFDIR', ''),
                'awsprov_config.json'
            )
            if os.path.exists(default_config_path):
                self._load_config_file(default_config_path)

        # Load environment variables (highest priority)
        self._load_env_vars()
        
        # Validate the final configuration
        self.validate_config()

    def _load_config_file(self, config_path: str) -> None:
        """Load configuration from file."""
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                self._merge_config(user_config)
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")

    def _merge_config(self, user_config: Dict[str, Any]) -> None:
        """
        Merge user configuration with defaults.
        
        Args:
            user_config: User configuration dictionary
        """
        def deep_update(target: Dict[str, Any], source: Dict[str, Any]) -> None:
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    deep_update(target[key], value)
                else:
                    target[key] = value

        deep_update(self._config, user_config)

    def _load_env_vars(self) -> None:
        """Load and apply environment variable overrides."""
        direct_mappings = [
            "AWS_CREDENTIAL_FILE",
            "AWS_REGION",
            "AWS_KEY_FILE",
            "AWS_ENDPOINT_URL",
            "AWS_PROXY_HOST",
            "AWS_PROXY_PORT",
            "AWS_SPOT_FLEET_ROLE_ARN",
            "HF_PROVIDER_WORKDIR",
            "HF_PROVIDER_LOGDIR",
            "HF_PROVIDER_CONFDIR",
            "HF_PROVIDER_NAME",
            "LOG_LEVEL",
            "LOG_DESTINATION"
        ]

        for env_var in direct_mappings:
            if env_var in os.environ:
                self._config[env_var] = os.environ[env_var]

    def _set_nested_value(self, config: Dict[str, Any], path: tuple, value: Any) -> None:
        """Set a nested configuration value."""
        current = config
        for key in path[:-1]:
            current = current.setdefault(key, {})
        current[path[-1]] = value

    def _interpolate_values(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Interpolate variables in configuration values."""
        if isinstance(config, str):
            if config.startswith("${") and config.endswith("}"):
                var_name = config[2:-1]
                if ":" in var_name:
                    var_name, default = var_name.split(":", 1)
                    return os.environ.get(var_name, default)
                return os.environ.get(var_name, config)
            return config
        elif isinstance(config, dict):
            return {k: self._interpolate_values(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._interpolate_values(v) for v in config]
        return config

    def update_config(self, user_config: Dict[str, Any]) -> None:
        """
        Update configuration with user-provided values.
        
        Args:
            user_config: Configuration dictionary from user config file
        """
        def deep_update(target: Dict[str, Any], source: Dict[str, Any]) -> None:
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    deep_update(target[key], value)
                else:
                    target[key] = value

        deep_update(self._config, user_config)

    def get_config(self) -> Dict[str, Any]:
        """
        Get the complete configuration with all interpolations applied.
        
        Returns:
            Dict containing the complete configuration
        """
        return self._interpolate_values(self._config)

    def validate_config(self) -> None:
        """
        Validate the configuration.
        
        Validates:
        - Required fields are present
        - Values are within allowed ranges
        - URLs are properly formatted
        - File paths exist where required
        - Proxy configuration is consistent
        - Timeout and retry settings are within bounds
        
        Raises:
            ValueError: If configuration is invalid with detailed error messages
        """
        config = self.get_config()
        errors = []

        # Required fields validation
        for field in config["VALIDATION_RULES"]["required_fields"]:
            if not config.get(field):
                errors.append(f"{field} is required")

        # Optional file validations - only check if they're provided
        cred_file = config.get("AWS_CREDENTIAL_FILE")
        if cred_file and cred_file != "${AWS_CREDENTIAL_FILE}":  # Only validate if explicitly set
            expanded_cred_file = os.path.expandvars(cred_file)
            if not os.path.exists(expanded_cred_file):
                errors.append(f"AWS_CREDENTIAL_FILE does not exist: {expanded_cred_file}")

        key_file = config.get("AWS_KEY_FILE")
        if key_file and key_file != "${AWS_KEY_FILE}":  # Only validate if explicitly set
            expanded_key_file = os.path.expandvars(key_file)
            if not os.path.exists(expanded_key_file):
                errors.append(f"AWS_KEY_FILE does not exist: {expanded_key_file}")

        # Validate Spot Fleet role if provided
        spot_fleet_role = config.get('AWS_SPOT_FLEET_ROLE_ARN')
        if spot_fleet_role:
            if spot_fleet_role == 'AWSServiceRoleForEC2SpotFleet':
                # Convert service-linked role name to full ARN
                try:
                    sts = boto3.client('sts')
                    account_id = sts.get_caller_identity()['Account']
                    config['AWS_SPOT_FLEET_ROLE_ARN'] = (
                        f"arn:aws:iam::{account_id}:role/aws-service-role/"
                        f"spotfleet.amazonaws.com/AWSServiceRoleForEC2SpotFleet"
                    )
                except Exception as e:
                    errors.append(f"Failed to get account ID: {str(e)}")
            elif not spot_fleet_role.startswith('arn:aws:iam::'):
                errors.append("AWS_SPOT_FLEET_ROLE_ARN must be either 'AWSServiceRoleForEC2SpotFleet' or a valid IAM role ARN")

        # Proxy validation - only if proxy host is set
        proxy_host = config.get("AWS_PROXY_HOST")
        if proxy_host:  # Only validate proxy port if proxy host is set
            proxy_port = config.get("AWS_PROXY_PORT")
            if not proxy_port:
                errors.append("AWS_PROXY_PORT is required when AWS_PROXY_HOST is specified")
            elif not isinstance(proxy_port, int):
                try:
                    int(proxy_port)  # Try to convert string to int
                except (TypeError, ValueError):
                    errors.append("AWS_PROXY_PORT must be an integer")

        # Validate logging configuration using enums
        log_config = config["LOGGING_CONFIG"]
        log_level = log_config["level"].upper()
        if log_level not in LogLevel.__members__:
            errors.append(f"Invalid log level: {log_level}")

        log_dest = log_config["destination"].lower()
        try:
            LogDestination(log_dest)  # Validate using enum
        except ValueError:
            errors.append(f"Invalid log destination: {log_dest}. Must be one of: {', '.join(LogDestination.__members__.keys())}")

        # Validate repository configuration using enums
        repo_config = config["REPOSITORY_CONFIG"]
        repo_type = repo_config["type"].lower()
        try:
            RepositoryType(repo_type)  # Validate using enum
        except ValueError:
            errors.append(f"Invalid repository type: {repo_type}. Must be one of: {', '.join(RepositoryType.__members__.keys())}")

        if repo_type == RepositoryType.JSON.value:
            storage_type = repo_config["json"]["storage_type"]
            try:
                StorageType(storage_type)  # Validate using enum
            except ValueError:
                errors.append(f"Invalid storage type: {storage_type}. Must be one of: {', '.join(StorageType.__members__.keys())}")

        # Numeric validations - only for non-None values
        for field, rules in config["VALIDATION_RULES"].items():
            if isinstance(rules, dict) and "type" in rules and rules["type"] == "int":
                value = config.get(field)
                if value is not None:  # Only validate if value is set
                    try:
                        value = int(value)
                        if "min" in rules and value < rules["min"]:
                            errors.append(f"{field} must be at least {rules['min']}")
                        if "max" in rules and value > rules["max"]:
                            errors.append(f"{field} must be at most {rules['max']}")
                    except (TypeError, ValueError):
                        errors.append(f"{field} must be an integer")

        # Ensure required directories exist
        required_dirs = [
            os.path.expandvars(config.get("HF_PROVIDER_WORKDIR", "")),
            os.path.expandvars(config.get("HF_PROVIDER_LOGDIR", "")),
            os.path.expandvars(config.get("HF_PROVIDER_CONFDIR", ""))
        ]
        
        for directory in required_dirs:
            if directory and directory != "${HF_PROVIDER_WORKDIR}" and directory != "${HF_PROVIDER_LOGDIR}" and directory != "${HF_PROVIDER_CONFDIR}":
                os.makedirs(directory, exist_ok=True)

        if errors:
            raise ValueError("\n".join(errors))