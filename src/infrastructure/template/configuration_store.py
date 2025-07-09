"""Template Configuration Store - Unified template configuration management.

This module provides a unified approach to template configuration management,
implementing a clean configuration-centric approach for template operations.

Follows DDD principles by treating templates as configuration entities
rather than transactional business entities.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from .dtos import TemplateDTO
from .mappers import TemplateMapper
from .loader import TemplateLoader
from .template_cache_service import TemplateCacheService
from .provider_stores import ProviderTemplateStore, get_provider_store_registry
from .extensions import get_template_extension_registry, get_template_extension
from src.domain.template.aggregate import Template
from src.domain.base.ports import LoggingPort
from src.domain.base.dependency_injection import injectable


@injectable
class TemplateFileStore:
    """File-based template storage using TemplateLoader."""
    
    def __init__(self, loader: TemplateLoader, logger: LoggingPort):
        self.loader = loader
        self.logger = logger
    
    async def load_templates(self) -> List[TemplateDTO]:
        """Load templates from file sources."""
        try:
            return self.loader.load_all()
        except Exception as e:
            self.logger.error(f"Failed to load templates from files: {e}")
            return []
    
    async def save_template(self, template: TemplateDTO) -> None:
        """Save template to file (not implemented - files are managed externally)."""
        # This method is here for interface consistency but doesn't implement file writing
        self.logger.warning(f"File-based template saving not implemented for {template.template_id}")
        raise NotImplementedError("File-based template saving is managed externally")
    
    async def delete_template(self, template_id: str) -> None:
        """Delete template from file (not implemented - files are managed externally)."""
        self.logger.warning(f"File-based template deletion not implemented for {template_id}")
        raise NotImplementedError("File-based template deletion is managed externally")


class TemplateConfigurationStore:
    """
    Unified template configuration store.
    
    This class replaces TemplateService, TemplateConfigurationManager, and provides
    a single point of access for all template configuration operations.
    
    Responsibilities:
    - Load templates from file sources
    - Manage provider-specific template storage
    - Provide caching for performance
    - Validate template configurations
    - Handle template lifecycle operations
    
    Follows SRP by focusing solely on template configuration management.
    """
    
    def __init__(self, 
                 file_store: TemplateFileStore,
                 cache: TemplateCacheService,
                 provider_stores: Optional[Dict[str, ProviderTemplateStore]] = None,
                 use_provider_registry: bool = True,
                 logger: Optional[LoggingPort] = None):
        """
        Initialize template configuration store.
        
        Args:
            file_store: File-based template storage
            cache: Template caching service
            provider_stores: Optional provider-specific stores (e.g., {'aws': AWSSSMStore})
            use_provider_registry: Whether to use the global provider registry
            logger: Logger for operations
        """
        self.file_store = file_store
        self.cache = cache
        self.logger = logger
        self._last_load_time: Optional[datetime] = None
        self._templates_cache: List[TemplateDTO] = []
        
        # Initialize provider stores
        self.provider_stores = provider_stores or {}
        
        # Optionally load from provider registry
        if use_provider_registry:
            registry = get_provider_store_registry()
            registry_stores = registry.get_all_stores()
            # Merge registry stores with explicitly provided stores
            for provider_type, store in registry_stores.items():
                if provider_type not in self.provider_stores:
                    self.provider_stores[provider_type] = store
    
    async def get_templates(self) -> List[TemplateDTO]:
        """
        Get all templates with caching support.
        
        Returns:
            List of TemplateDTO objects
        """
        try:
            # Check cache first
            cached_templates = self.cache.get_all()
            if cached_templates:
                self.logger.debug(f"Retrieved {len(cached_templates)} templates from cache")
                return cached_templates
            
            # Load from file store
            templates = await self.file_store.load_templates()
            
            # Cache the results
            for template in templates:
                self.cache.put(template.template_id, template)
            
            self._last_load_time = datetime.now()
            self.logger.info(f"Loaded {len(templates)} templates from configuration")
            
            return templates
            
        except Exception as e:
            self.logger.error(f"Failed to get templates: {e}")
            return []
    
    async def get_template_by_id(self, template_id: str) -> Optional[TemplateDTO]:
        """
        Get a specific template by ID.
        
        Args:
            template_id: Template identifier
            
        Returns:
            TemplateDTO if found, None otherwise
        """
        try:
            # Check cache first
            cached_template = self.cache.get(template_id)
            if cached_template:
                self.logger.debug(f"Retrieved template {template_id} from cache")
                return cached_template
            
            # Load all templates and find the one we need
            templates = await self.get_templates()
            for template in templates:
                if template.template_id == template_id:
                    return template
            
            self.logger.warning(f"Template {template_id} not found")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get template {template_id}: {e}")
            return None
    
    async def get_templates_by_provider(self, provider_api: str) -> List[TemplateDTO]:
        """
        Get templates filtered by provider API.
        
        Args:
            provider_api: Provider API identifier (e.g., "EC2Fleet", "SpotFleet")
            
        Returns:
            List of templates for the specified provider
        """
        templates = await self.get_templates()
        filtered_templates = [
            t for t in templates 
            if getattr(t, 'provider_api', None) == provider_api
        ]
        
        self.logger.debug(f"Found {len(filtered_templates)} templates for provider {provider_api}")
        return filtered_templates
    
    async def save_template(self, template: TemplateDTO) -> None:
        """
        Save template to configuration store.
        
        Args:
            template: Template to save
        """
        try:
            # Apply template extensions before saving
            processed_template = self._apply_template_extensions(template)
            
            # Save to provider-specific stores if configured
            for provider_type, provider_store in self.provider_stores.items():
                try:
                    await provider_store.save_template(processed_template)
                    self.logger.debug(f"Saved template {processed_template.template_id} to {provider_type} store")
                except Exception as e:
                    self.logger.warning(f"Failed to save template to {provider_type} store: {e}")
            
            # Update cache
            self.cache.put(processed_template.template_id, processed_template)
            
            # Update timestamp
            processed_template.updated_at = datetime.now()
            
            self.logger.info(f"Saved template {processed_template.template_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to save template {template.template_id}: {e}")
            raise
    
    async def delete_template(self, template_id: str) -> None:
        """
        Delete template from configuration store.
        
        Args:
            template_id: Template identifier to delete
        """
        try:
            # Delete from provider-specific stores
            for provider_type, provider_store in self.provider_stores.items():
                try:
                    await provider_store.delete_template(template_id)
                    self.logger.debug(f"Deleted template {template_id} from {provider_type} store")
                except Exception as e:
                    self.logger.warning(f"Failed to delete template from {provider_type} store: {e}")
            
            # Remove from cache
            self.cache.evict(template_id)
            
            self.logger.info(f"Deleted template {template_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to delete template {template_id}: {e}")
            raise
    
    async def reload_templates(self) -> List[TemplateDTO]:
        """
        Reload templates from all sources.
        
        Returns:
            List of reloaded templates
        """
        try:
            # Clear cache
            self.cache.clear()
            
            # Reload from file store
            templates = await self.file_store.load_templates()
            
            # Update cache
            for template in templates:
                self.cache.put(template.template_id, template)
            
            self._last_load_time = datetime.now()
            self.logger.info(f"Reloaded {len(templates)} templates")
            
            return templates
            
        except Exception as e:
            self.logger.error(f"Failed to reload templates: {e}")
            return []
    
    def template_exists(self, template_id: str) -> bool:
        """
        Check if template exists.
        
        Args:
            template_id: Template identifier
            
        Returns:
            True if template exists, False otherwise
        """
        try:
            # Check cache first
            if self.cache.get(template_id):
                return True
            
            # This is a synchronous method, so we can't use async get_template_by_id
            # Instead, check if we have cached templates
            cached_templates = self.cache.get_all()
            if cached_templates:
                return any(t.template_id == template_id for t in cached_templates)
            
            # If no cache, we need to indicate that async loading is required
            self.logger.debug(f"Template existence check for {template_id} requires async loading")
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to check template existence for {template_id}: {e}")
            return False
    
    def get_template_count(self) -> int:
        """
        Get total number of templates.
        
        Returns:
            Number of templates
        """
        try:
            cached_templates = self.cache.get_all()
            if cached_templates:
                return len(cached_templates)
            
            # If no cache, return 0 and log that async loading is needed
            self.logger.debug("Template count requires async loading")
            return 0
            
        except Exception as e:
            self.logger.error(f"Failed to get template count: {e}")
            return 0
    
    def get_configuration_info(self) -> Dict[str, Any]:
        """
        Get configuration information and statistics.
        
        Returns:
            Dictionary with configuration information
        """
        try:
            cached_templates = self.cache.get_all()
            template_count = len(cached_templates) if cached_templates else 0
            
            info = {
                'template_count': template_count,
                'last_load_time': self._last_load_time.isoformat() if self._last_load_time else None,
                'cache_enabled': True,
                'provider_stores': list(self.provider_stores.keys()),
                'file_store_enabled': True
            }
            
            if cached_templates:
                # Add provider breakdown
                provider_counts = {}
                for template in cached_templates:
                    provider = getattr(template, 'provider_api', 'unknown')
                    provider_counts[provider] = provider_counts.get(provider, 0) + 1
                info['templates_by_provider'] = provider_counts
            
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get configuration info: {e}")
            return {'error': str(e)}


    def _apply_template_extensions(self, template_dto: TemplateDTO) -> TemplateDTO:
        """
        Apply provider-specific template extensions to template DTO.
        
        Args:
            template_dto: Template DTO to process
            
        Returns:
            Processed template DTO with extensions applied
        """
        try:
            # Determine provider type from template
            provider_type = self._get_provider_type(template_dto)
            
            if provider_type:
                # Get and apply template extension
                extension = get_template_extension(provider_type)
                processed_dto = extension.process_template_dto(template_dto)
                
                self.logger.debug(f"Applied {provider_type} extension to template {template_dto.template_id}")
                return processed_dto
            
            return template_dto
            
        except Exception as e:
            self.logger.warning(f"Failed to apply template extensions to {template_dto.template_id}: {e}")
            return template_dto
    
    def _get_provider_type(self, template_dto: TemplateDTO) -> Optional[str]:
        """
        Determine provider type from template DTO.
        
        Args:
            template_dto: Template DTO
            
        Returns:
            Provider type string or None
        """
        # Try to determine from provider_api field
        provider_api = template_dto.provider_api
        if provider_api:
            # Map provider APIs to provider types
            if provider_api in ['EC2Fleet', 'SpotFleet', 'RunInstances', 'AutoScalingGroup']:
                return 'aws'
            # Add other provider mappings as needed
        
        # Try to determine from configuration
        config = template_dto.configuration
        if config:
            if 'aws' in config or any(key.startswith('aws_') for key in config.keys()):
                return 'aws'
            # Add other provider detection logic as needed
        
        return None


def create_template_configuration_store(
    loader: TemplateLoader,
    cache: TemplateCacheService,
    provider_stores: Optional[Dict[str, ProviderTemplateStore]] = None,
    use_provider_registry: bool = True,
    logger: Optional[LoggingPort] = None
) -> TemplateConfigurationStore:
    """
    Factory function to create TemplateConfigurationStore.
    
    Args:
        loader: Template loader for file-based loading
        cache: Template cache service
        provider_stores: Optional provider-specific stores
        use_provider_registry: Whether to use the global provider registry
        logger: Optional logger
        
    Returns:
        Configured TemplateConfigurationStore instance
    """
    file_store = TemplateFileStore(loader)
    return TemplateConfigurationStore(
        file_store=file_store,
        cache=cache,
        provider_stores=provider_stores,
        use_provider_registry=use_provider_registry,
        logger=logger
    )
