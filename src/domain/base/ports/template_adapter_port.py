"""Template Adapter Port - Provider-specific template operations interface."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.domain.template.aggregate import Template


class TemplateAdapterPort(ABC):
    """Port for provider-specific template operations.
    
    This port defines the interface for provider-specific template operations
    such as validation, field resolution, and provider-specific processing.
    
    Implementations should provide:
    - Template validation specific to the provider
    - Field resolution (e.g., AMI ID resolution for AWS)
    - Provider-specific template processing
    - Template field extension and enhancement
    """
    
    @abstractmethod
    def validate_template(self, template: Template) -> List[str]:
        """
        Validate template for provider-specific requirements.
        
        Args:
            template: Template domain entity to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        pass
    
    @abstractmethod
    def extend_template_fields(self, template: Template) -> Template:
        """
        Extend template with provider-specific fields and processing.
        
        Args:
            template: Template domain entity to extend
            
        Returns:
            Enhanced template with provider-specific fields
        """
        pass
    
    @abstractmethod
    def resolve_template_references(self, template: Template) -> Template:
        """
        Resolve provider-specific references in template (e.g., AMI aliases, SSM parameters).
        
        Args:
            template: Template with potential references to resolve
            
        Returns:
            Template with resolved references
        """
        pass
    
    @abstractmethod
    def get_supported_fields(self) -> List[str]:
        """
        Get list of fields supported by this provider adapter.
        
        Returns:
            List of supported field names
        """
        pass
    
    @abstractmethod
    def validate_field_values(self, template: Template) -> Dict[str, str]:
        """
        Validate provider-specific field values.
        
        Args:
            template: Template to validate
            
        Returns:
            Dictionary mapping field names to validation error messages
        """
        pass
    
    @abstractmethod
    def get_provider_api(self) -> str:
        """
        Get the provider API identifier for this adapter.
        
        Returns:
            Provider API identifier (e.g., 'EC2Fleet', 'SpotFleet')
        """
        pass
