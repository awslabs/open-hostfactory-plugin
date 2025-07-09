"""Template Format Adapter implementing TemplateFormatPort.

This adapter implements the TemplateFormatPort interface using the existing
infrastructure format converter, maintaining Clean Architecture by providing
the bridge between domain abstractions and infrastructure implementations.

Architecture:
- Implements domain TemplateFormatPort interface
- Uses infrastructure TemplateFormatConverter for actual conversion
- Follows Adapter pattern to bridge domain and infrastructure
- Maintains separation of concerns
"""
from typing import Dict, Any, List
from src.domain.base.ports.template_format_port import TemplateFormatPort
from src.infrastructure.template.format_converter import TemplateFormatConverter


class TemplateFormatAdapter(TemplateFormatPort):
    """Adapter implementing TemplateFormatPort using infrastructure format converter.
    
    This adapter wraps the infrastructure TemplateFormatConverter to provide
    a clean domain interface while preserving all existing functionality.
    """
    
    def __init__(self, converter: TemplateFormatConverter):
        """Initialize with format converter.
        
        Args:
            converter: Infrastructure format converter instance
        """
        self._converter = converter
    
    def convert_to_legacy(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert template data to legacy camelCase format."""
        return self._converter.convert_new_to_legacy(template_data)
    
    def convert_from_legacy(self, legacy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert legacy camelCase data to new snake_case format."""
        return self._converter.convert_legacy_to_new(legacy_data)
    
    def create_minimal_template(self, template_data: Dict[str, Any], use_camel_case: bool = False) -> Dict[str, Any]:
        """Create HF-compatible minimal template with essential fields only."""
        # Essential fields for HF compatibility
        minimal = {
            "template_id": template_data.get("template_id", ""),
            "max_instances": template_data.get("max_instances", 1),
            "attributes": self.create_hf_attributes(template_data)
        }
        
        # Convert to camelCase if requested
        if use_camel_case:
            minimal = self.convert_to_legacy(minimal)
        
        return minimal
    
    def create_hf_attributes(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create HF-compatible attributes object with CPU/RAM specs."""
        instance_type = template_data.get('instance_type', 't2.micro')
        
        # CPU/RAM mapping for common instance types
        cpu_ram_mapping = {
            "t2.micro": {"ncpus": "1", "nram": "1024"},
            "t2.small": {"ncpus": "1", "nram": "2048"},
            "t2.medium": {"ncpus": "2", "nram": "4096"},
            "t3.micro": {"ncpus": "2", "nram": "1024"},
            "t3.small": {"ncpus": "2", "nram": "2048"},
            "t3.medium": {"ncpus": "2", "nram": "4096"},
            "m5.large": {"ncpus": "2", "nram": "8192"},
            "m5.xlarge": {"ncpus": "4", "nram": "16384"},
        }
        
        specs = cpu_ram_mapping.get(instance_type, {"ncpus": "1", "nram": "1024"})
        
        return {
            "type": ["String", "X86_64"],
            "ncpus": ["Numeric", specs["ncpus"]],
            "nram": ["Numeric", specs["nram"]]
        }
    
    def convert_batch_to_legacy(self, template_data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert multiple template data objects to legacy format."""
        return [self.convert_to_legacy(data) for data in template_data_list]
    
    def convert_batch_from_legacy(self, legacy_data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert multiple legacy format data to new format."""
        return [self.convert_from_legacy(data) for data in legacy_data_list]
