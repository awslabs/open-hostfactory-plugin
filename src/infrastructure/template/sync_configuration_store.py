"""Synchronous Template Configuration Store Wrapper.

This module provides a synchronous wrapper around the async TemplateConfigurationStore
to enable clean integration with CQRS handlers and other synchronous components
while maintaining the async capabilities for provider stores.

Follows the Adapter pattern to bridge async/sync boundaries cleanly.
"""
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from .configuration_store import TemplateConfigurationStore
from .dtos import TemplateDTO
from src.domain.base.ports import LoggingPort
from src.domain.base.dependency_injection import injectable


@injectable
class SyncTemplateConfigurationStore:
    """
    Synchronous wrapper for TemplateConfigurationStore.
    
    This wrapper provides synchronous methods that internally handle
    the async operations of the underlying configuration store.
    
    It handles event loop management and provides fallback to cache
    when async operations are not possible.
    """
    
    def __init__(self, async_store: TemplateConfigurationStore, logger: LoggingPort):
        """
        Initialize synchronous wrapper.
        
        Args:
            async_store: The async TemplateConfigurationStore to wrap
            logger: Logger for dependency injection
        """
        self.async_store = async_store
        self.logger = logger
    
    def get_templates(self) -> List[TemplateDTO]:
        """
        Get all templates synchronously.
        
        Returns:
            List of TemplateDTO objects
        """
        try:
            return self._run_async(self.async_store.get_templates())
        except Exception as e:
            self.logger.warning(f"Failed to get templates async, falling back to cache: {e}")
            return self.async_store.cache.get_all() or []
    
    def get_template_by_id(self, template_id: str) -> Optional[TemplateDTO]:
        """
        Get a specific template by ID synchronously.
        
        Args:
            template_id: Template identifier
            
        Returns:
            TemplateDTO if found, None otherwise
        """
        try:
            return self._run_async(self.async_store.get_template_by_id(template_id))
        except Exception as e:
            self.logger.warning(f"Failed to get template {template_id} async, falling back to cache: {e}")
            cached_templates = self.async_store.cache.get_all() or []
            return next((t for t in cached_templates if t.template_id == template_id), None)
    
    def get_templates_by_provider(self, provider_api: str) -> List[TemplateDTO]:
        """
        Get templates filtered by provider API synchronously.
        
        Args:
            provider_api: Provider API identifier
            
        Returns:
            List of templates for the specified provider
        """
        try:
            return self._run_async(self.async_store.get_templates_by_provider(provider_api))
        except Exception as e:
            self.logger.warning(f"Failed to get templates by provider {provider_api} async, falling back to cache: {e}")
            cached_templates = self.async_store.cache.get_all() or []
            return [t for t in cached_templates if getattr(t, 'provider_api', None) == provider_api]
    
    def save_template(self, template: TemplateDTO) -> None:
        """
        Save template synchronously.
        
        Args:
            template: Template to save
        """
        try:
            self._run_async(self.async_store.save_template(template))
        except Exception as e:
            self.logger.error(f"Failed to save template {template.template_id}: {e}")
            raise
    
    def delete_template(self, template_id: str) -> None:
        """
        Delete template synchronously.
        
        Args:
            template_id: Template identifier to delete
        """
        try:
            self._run_async(self.async_store.delete_template(template_id))
        except Exception as e:
            self.logger.error(f"Failed to delete template {template_id}: {e}")
            raise
    
    def reload_templates(self) -> List[TemplateDTO]:
        """
        Reload templates synchronously.
        
        Returns:
            List of reloaded templates
        """
        try:
            return self._run_async(self.async_store.reload_templates())
        except Exception as e:
            self.logger.error(f"Failed to reload templates: {e}")
            return []
    
    def template_exists(self, template_id: str) -> bool:
        """
        Check if template exists synchronously.
        
        Args:
            template_id: Template identifier
            
        Returns:
            True if template exists, False otherwise
        """
        # This method is already synchronous in the async store
        return self.async_store.template_exists(template_id)
    
    def get_template_count(self) -> int:
        """
        Get total number of templates synchronously.
        
        Returns:
            Number of templates
        """
        # This method is already synchronous in the async store
        return self.async_store.get_template_count()
    
    def get_configuration_info(self) -> Dict[str, Any]:
        """
        Get configuration information synchronously.
        
        Returns:
            Dictionary with configuration information
        """
        # This method is already synchronous in the async store
        return self.async_store.get_configuration_info()
    
    def _run_async(self, coro):
        """
        Run async coroutine synchronously with proper event loop handling.
        
        Args:
            coro: Coroutine to run
            
        Returns:
            Result of the coroutine
        """
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            
            if loop.is_running():
                # If loop is running, we can't use asyncio.run()
                # This typically happens in async contexts or some frameworks
                self.logger.debug("Event loop is running, cannot use asyncio.run()")
                raise RuntimeError("Event loop is already running")
            else:
                # Loop exists but not running, we can use it
                return loop.run_until_complete(coro)
                
        except RuntimeError as e:
            if "no current event loop" in str(e).lower():
                # No event loop exists, create one
                return asyncio.run(coro)
            else:
                # Event loop is running or other runtime error
                self.logger.debug(f"Cannot run async operation: {e}")
                raise
    
    @property
    def cache(self):
        """Access to the underlying cache for direct operations."""
        return self.async_store.cache
    
    @property
    def file_store(self):
        """Access to the underlying file store."""
        return self.async_store.file_store
    
    @property
    def provider_stores(self):
        """Access to the underlying provider stores."""
        return self.async_store.provider_stores


def create_sync_template_configuration_store(
    async_store: TemplateConfigurationStore,
    logger: LoggingPort
) -> SyncTemplateConfigurationStore:
    """
    Factory function to create SyncTemplateConfigurationStore.
    
    Args:
        async_store: The async TemplateConfigurationStore to wrap
        logger: Logger for dependency injection
        
    Returns:
        Configured SyncTemplateConfigurationStore instance
    """
    return SyncTemplateConfigurationStore(async_store, logger)
