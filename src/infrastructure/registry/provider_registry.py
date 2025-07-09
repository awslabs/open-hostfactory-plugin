"""Provider Registry - Registry pattern for provider strategy factories.

This module implements the registry pattern for provider creation, eliminating
hard-coded provider conditionals and enabling true OCP compliance.
"""

from typing import Dict, Callable, Optional, List, Any
import threading
from abc import ABC, abstractmethod

from src.domain.base.exceptions import ConfigurationError
from src.infrastructure.logging.logger import get_logger


class UnsupportedProviderError(Exception):
    """Exception raised when an unsupported provider type is requested."""
    pass


class ProviderFactoryInterface(ABC):
    """Interface for provider factory functions."""
    
    @abstractmethod
    def create_strategy(self, config: Any) -> Any:
        """Create a provider strategy."""
        pass
    
    @abstractmethod
    def create_config(self, data: Dict[str, Any]) -> Any:
        """Create a provider configuration."""
        pass


class ProviderRegistration:
    """Container for provider registration information."""
    
    def __init__(self,
                 provider_type: str,
                 strategy_factory: Callable,
                 config_factory: Callable,
                 resolver_factory: Optional[Callable] = None,
                 validator_factory: Optional[Callable] = None):
        """
        Initialize provider registration.
        
        Args:
            provider_type: Type identifier for the provider (e.g., 'aws', 'provider1')
            strategy_factory: Factory function to create provider strategy
            config_factory: Factory function to create provider configuration
            resolver_factory: Optional factory for template resolver
            validator_factory: Optional factory for template validator
        """
        self.provider_type = provider_type
        self.strategy_factory = strategy_factory
        self.config_factory = config_factory
        self.resolver_factory = resolver_factory
        self.validator_factory = validator_factory


