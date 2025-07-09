"""Template format conversion service - Clean Architecture compliant.

This service handles technical conversions between different template formats,
now properly following Clean Architecture by depending on domain ports
instead of infrastructure implementations.

Architecture:
- Application layer service (this file)
- Depends on domain TemplateFormatPort interface
- Infrastructure provides TemplateFormatAdapter implementation
- Follows Dependency Inversion Principle
"""
from typing import Dict, Any, List
from src.domain.template.aggregate import Template
from src.domain.base.ports.template_format_port import TemplateFormatPort
from src.domain.base.exceptions import ApplicationError


class TemplateFormatService:
    """Application service for template format conversions.
    
    This service handles technical conversions between different template formats,
    keeping the domain layer pure of technical conversion concerns while following
    Clean Architecture by depending on domain ports.
    """
    
    def __init__(self, format_port: TemplateFormatPort):
        """Initialize with format port.
        
        Args:
            format_port: Domain port for template format operations
            
        Note:
            Now depends on domain port instead of infrastructure converter,
            following Dependency Inversion Principle.
        """
        self._format_port = format_port
    
    
    def convert_to_legacy(self, template: Template) -> Dict[str, Any]:
        """Convert template to legacy format.
        
        Args:
            template: Template domain object
            
        Returns:
            Dictionary in legacy format
            
        Raises:
            ApplicationError: If conversion fails
        """
        template_data = template.model_dump()
        return self._format_port.convert_to_legacy(template_data)
    
    
    def convert_from_legacy(self, legacy_data: Dict[str, Any]) -> Template:
        """Convert from legacy format to Template domain object.
        
        Args:
            legacy_data: Template data in legacy format
            
        Returns:
            Template domain object
            
        Raises:
            ApplicationError: If conversion fails
        """
        new_format_data = self._format_port.convert_from_legacy(legacy_data)
        return Template.model_validate(new_format_data)
    
    
    def convert_batch_to_legacy(self, templates: list[Template]) -> list[Dict[str, Any]]:
        """Convert multiple templates to legacy format.
        
        Args:
            templates: List of Template domain objects
            
        Returns:
            List of dictionaries in legacy format
        """
        return [self.convert_to_legacy(template) for template in templates]
    
    
    def convert_batch_from_legacy(self, legacy_data_list: list[Dict[str, Any]]) -> list[Template]:
        """Convert multiple legacy format data to Template domain objects.
        
        Args:
            legacy_data_list: List of template data in legacy format
            
        Returns:
            List of Template domain objects
        """
        return [self.convert_from_legacy(data) for data in legacy_data_list]
    
    def convert_templates(self, templates: list[Template], include_full_config: bool = False, use_camel_case: bool = False) -> Dict[str, Any]:
        """
        Unified template conversion method.
        
        Args:
            templates: List of Template domain objects
            include_full_config: If True, include all fields. If False, include only essential fields (HF minimal)
            use_camel_case: If True, use camelCase field names. If False, use snake_case
            
        Returns:
            Dictionary with converted templates
        """
        try:
            converted_templates = []
            
            for template in templates:
                template_data = template.model_dump()
                
                if include_full_config:
                    # Full configuration - all fields
                    if use_camel_case:
                        converted = self._format_port.convert_to_legacy(template_data)
                    else:
                        converted = template_data  # Already in snake_case
                else:
                    # Minimal configuration - HF essential fields only
                    converted = self._create_minimal_template(template_data, use_camel_case)
                
                converted_templates.append(converted)
            
            return {"templates": converted_templates}
            
        except Exception as e:
            raise ApplicationError(f"Failed to convert templates: {str(e)}")
    
    def _create_minimal_template(self, template_data: Dict[str, Any], use_camel_case: bool) -> Dict[str, Any]:
        """Create minimal template with essential fields only (HF compatible)."""
        return self._format_port.create_minimal_template(template_data, use_camel_case)
    
    def _create_hf_attributes(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create HF-compatible attributes object."""
        return self._format_port.create_hf_attributes(template_data)
