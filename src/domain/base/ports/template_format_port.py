"""Template Format Port - Interface for template format conversions.

This port defines the interface for converting between different template formats,
maintaining Clean Architecture by keeping format conversion concerns in the domain layer
as an abstraction that infrastructure implements.

Architecture:
- Domain layer defines the interface (this port)
- Infrastructure layer provides implementation (adapter)
- Application layer depends on this port, not infrastructure
- Follows Dependency Inversion Principle
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List


class TemplateFormatPort(ABC):
    """Port for template format conversion operations.
    
    This port defines the interface for converting between different
    template formats (snake_case ↔ camelCase, minimal ↔ full config).
    
    Implementations should provide:
    - Legacy format conversion (snake_case ↔ camelCase)
    - HF minimal template creation
    - HF attributes generation with CPU/RAM specs
    - Batch conversion operations
    """
    
    @abstractmethod
    def convert_to_legacy(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert template data to legacy camelCase format.
        
        Args:
            template_data: Template data in snake_case format
            
        Returns:
            Template data in camelCase format
            
        Example:
            Input: {"template_id": "test", "max_instances": 5}
            Output: {"templateId": "test", "maxInstances": 5}
        """
        pass
    
    @abstractmethod
    def convert_from_legacy(self, legacy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert legacy camelCase data to new snake_case format.
        
        Args:
            legacy_data: Template data in camelCase format
            
        Returns:
            Template data in snake_case format
            
        Example:
            Input: {"templateId": "test", "maxInstances": 5}
            Output: {"template_id": "test", "max_instances": 5}
        """
        pass
    
    @abstractmethod
    def create_minimal_template(self, template_data: Dict[str, Any], use_camel_case: bool = False) -> Dict[str, Any]:
        """Create HF-compatible minimal template with essential fields only.
        
        Args:
            template_data: Full template data
            use_camel_case: Whether to use camelCase field names
            
        Returns:
            Minimal template with essential fields for HF compatibility
            
        Note:
            HF minimal format includes: template_id, max_instances, attributes
        """
        pass
    
    @abstractmethod
    def create_hf_attributes(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create HF-compatible attributes object with CPU/RAM specs.
        
        Args:
            template_data: Template data containing instance_type
            
        Returns:
            HF attributes object with type, ncpus, nram specifications
            
        Example:
            Input: {"instance_type": "t2.micro"}
            Output: {
                "type": ["String", "X86_64"],
                "ncpus": ["Numeric", "1"],
                "nram": ["Numeric", "1024"]
            }
        """
        pass
    
    @abstractmethod
    def convert_batch_to_legacy(self, template_data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert multiple template data objects to legacy format.
        
        Args:
            template_data_list: List of template data in snake_case format
            
        Returns:
            List of template data in camelCase format
        """
        pass
    
    @abstractmethod
    def convert_batch_from_legacy(self, legacy_data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert multiple legacy format data to new format.
        
        Args:
            legacy_data_list: List of template data in camelCase format
            
        Returns:
            List of template data in snake_case format
        """
        pass
