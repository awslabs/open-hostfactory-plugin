"""Example: StorageRegistry using EnhancedBaseRegistry (SINGLE_CHOICE mode)."""

from typing import Any, Callable

from .enhanced_base_registry import BaseRegistration, EnhancedBaseRegistry, RegistryMode


class StorageRegistration(BaseRegistration):
    """Storage-specific registration with unit_of_work_factory."""

    def __init__(
        self,
        type_name: str,
        strategy_factory: Callable,
        config_factory: Callable,
        unit_of_work_factory: Callable = None,
    ):
        """Initialize the instance."""
        super().__init__(
            type_name,
            strategy_factory,
            config_factory,
            unit_of_work_factory=unit_of_work_factory,
        )
        self.unit_of_work_factory = unit_of_work_factory


class EnhancedStorageRegistry(EnhancedBaseRegistry):
    """Storage registry using enhanced base - SINGLE_CHOICE mode."""

    def __init__(self):
        # Storage is SINGLE_CHOICE - only one storage strategy at a time
        super().__init__(mode=RegistryMode.SINGLE_CHOICE)

    def register(
        self,
        storage_type: str,
        strategy_factory: Callable,
        config_factory: Callable,
        unit_of_work_factory: Callable = None,
    ):
        """Register storage strategy - implements abstract method."""
        self.register_type(
            storage_type,
            strategy_factory,
            config_factory,
            unit_of_work_factory=unit_of_work_factory,
        )

    def create_strategy(self, storage_type: str, config: Any) -> Any:
        """Create storage strategy - implements abstract method."""
        return self.create_strategy_by_type(storage_type, config)

    def create_unit_of_work(self, storage_type: str) -> Any:
        """Create unit of work for storage type."""
        return self.create_additional_component(storage_type, "unit_of_work_factory")

    def _create_registration(
        self,
        type_name: str,
        strategy_factory: Callable,
        config_factory: Callable,
        **additional_factories,
    ) -> BaseRegistration:
        """Create storage-specific registration."""
        return StorageRegistration(
            type_name,
            strategy_factory,
            config_factory,
            additional_factories.get("unit_of_work_factory"),
        )


# Usage example:
def example_usage():
    registry = EnhancedStorageRegistry()

    # Register storage types (only one active at a time)
    registry.register("json", json_strategy_factory, json_config_factory, json_uow_factory)
    registry.register("sql", sql_strategy_factory, sql_config_factory, sql_uow_factory)

    # Create strategy (single choice - only one at a time)
    registry.create_strategy("json", config)
    registry.create_unit_of_work("json")

    # Cannot register instances (single choice mode)
    # registry.register_instance("json", "json-primary", ...) # Would raise ValueError
