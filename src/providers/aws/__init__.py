"""AWS Provider implementation."""

from src.providers.aws.strategy.aws_provider_strategy import AWSProviderStrategy
from src.providers.aws.configuration.config import AWSProviderConfig
from src.providers.aws.configuration.template_extension import AWSTemplateExtensionConfig, AMIResolutionConfig
from src.providers.aws.registration import (
    register_aws_extensions, 
    get_aws_extension_defaults,
    register_aws_template_factory,
    initialize_aws_provider,
    is_aws_provider_registered
)

__all__ = [
    'AWSProviderStrategy',
    'AWSProviderConfig',
    'AWSTemplateExtensionConfig',
    'AMIResolutionConfig',
    'register_aws_extensions',
    'get_aws_extension_defaults',
    'register_aws_template_factory',
    'initialize_aws_provider',
    'is_aws_provider_registered'
]
