"""Template Extension System - Provider-specific template extensions.

This module implements the Template Extension pattern, allowing providers
to extend template functionality with provider-specific fields, validation,
and processing logic while maintaining clean separation of concerns.

Follows the Strategy pattern and Extension pattern for provider extensibility.
"""
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable
from abc import ABC, abstractmethod

from .dtos import TemplateDTO
from src.domain.template.aggregate import Template
from src.domain.base.ports import LoggingPort
from src.domain.base.dependency_injection import injectable


@runtime_checkable
class TemplateExtension(Protocol):
    """
    Protocol for provider-specific template extensions.
    
    This protocol defines the interface that all provider-specific
    template extensions must implement.
    """
    
    def get_provider_type(self) -> str:
        """Get the provider type this extension supports."""
        ...
    
    def extend_template_fields(self, template: Template) -> Template:
        """
        Extend template with provider-specific fields and defaults.
        
        Args:
            template: Base template to extend
            
        Returns:
            Extended template with provider-specific fields
        """
        ...
    
    def validate_template(self, template: Template) -> List[str]:
        """
        Validate provider-specific template configuration.
        
        Args:
            template: Template to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        ...
    
    def process_template_dto(self, template_dto: TemplateDTO) -> TemplateDTO:
        """
        Process template DTO with provider-specific logic.
        
        Args:
            template_dto: Template DTO to process
            
        Returns:
            Processed template DTO
        """
        ...
    
    def get_supported_fields(self) -> List[str]:
        """
        Get list of provider-specific fields supported by this extension.
        
        Returns:
            List of field names
        """
        ...


class BaseTemplateExtension(ABC):
    """
    Base implementation of TemplateExtension with common functionality.
    
    Provides default implementations and helper methods for concrete extensions.
    """
    
    def __init__(self, provider_type: str, logger: Optional[LoggingPort] = None):
        """
        Initialize base template extension.
        
        Args:
            provider_type: Provider type identifier
            logger: Optional logger
        """
        self.provider_type = provider_type
        self.logger = logger
    
    def get_provider_type(self) -> str:
        """Get the provider type this extension supports."""
        return self.provider_type
    
    @abstractmethod
    def extend_template_fields(self, template: Template) -> Template:
        """Extend template with provider-specific fields."""
        pass
    
    @abstractmethod
    def validate_template(self, template: Template) -> List[str]:
        """Validate provider-specific template configuration."""
        pass
    
    def process_template_dto(self, template_dto: TemplateDTO) -> TemplateDTO:
        """
        Default DTO processing - can be overridden by concrete extensions.
        
        Args:
            template_dto: Template DTO to process
            
        Returns:
            Processed template DTO (default: no changes)
        """
        return template_dto
    
    @abstractmethod
    def get_supported_fields(self) -> List[str]:
        """Get list of provider-specific fields."""
        pass
    
    def _validate_required_field(self, template: Template, field_name: str, field_path: str = None) -> Optional[str]:
        """
        Helper method to validate required fields.
        
        Args:
            template: Template to validate
            field_name: Name of the required field
            field_path: Optional path for nested fields (e.g., 'metadata.aws.instance_type')
            
        Returns:
            Error message if field is missing, None otherwise
        """
        if field_path:
            # Handle nested field validation
            parts = field_path.split('.')
            current = template
            for part in parts:
                if hasattr(current, part):
                    current = getattr(current, part)
                    if current is None:
                        return f"Required field '{field_name}' is missing at path '{field_path}'"
                else:
                    return f"Required field '{field_name}' is missing at path '{field_path}'"
        else:
            # Handle direct field validation
            if not hasattr(template, field_name) or getattr(template, field_name) is None:
                return f"Required field '{field_name}' is missing"
        
        return None
    
    def _validate_field_values(self, template: Template, field_name: str, valid_values: List[Any]) -> Optional[str]:
        """
        Helper method to validate field values against allowed values.
        
        Args:
            template: Template to validate
            field_name: Name of the field to validate
            valid_values: List of valid values
            
        Returns:
            Error message if value is invalid, None otherwise
        """
        if hasattr(template, field_name):
            field_value = getattr(template, field_name)
            if field_value is not None and field_value not in valid_values:
                return f"Field '{field_name}' has invalid value '{field_value}'. Valid values: {valid_values}"
        
        return None


class NoOpTemplateExtension(BaseTemplateExtension):
    """
    No-operation template extension for providers without specific extensions.
    
    This extension does nothing and is used as a default when no provider-specific
    extension is available.
    """
    
    def __init__(self, provider_type: str = "generic"):
        super().__init__(provider_type)
    
    def extend_template_fields(self, template: Template) -> Template:
        """No-op field extension."""
        return template
    
    def validate_template(self, template: Template) -> List[str]:
        """No-op validation."""
        return []
    
    def get_supported_fields(self) -> List[str]:
        """No additional fields supported."""
        return []


class TemplateExtensionRegistry:
    """
    Registry for template extensions.
    
    This registry allows providers to register their template extensions
    and enables the template system to use them.
    
    Follows the Registry pattern for extension management.
    """
    
    def __init__(self):
        self._extensions: Dict[str, TemplateExtension] = {}
        self._factories: Dict[str, callable] = {}
    
    def register_extension(self, provider_type: str, extension: TemplateExtension) -> None:
        """
        Register a template extension instance.
        
        Args:
            provider_type: Provider type identifier
            extension: Template extension instance
        """
        self._extensions[provider_type] = extension
    
    def register_factory(self, provider_type: str, factory: callable) -> None:
        """
        Register a factory function for creating template extensions.
        
        Args:
            provider_type: Provider type identifier
            factory: Factory function that returns a TemplateExtension
        """
        self._factories[provider_type] = factory
    
    def get_extension(self, provider_type: str) -> TemplateExtension:
        """
        Get template extension for provider type.
        
        Args:
            provider_type: Provider type identifier
            
        Returns:
            TemplateExtension instance (NoOpTemplateExtension if not found)
        """
        # First check for registered instances
        if provider_type in self._extensions:
            return self._extensions[provider_type]
        
        # Then check for factories
        if provider_type in self._factories:
            factory = self._factories[provider_type]
            extension = factory()
            self._extensions[provider_type] = extension  # Cache the instance
            return extension
        
        # Return no-op extension as default
        return NoOpTemplateExtension(provider_type)
    
    def get_all_extensions(self) -> Dict[str, TemplateExtension]:
        """
        Get all registered template extensions.
        
        Returns:
            Dictionary mapping provider types to extension instances
        """
        # Ensure all factories are instantiated
        for provider_type, factory in self._factories.items():
            if provider_type not in self._extensions:
                self._extensions[provider_type] = factory()
        
        return self._extensions.copy()
    
    def list_providers(self) -> List[str]:
        """
        List all registered provider types.
        
        Returns:
            List of provider type identifiers
        """
        all_providers = set(self._extensions.keys()) | set(self._factories.keys())
        return list(all_providers)
    
    def unregister_extension(self, provider_type: str) -> None:
        """
        Unregister a template extension.
        
        Args:
            provider_type: Provider type identifier
        """
        self._extensions.pop(provider_type, None)
        self._factories.pop(provider_type, None)


# Global registry instance
_template_extension_registry = TemplateExtensionRegistry()


def get_template_extension_registry() -> TemplateExtensionRegistry:
    """
    Get the global template extension registry.
    
    Returns:
        Global TemplateExtensionRegistry instance
    """
    return _template_extension_registry


def register_template_extension(provider_type: str, extension: TemplateExtension) -> None:
    """
    Convenience function to register a template extension.
    
    Args:
        provider_type: Provider type identifier
        extension: Template extension instance
    """
    _template_extension_registry.register_extension(provider_type, extension)


def register_template_extension_factory(provider_type: str, factory: callable) -> None:
    """
    Convenience function to register a template extension factory.
    
    Args:
        provider_type: Provider type identifier
        factory: Factory function
    """
    _template_extension_registry.register_factory(provider_type, factory)


def get_template_extension(provider_type: str) -> TemplateExtension:
    """
    Convenience function to get a template extension.
    
    Args:
        provider_type: Provider type identifier
        
    Returns:
        TemplateExtension instance
    """
    return _template_extension_registry.get_extension(provider_type)


class CompositeTemplateExtension:
    """
    Composite extension that applies multiple extensions in sequence.
    
    This extension allows templates to be processed by multiple extensions,
    useful for complex scenarios or multi-provider templates.
    
    Follows the Composite pattern for multi-extension support.
    """
    
    def __init__(self, extensions: List[TemplateExtension]):
        """
        Initialize composite extension with list of extensions.
        
        Args:
            extensions: List of template extensions to apply
        """
        self.extensions = extensions
    
    def get_provider_type(self) -> str:
        """Get composite provider type."""
        provider_types = [ext.get_provider_type() for ext in self.extensions]
        return f"composite({','.join(provider_types)})"
    
    def extend_template_fields(self, template: Template) -> Template:
        """
        Apply all extensions to template fields.
        
        Args:
            template: Template to extend
            
        Returns:
            Template extended by all extensions
        """
        extended_template = template
        for extension in self.extensions:
            extended_template = extension.extend_template_fields(extended_template)
        return extended_template
    
    def validate_template(self, template: Template) -> List[str]:
        """
        Validate template using all extensions.
        
        Args:
            template: Template to validate
            
        Returns:
            Combined list of validation errors from all extensions
        """
        all_errors = []
        for extension in self.extensions:
            errors = extension.validate_template(template)
            all_errors.extend(errors)
        return all_errors
    
    def process_template_dto(self, template_dto: TemplateDTO) -> TemplateDTO:
        """
        Process template DTO using all extensions.
        
        Args:
            template_dto: Template DTO to process
            
        Returns:
            Template DTO processed by all extensions
        """
        processed_dto = template_dto
        for extension in self.extensions:
            processed_dto = extension.process_template_dto(processed_dto)
        return processed_dto
    
    def get_supported_fields(self) -> List[str]:
        """
        Get combined list of supported fields from all extensions.
        
        Returns:
            List of all supported field names
        """
        all_fields = []
        for extension in self.extensions:
            fields = extension.get_supported_fields()
            all_fields.extend(fields)
        return list(set(all_fields))  # Remove duplicates
