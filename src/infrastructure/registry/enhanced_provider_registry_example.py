"""Example: ProviderRegistry using EnhancedBaseRegistry (MULTI_CHOICE mode)."""

from typing import Any, Callable, Dict

from .enhanced_base_registry import BaseRegistration, EnhancedBaseRegistry, RegistryMode


class ProviderRegistration(BaseRegistration):
    """Provider-specific registration with resolver and validator factories."""

    def __init__(
        self,
        type_name: str,
        strategy_factory: Callable,
        config_factory: Callable,
        resolver_factory: Callable = None,
        validator_factory: Callable = None,
    ):
        super().__init__(
            type_name,
            strategy_factory,
            config_factory,
            resolver_factory=resolver_factory,
            validator_factory=validator_factory,
        )
        self.resolver_factory = resolver_factory
        self.validator_factory = validator_factory


class EnhancedProviderRegistry(EnhancedBaseRegistry):
    """Provider registry using enhanced base - MULTI_CHOICE mode."""

    def __init__(self):
        # Provider is MULTI_CHOICE - multiple provider strategies simultaneously
        super().__init__(mode=RegistryMode.MULTI_CHOICE)

    def register(
        self,
        provider_type: str,
        strategy_factory: Callable,
        config_factory: Callable,
        resolver_factory: Callable = None,
        validator_factory: Callable = None,
    ):
        """Register provider type - implements abstract method."""
        self.register_type(
            provider_type,
            strategy_factory,
            config_factory,
            resolver_factory=resolver_factory,
            validator_factory=validator_factory,
        )

    def register_provider_instance(
        self,
        provider_type: str,
        instance_name: str,
        strategy_factory: Callable,
        config_factory: Callable,
        resolver_factory: Callable = None,
        validator_factory: Callable = None,
    ):
        """Register named provider instance."""
        self.register_instance(
            provider_type,
            instance_name,
            strategy_factory,
            config_factory,
            resolver_factory=resolver_factory,
            validator_factory=validator_factory,
        )

    def create_strategy(self, provider_type: str, config: Any) -> Any:
        """Create provider strategy by type - implements abstract method."""
        return self.create_strategy_by_type(provider_type, config)

    def create_strategy_from_instance(self, instance_name: str, config: Any) -> Any:
        """Create provider strategy by instance name."""
        return self.create_strategy_by_instance(instance_name, config)

    def create_resolver(self, provider_type: str) -> Any:
        """Create resolver for provider type."""
        return self.create_additional_component(provider_type, "resolver_factory")

    def create_validator(self, provider_type: str) -> Any:
        """Create validator for provider type."""
        return self.create_additional_component(provider_type, "validator_factory")

    def _create_registration(
        self,
        type_name: str,
        strategy_factory: Callable,
        config_factory: Callable,
        **additional_factories,
    ) -> BaseRegistration:
        """Create provider-specific registration."""
        return ProviderRegistration(
            type_name,
            strategy_factory,
            config_factory,
            additional_factories.get("resolver_factory"),
            additional_factories.get("validator_factory"),
        )


# Usage example:
def example_usage():
    registry = EnhancedProviderRegistry()

    # Register provider types
    registry.register(
        "aws", aws_strategy_factory, aws_config_factory, aws_resolver_factory, aws_validator_factory
    )
    registry.register("azure", azure_strategy_factory, azure_config_factory)

    # Register multiple instances of same provider type (multi choice mode)
    registry.register_provider_instance(
        "aws", "aws-primary", aws_strategy_factory, aws_config_factory
    )
    registry.register_provider_instance(
        "aws", "aws-secondary", aws_strategy_factory, aws_config_factory
    )
    registry.register_provider_instance(
        "azure", "azure-backup", azure_strategy_factory, azure_config_factory
    )

    # Create strategies by type
    aws_strategy = registry.create_strategy("aws", aws_config)

    # Create strategies by instance (multiple instances simultaneously)
    primary_aws = registry.create_strategy_from_instance("aws-primary", config1)
    secondary_aws = registry.create_strategy_from_instance("aws-secondary", config2)
    backup_azure = registry.create_strategy_from_instance("azure-backup", config3)

    # Create additional components
    aws_resolver = registry.create_resolver("aws")
    aws_validator = registry.create_validator("aws")