class ProviderRegistry:
    """
    Registry for provider strategy factories.
    
    This class implements the registry pattern to eliminate hard-coded provider
    conditionals and enable true Open/Closed Principle compliance. New providers
    can be added by registering their factories without modifying existing code.
    
    Thread-safe singleton implementation.
    """
    
    _instance: Optional['ProviderRegistry'] = None
    _lock = threading.RLock()
    
    def __init__(self):
        """Initialize provider registry."""
        self._registrations: Dict[str, ProviderRegistration] = {}
        self._instance_registrations: Dict[str, ProviderRegistration] = {}  # For named instances
        self._logger = get_logger(__name__)
        self._registration_lock = threading.RLock()
    
    @classmethod
    def get_instance(cls) -> 'ProviderRegistry':
        """Get singleton instance of provider registry."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def register_provider(self,
                         provider_type: str,
                         strategy_factory: Callable,
                         config_factory: Callable,
                         resolver_factory: Optional[Callable] = None,
                         validator_factory: Optional[Callable] = None) -> None:
        """
        Register a provider with its factory functions.
        
        Args:
            provider_type: Type identifier for the provider (e.g., 'aws', 'provider1')
            strategy_factory: Factory function to create provider strategy
            config_factory: Factory function to create provider configuration
            resolver_factory: Optional factory for template resolver
            validator_factory: Optional factory for template validator
            
        Raises:
            ValueError: If provider_type is already registered
        """
        with self._registration_lock:
            if provider_type in self._registrations:
                raise ValueError(f"Provider type '{provider_type}' is already registered")
            
            registration = ProviderRegistration(
                provider_type=provider_type,
                strategy_factory=strategy_factory,
                config_factory=config_factory,
                resolver_factory=resolver_factory,
                validator_factory=validator_factory
            )
            
            self._registrations[provider_type] = registration
            self._logger.info(f"Registered provider: {provider_type}")
    
    def register_provider_instance(self,
                                 provider_type: str,
                                 instance_name: str,
                                 strategy_factory: Callable,
                                 config_factory: Callable,
                                 resolver_factory: Optional[Callable] = None,
                                 validator_factory: Optional[Callable] = None) -> None:
        """
        Register a named provider instance with its factory functions.
        
        Args:
            provider_type: Type identifier for the provider (e.g., 'aws')
            instance_name: Unique name for this provider instance (e.g., 'aws-us-east-1')
            strategy_factory: Factory function to create provider strategy
            config_factory: Factory function to create provider configuration
            resolver_factory: Optional factory for template resolver
            validator_factory: Optional factory for template validator
            
        Raises:
            ValueError: If instance_name is already registered
        """
        with self._registration_lock:
            if instance_name in self._instance_registrations:
                raise ValueError(f"Provider instance '{instance_name}' is already registered")
            
            registration = ProviderRegistration(
                provider_type=provider_type,
                strategy_factory=strategy_factory,
                config_factory=config_factory,
                resolver_factory=resolver_factory,
                validator_factory=validator_factory
            )
            
            self._instance_registrations[instance_name] = registration
            self._logger.info(f"Registered provider instance: {instance_name} (type: {provider_type})")
    
    def unregister_provider_instance(self, instance_name: str) -> bool:
        """
        Unregister a named provider instance.
        
        Args:
            instance_name: Name of the provider instance
            
        Returns:
            True if instance was unregistered, False if not found
        """
        with self._registration_lock:
            if instance_name in self._instance_registrations:
                del self._instance_registrations[instance_name]
                self._logger.info(f"Unregistered provider instance: {instance_name}")
                return True
            return False
    
    def is_provider_instance_registered(self, instance_name: str) -> bool:
        """
        Check if a provider instance is registered.
        
        Args:
            instance_name: Name of the provider instance
            
        Returns:
            True if instance is registered, False otherwise
        """
        return instance_name in self._instance_registrations
    
    def get_registered_provider_instances(self) -> List[str]:
        """
        Get list of all registered provider instance names.
        
        Returns:
            List of registered provider instance names
        """
        return list(self._instance_registrations.keys())
    
    def get_provider_instance_registration(self, instance_name: str) -> Optional[ProviderRegistration]:
        """
        Get registration for a specific provider instance.
        
        Args:
            instance_name: Name of the provider instance
            
        Returns:
            ProviderRegistration if found, None otherwise
        """
        return self._instance_registrations.get(instance_name)
    
    def unregister_provider(self, provider_type: str) -> bool:
        """
        Unregister a provider.
        
        Args:
            provider_type: Type identifier for the provider
            
        Returns:
            True if provider was unregistered, False if not found
        """
        with self._registration_lock:
            if provider_type in self._registrations:
                del self._registrations[provider_type]
                self._logger.info(f"Unregistered provider: {provider_type}")
                return True
            return False
    
    def is_provider_registered(self, provider_type: str) -> bool:
        """
        Check if a provider type is registered.
        
        Args:
            provider_type: Type identifier for the provider
            
        Returns:
            True if provider is registered, False otherwise
        """
        return provider_type in self._registrations
    
    def get_registered_providers(self) -> List[str]:
        """
        Get list of all registered provider types.
        
        Returns:
            List of registered provider type identifiers
        """
        return list(self._registrations.keys())
    
    def create_strategy(self, provider_type: str, config: Any) -> Any:
        """
        Create a provider strategy using registered factory.
        
        Args:
            provider_type: Type identifier for the provider
            config: Configuration object for the provider
            
        Returns:
            Created provider strategy instance
            
        Raises:
            UnsupportedProviderError: If provider type is not registered
        """
        if provider_type not in self._registrations:
            available_providers = ', '.join(self.get_registered_providers())
            raise UnsupportedProviderError(
                f"Provider type '{provider_type}' is not registered. "
                f"Available providers: {available_providers}"
            )
        
        registration = self._registrations[provider_type]
        try:
            strategy = registration.strategy_factory(config)
            self._logger.debug(f"Created strategy for provider: {provider_type}")
            return strategy
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create strategy for provider '{provider_type}': {str(e)}"
            ) from e
    
    def create_strategy_from_instance(self, instance_name: str, config: Any) -> Any:
        """
        Create a provider strategy from a named instance using registered factory.
        
        Args:
            instance_name: Name of the provider instance
            config: Configuration object for the provider
            
        Returns:
            Created provider strategy instance
            
        Raises:
            UnsupportedProviderError: If provider instance is not registered
        """
        if instance_name not in self._instance_registrations:
            available_instances = ', '.join(self.get_registered_provider_instances())
            raise UnsupportedProviderError(
                f"Provider instance '{instance_name}' is not registered. "
                f"Available instances: {available_instances}"
            )
        
        registration = self._instance_registrations[instance_name]
        try:
            strategy = registration.strategy_factory(config)
            self._logger.debug(f"Created strategy for provider instance: {instance_name}")
            return strategy
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create strategy for provider instance '{instance_name}': {str(e)}"
            ) from e
    
    def create_config(self, provider_type: str, data: Dict[str, Any]) -> Any:
        """
        Create a provider configuration using registered factory.
        
        Args:
            provider_type: Type identifier for the provider
            data: Configuration data dictionary
            
        Returns:
            Created provider configuration instance
            
        Raises:
            UnsupportedProviderError: If provider type is not registered
        """
        if provider_type not in self._registrations:
            available_providers = ', '.join(self.get_registered_providers())
            raise UnsupportedProviderError(
                f"Provider type '{provider_type}' is not registered. "
                f"Available providers: {available_providers}"
            )
        
        registration = self._registrations[provider_type]
        try:
            config = registration.config_factory(data)
            self._logger.debug(f"Created config for provider: {provider_type}")
            return config
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create config for provider '{provider_type}': {str(e)}"
            ) from e
    
    def create_resolver(self, provider_type: str) -> Optional[Any]:
        """
        Create a template resolver using registered factory.
        
        Args:
            provider_type: Type identifier for the provider
            
        Returns:
            Created template resolver instance or None if not registered
            
        Raises:
            UnsupportedProviderError: If provider type is not registered
        """
        if provider_type not in self._registrations:
            return None
        
        registration = self._registrations[provider_type]
        if registration.resolver_factory is None:
            return None
        
        try:
            resolver = registration.resolver_factory()
            self._logger.debug(f"Created resolver for provider: {provider_type}")
            return resolver
        except Exception as e:
            self._logger.warning(f"Failed to create resolver for provider '{provider_type}': {str(e)}")
            return None
    
    def create_validator(self, provider_type: str) -> Optional[Any]:
        """
        Create a template validator using registered factory.
        
        Args:
            provider_type: Type identifier for the provider
            
        Returns:
            Created template validator instance or None if not registered
            
        Raises:
            UnsupportedProviderError: If provider type is not registered
        """
        if provider_type not in self._registrations:
            return None
        
        registration = self._registrations[provider_type]
        if registration.validator_factory is None:
            return None
        
        try:
            validator = registration.validator_factory()
            self._logger.debug(f"Created validator for provider: {provider_type}")
            return validator
        except Exception as e:
            self._logger.warning(f"Failed to create validator for provider '{provider_type}': {str(e)}")
            return None
    
    def clear_registrations(self) -> None:
        """Clear all provider registrations. Used primarily for testing."""
        with self._registration_lock:
            self._registrations.clear()
            self._logger.info("Cleared all provider registrations")


# Convenience function for global access
def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance."""
    return ProviderRegistry.get_instance()
