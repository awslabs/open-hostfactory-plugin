"""Provider-specific template store interfaces and implementations.

This module defines the provider extension pattern for template storage,
allowing different providers to implement their own storage mechanisms
while maintaining a consistent interface.

Follows the Strategy pattern and Provider pattern for extensibility.
"""
from typing import List, Optional, Dict, Any, Protocol, runtime_checkable
from abc import ABC, abstractmethod

from .dtos import TemplateDTO


@runtime_checkable
class ProviderTemplateStore(Protocol):
    """
    Protocol for provider-specific template storage.
    
    This protocol defines the interface that all provider-specific
    template stores must implement. Examples include:
    - AWS SSM Parameter Store
    - Azure Key Vault
    - Google Cloud Secret Manager
    - HashiCorp Vault
    - File-based storage
    """
    
    async def save_template(self, template: TemplateDTO) -> None:
        """
        Save template to provider-specific storage.
        
        Args:
            template: Template to save
        """
        ...
    
    async def load_templates(self) -> List[TemplateDTO]:
        """
        Load all templates from provider-specific storage.
        
        Returns:
            List of TemplateDTO objects
        """
        ...
    
    async def delete_template(self, template_id: str) -> None:
        """
        Delete template from provider-specific storage.
        
        Args:
            template_id: Template identifier to delete
        """
        ...


class NoOpProviderTemplateStore:
    """
    No-operation provider template store.
    
    This implementation does nothing and is used as a default
    when no provider-specific storage is configured.
    """
    
    async def save_template(self, template: TemplateDTO) -> None:
        """No-op save operation."""
        pass
    
    async def load_templates(self) -> List[TemplateDTO]:
        """No-op load operation."""
        return []
    
    async def delete_template(self, template_id: str) -> None:
        """No-op delete operation."""
        pass


class ProviderTemplateStoreRegistry:
    """
    Registry for provider-specific template stores.
    
    This registry allows providers to register their template storage
    implementations and enables the configuration store to use them.
    
    Follows the Registry pattern for provider extensibility.
    """
    
    def __init__(self):
        self._stores: Dict[str, ProviderTemplateStore] = {}
        self._factories: Dict[str, callable] = {}
    
    def register_store(self, provider_type: str, store: ProviderTemplateStore) -> None:
        """
        Register a provider-specific template store instance.
        
        Args:
            provider_type: Provider type identifier (e.g., 'aws', 'azure')
            store: Template store instance
        """
        self._stores[provider_type] = store
    
    def register_factory(self, provider_type: str, factory: callable) -> None:
        """
        Register a factory function for creating provider-specific stores.
        
        Args:
            provider_type: Provider type identifier
            factory: Factory function that returns a ProviderTemplateStore
        """
        self._factories[provider_type] = factory
    
    def get_store(self, provider_type: str) -> Optional[ProviderTemplateStore]:
        """
        Get provider-specific template store.
        
        Args:
            provider_type: Provider type identifier
            
        Returns:
            ProviderTemplateStore instance or None if not found
        """
        # First check for registered instances
        if provider_type in self._stores:
            return self._stores[provider_type]
        
        # Then check for factories
        if provider_type in self._factories:
            factory = self._factories[provider_type]
            store = factory()
            self._stores[provider_type] = store  # Cache the instance
            return store
        
        return None
    
    def get_all_stores(self) -> Dict[str, ProviderTemplateStore]:
        """
        Get all registered provider stores.
        
        Returns:
            Dictionary mapping provider types to store instances
        """
        # Ensure all factories are instantiated
        for provider_type, factory in self._factories.items():
            if provider_type not in self._stores:
                self._stores[provider_type] = factory()
        
        return self._stores.copy()
    
    def list_providers(self) -> List[str]:
        """
        List all registered provider types.
        
        Returns:
            List of provider type identifiers
        """
        all_providers = set(self._stores.keys()) | set(self._factories.keys())
        return list(all_providers)
    
    def unregister_store(self, provider_type: str) -> None:
        """
        Unregister a provider-specific template store.
        
        Args:
            provider_type: Provider type identifier
        """
        self._stores.pop(provider_type, None)
        self._factories.pop(provider_type, None)


# Global registry instance
_provider_store_registry = ProviderTemplateStoreRegistry()


def get_provider_store_registry() -> ProviderTemplateStoreRegistry:
    """
    Get the global provider template store registry.
    
    Returns:
        Global ProviderTemplateStoreRegistry instance
    """
    return _provider_store_registry


def register_provider_template_store(provider_type: str, store: ProviderTemplateStore) -> None:
    """
    Convenience function to register a provider template store.
    
    Args:
        provider_type: Provider type identifier
        store: Template store instance
    """
    _provider_store_registry.register_store(provider_type, store)


def register_provider_template_store_factory(provider_type: str, factory: callable) -> None:
    """
    Convenience function to register a provider template store factory.
    
    Args:
        provider_type: Provider type identifier
        factory: Factory function
    """
    _provider_store_registry.register_factory(provider_type, factory)


class CompositeProviderTemplateStore:
    """
    Composite store that delegates to multiple provider-specific stores.
    
    This store allows templates to be saved to and loaded from multiple
    provider-specific storage systems simultaneously.
    
    Follows the Composite pattern for multi-provider support.
    """
    
    def __init__(self, stores: Dict[str, ProviderTemplateStore]):
        """
        Initialize composite store with provider stores.
        
        Args:
            stores: Dictionary mapping provider types to store instances
        """
        self.stores = stores
    
    async def save_template(self, template: TemplateDTO) -> None:
        """
        Save template to all provider stores.
        
        Args:
            template: Template to save
        """
        errors = []
        
        for provider_type, store in self.stores.items():
            try:
                await store.save_template(template)
            except Exception as e:
                errors.append(f"{provider_type}: {e}")
        
        if errors:
            raise Exception(f"Failed to save template to some providers: {'; '.join(errors)}")
    
    async def load_templates(self) -> List[TemplateDTO]:
        """
        Load templates from all provider stores and merge them.
        
        Returns:
            Merged list of TemplateDTO objects (duplicates removed by template_id)
        """
        all_templates = []
        template_ids_seen = set()
        
        for provider_type, store in self.stores.items():
            try:
                provider_templates = await store.load_templates()
                for template in provider_templates:
                    if template.template_id not in template_ids_seen:
                        all_templates.append(template)
                        template_ids_seen.add(template.template_id)
            except Exception as e:
                # Log error but continue with other providers
                continue
        
        return all_templates
    
    async def delete_template(self, template_id: str) -> None:
        """
        Delete template from all provider stores.
        
        Args:
            template_id: Template identifier to delete
        """
        errors = []
        
        for provider_type, store in self.stores.items():
            try:
                await store.delete_template(template_id)
            except Exception as e:
                errors.append(f"{provider_type}: {e}")
        
        if errors:
            raise Exception(f"Failed to delete template from some providers: {'; '.join(errors)}")


def create_composite_provider_store(
    provider_types: List[str],
    registry: Optional[ProviderTemplateStoreRegistry] = None
) -> CompositeProviderTemplateStore:
    """
    Create a composite provider store from registry.
    
    Args:
        provider_types: List of provider types to include
        registry: Optional registry (uses global if not provided)
        
    Returns:
        CompositeProviderTemplateStore instance
    """
    if registry is None:
        registry = get_provider_store_registry()
    
    stores = {}
    for provider_type in provider_types:
        store = registry.get_store(provider_type)
        if store:
            stores[provider_type] = store
    
    return CompositeProviderTemplateStore(stores)
