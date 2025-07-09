"""AWS provider configuration."""

from .config import (
    AWSProviderConfig,
    HandlersConfig,
    HandlerCapabilityConfig,
    HandlerDefaultsConfig
)
from .validator import (
    AWSNamingConfig,
    AWSConfigManager,
    get_aws_config_manager
)

__all__ = [
    'AWSProviderConfig',
    'HandlersConfig',
    'HandlerCapabilityConfig', 
    'HandlerDefaultsConfig',
    'AWSNamingConfig',
    'AWSConfigManager',
    'get_aws_config_manager'
]
