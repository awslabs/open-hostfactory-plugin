"""Tests for enhanced base registry supporting both single and multi choice patterns."""

from unittest.mock import Mock

import pytest

from src.infrastructure.registry.enhanced_base_registry import (
    EnhancedBaseRegistry,
    RegistryMode,
)


class SingleChoiceTestRegistry(EnhancedBaseRegistry):
    """Test registry for single choice mode."""

    def __init__(self):
        """Initialize the instance."""
        super().__init__(mode=RegistryMode.SINGLE_CHOICE)

    def register(self, type_name, strategy_factory, config_factory, **kwargs):
        self.register_type(type_name, strategy_factory, config_factory, **kwargs)

    def create_strategy(self, type_name, config):
        return self.create_strategy_by_type(type_name, config)


class MultiChoiceTestRegistry(EnhancedBaseRegistry):
    """Test registry for multi choice mode."""

    def __init__(self):
        super().__init__(mode=RegistryMode.MULTI_CHOICE)

    def register(self, type_name, strategy_factory, config_factory, **kwargs):
        self.register_type(type_name, strategy_factory, config_factory, **kwargs)

    def create_strategy(self, type_name, config):
        return self.create_strategy_by_type(type_name, config)


class TestEnhancedBaseRegistry:
    """Test enhanced base registry functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_strategy_factory = Mock(return_value="strategy_instance")
        self.mock_config_factory = Mock(return_value="config_instance")
        self.mock_additional_factory = Mock(return_value="additional_instance")

        # Clear registrations from singleton instances to ensure clean state
        SingleChoiceTestRegistry().clear_registrations()
        MultiChoiceTestRegistry().clear_registrations()

    def test_single_choice_mode_basic_functionality(self):
        """Test single choice mode basic operations."""
        registry = SingleChoiceTestRegistry()

        # Register type
        registry.register("json", self.mock_strategy_factory, self.mock_config_factory)

        # Verify registration
        assert registry.is_type_registered("json")
        assert "json" in registry.get_registered_types()

        # Create strategy
        strategy = registry.create_strategy("json", {"test": "config"})
        assert strategy == "strategy_instance"
        self.mock_strategy_factory.assert_called_once_with({"test": "config"})

    def test_single_choice_mode_prevents_instance_registration(self):
        """Test that single choice mode prevents instance registration."""
        registry = SingleChoiceTestRegistry()

        with pytest.raises(
            ValueError, match="Instance registration only supported in MULTI_CHOICE mode"
        ):
            registry.register_instance(
                "json", "json-primary", self.mock_strategy_factory, self.mock_config_factory
            )

    def test_single_choice_mode_prevents_instance_creation(self):
        """Test that single choice mode prevents instance-based creation."""
        registry = SingleChoiceTestRegistry()
        registry.register("json", self.mock_strategy_factory, self.mock_config_factory)

        with pytest.raises(
            ValueError, match="Instance-based creation only supported in MULTI_CHOICE mode"
        ):
            registry.create_strategy_by_instance("json-primary", {})

    def test_multi_choice_mode_basic_functionality(self):
        """Test multi choice mode basic operations."""
        registry = MultiChoiceTestRegistry()

        # Register type
        registry.register("aws", self.mock_strategy_factory, self.mock_config_factory)

        # Verify registration
        assert registry.is_type_registered("aws")
        assert "aws" in registry.get_registered_types()

        # Create strategy by type
        strategy = registry.create_strategy("aws", {"test": "config"})
        assert strategy == "strategy_instance"

    def test_multi_choice_mode_instance_registration(self):
        """Test multi choice mode instance registration."""
        registry = MultiChoiceTestRegistry()

        # Register type first
        registry.register("aws", self.mock_strategy_factory, self.mock_config_factory)

        # Register instances
        registry.register_instance(
            "aws", "aws-primary", self.mock_strategy_factory, self.mock_config_factory
        )
        registry.register_instance(
            "aws", "aws-secondary", self.mock_strategy_factory, self.mock_config_factory
        )

        # Verify instance registration
        assert registry.is_instance_registered("aws-primary")
        assert registry.is_instance_registered("aws-secondary")
        assert "aws-primary" in registry.get_registered_instances()
        assert "aws-secondary" in registry.get_registered_instances()

        # Create strategies by instance
        primary_strategy = registry.create_strategy_by_instance(
            "aws-primary", {"config": "primary"}
        )
        secondary_strategy = registry.create_strategy_by_instance(
            "aws-secondary", {"config": "secondary"}
        )

        assert primary_strategy == "strategy_instance"
        assert secondary_strategy == "strategy_instance"

    def test_additional_factories_support(self):
        """Test support for additional factories."""
        registry = MultiChoiceTestRegistry()

        # Register with additional factories
        registry.register(
            "aws",
            self.mock_strategy_factory,
            self.mock_config_factory,
            resolver_factory=self.mock_additional_factory,
            validator_factory=self.mock_additional_factory,
        )

        # Create additional components
        resolver = registry.create_additional_component("aws", "resolver_factory")
        validator = registry.create_additional_component("aws", "validator_factory")

        assert resolver == "additional_instance"
        assert validator == "additional_instance"

        # Test non-existent factory
        non_existent = registry.create_additional_component("aws", "non_existent_factory")
        assert non_existent is None

    def test_error_handling(self):
        """Test error handling for unregistered types and instances."""
        registry = MultiChoiceTestRegistry()

        # Test unregistered type
        with pytest.raises(ValueError, match="Type 'unknown' is not registered"):
            registry.create_strategy_by_type("unknown", {})

        # Test unregistered instance
        with pytest.raises(ValueError, match="Instance 'unknown-instance' is not registered"):
            registry.create_strategy_by_instance("unknown-instance", {})

    def test_duplicate_registration_prevention(self):
        """Test prevention of duplicate registrations."""
        registry = MultiChoiceTestRegistry()

        # Register type
        registry.register("aws", self.mock_strategy_factory, self.mock_config_factory)

        # Try to register same type again
        with pytest.raises(ValueError, match="Type 'aws' is already registered"):
            registry.register("aws", self.mock_strategy_factory, self.mock_config_factory)

        # Register instance
        registry.register_instance(
            "aws", "aws-primary", self.mock_strategy_factory, self.mock_config_factory
        )

        # Try to register same instance again
        with pytest.raises(ValueError, match="Instance 'aws-primary' is already registered"):
            registry.register_instance(
                "aws", "aws-primary", self.mock_strategy_factory, self.mock_config_factory
            )

    def test_unregistration(self):
        """Test unregistration functionality."""
        registry = MultiChoiceTestRegistry()

        # Register and then unregister type
        registry.register("aws", self.mock_strategy_factory, self.mock_config_factory)
        assert registry.is_type_registered("aws")

        result = registry.unregister_type("aws")
        assert result is True
        assert not registry.is_type_registered("aws")

        # Try to unregister non-existent type
        result = registry.unregister_type("non-existent")
        assert result is False

        # Register and unregister instance
        registry.register("aws", self.mock_strategy_factory, self.mock_config_factory)
        registry.register_instance(
            "aws", "aws-primary", self.mock_strategy_factory, self.mock_config_factory
        )
        assert registry.is_instance_registered("aws-primary")

        result = registry.unregister_instance("aws-primary")
        assert result is True
        assert not registry.is_instance_registered("aws-primary")

    def test_clear_registrations(self):
        """Test clearing all registrations."""
        registry = MultiChoiceTestRegistry()

        # Register types and instances
        registry.register("aws", self.mock_strategy_factory, self.mock_config_factory)
        registry.register_instance(
            "aws", "aws-primary", self.mock_strategy_factory, self.mock_config_factory
        )

        assert len(registry.get_registered_types()) > 0
        assert len(registry.get_registered_instances()) > 0

        # Clear all
        registry.clear_registrations()

        assert len(registry.get_registered_types()) == 0
        assert len(registry.get_registered_instances()) == 0

    def test_singleton_behavior(self):
        """Test singleton behavior per registry class."""
        registry1 = SingleChoiceTestRegistry()
        registry2 = SingleChoiceTestRegistry()

        assert registry1 is registry2

        multi_registry1 = MultiChoiceTestRegistry()
        multi_registry2 = MultiChoiceTestRegistry()

        assert multi_registry1 is multi_registry2

        # Different registry classes should be different instances
        assert registry1 is not multi_registry1
