"""Template infrastructure components."""

from .loader import TemplateLoader
from .template_cache_service import TemplateCacheService, NoOpTemplateCacheService, create_template_cache_service
from .configuration_store import TemplateConfigurationStore, TemplateFileStore, create_template_configuration_store
from .sync_configuration_store import SyncTemplateConfigurationStore, create_sync_template_configuration_store
from .provider_stores import (
    ProviderTemplateStore, 
    NoOpProviderTemplateStore,
    ProviderTemplateStoreRegistry,
    get_provider_store_registry,
    register_provider_template_store,
    register_provider_template_store_factory,
    CompositeProviderTemplateStore,
    create_composite_provider_store
)
from .extensions import (
    TemplateExtension,
    BaseTemplateExtension,
    NoOpTemplateExtension,
    TemplateExtensionRegistry,
    get_template_extension_registry,
    register_template_extension,
    register_template_extension_factory,
    get_template_extension,
    CompositeTemplateExtension
)
from .format_converter import TemplateFormatConverter

__all__ = [
    # Unified configuration store
    'TemplateConfigurationStore',
    'TemplateFileStore',
    'create_template_configuration_store',
    'SyncTemplateConfigurationStore',
    'create_sync_template_configuration_store',
    
    # Provider extensibility
    'ProviderTemplateStore',
    'NoOpProviderTemplateStore',
    'ProviderTemplateStoreRegistry',
    'get_provider_store_registry',
    'register_provider_template_store',
    'register_provider_template_store_factory',
    'CompositeProviderTemplateStore',
    'create_composite_provider_store',
    
    # Template extensions
    'TemplateExtension',
    'BaseTemplateExtension',
    'NoOpTemplateExtension',
    'TemplateExtensionRegistry',
    'get_template_extension_registry',
    'register_template_extension',
    'register_template_extension_factory',
    'get_template_extension',
    'CompositeTemplateExtension',
    
    # Core components
    'TemplateLoader',
    'TemplateCacheService',
    'NoOpTemplateCacheService', 
    'create_template_cache_service',
    'TemplateFormatConverter',
]
