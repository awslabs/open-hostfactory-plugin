"""Scheduler Registry - Registry pattern for scheduler strategy factories."""
from typing import Any, Callable
from .base_registry import BaseRegistry, BaseRegistration, RegistryMode
from src.domain.base.exceptions import ConfigurationError


class UnsupportedSchedulerError(Exception):
    """Exception raised when an unsupported scheduler type is requested."""
    pass


class SchedulerRegistration(BaseRegistration):
    """Scheduler registration container."""
    
    def __init__(self, scheduler_type: str, strategy_factory: Callable, config_factory: Callable):
        super().__init__(scheduler_type, strategy_factory, config_factory)
        self.scheduler_type = scheduler_type


class SchedulerRegistry(BaseRegistry):
    """
    Registry for scheduler strategy factories.
    
    Uses SINGLE_CHOICE mode - only one scheduler strategy at a time.
    Thread-safe singleton implementation using unified BaseRegistry.
    """
    
    def __init__(self):
        # Scheduler is SINGLE_CHOICE - only one scheduler strategy at a time
        super().__init__(mode=RegistryMode.SINGLE_CHOICE)
    
    def register(self, scheduler_type: str, strategy_factory: Callable, config_factory: Callable, **kwargs):
        """Register scheduler strategy factory - implements abstract method."""
        try:
            self.register_type(scheduler_type, strategy_factory, config_factory, **kwargs)
        except ValueError as e:
            raise ConfigurationError(str(e)) from e
    
    def create_strategy(self, scheduler_type: str, config: Any) -> Any:
        """Create scheduler strategy - implements abstract method."""
        try:
            return self.create_strategy_by_type(scheduler_type, config)
        except ValueError as e:
            raise UnsupportedSchedulerError(str(e)) from e
    
    def _create_registration(self, type_name: str, strategy_factory: Callable, config_factory: Callable, **additional_factories) -> BaseRegistration:
        """Create scheduler-specific registration."""
        return SchedulerRegistration(type_name, strategy_factory, config_factory)


def get_scheduler_registry() -> SchedulerRegistry:
    """Get the singleton scheduler registry instance."""
    return SchedulerRegistry()
