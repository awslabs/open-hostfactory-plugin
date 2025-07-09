"""Template DTOs for application layer."""
from typing import Dict, Any, List, Optional
from pydantic import Field
from datetime import datetime

from src.domain.template.aggregate import Template
from src.application.dto.base import BaseDTO


class TemplateDTO(BaseDTO):
    """Data Transfer Object for template responses."""
    
    # Core fields
    template_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    
    # Instance configuration
    instance_type: Optional[str] = None
    image_id: Optional[str] = None
    max_instances: int = 1
    
    # Network configuration
    subnet_ids: List[str] = Field(default_factory=list)
    security_group_ids: List[str] = Field(default_factory=list)
    
    # Pricing and allocation
    price_type: str = "ondemand"
    allocation_strategy: str = "lowest_price"
    max_price: Optional[float] = None
    
    # Tags and metadata
    tags: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Provider-specific configuration
    provider_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Status and timestamps
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Legacy format fields for backward compatibility
    provider_api: Optional[str] = None
    max_number: Optional[int] = None
    vm_type: Optional[str] = None
    subnet_id: Optional[str] = None
    key_name: Optional[str] = None
    fleet_type: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, template: Template) -> 'TemplateDTO':
        """
        Create DTO from domain object.
        
        Args:
            template: Template domain object
            
        Returns:
            TemplateDTO instance
        """
        return cls(
            # Core fields
            template_id=template.template_id,
            name=template.name,
            description=template.description,
            
            # Instance configuration
            instance_type=template.instance_type,
            image_id=template.image_id,
            max_instances=template.max_instances,
            
            # Network configuration
            subnet_ids=template.subnet_ids,
            security_group_ids=template.security_group_ids,
            
            # Pricing and allocation
            price_type=template.price_type,
            allocation_strategy=template.allocation_strategy,
            max_price=template.max_price,
            
            # Tags and metadata
            tags=template.tags,
            metadata=template.metadata,
            
            # Provider configuration (empty dict for now)
            provider_config={},
            
            # Status and timestamps
            is_active=template.is_active,
            created_at=template.created_at,
            updated_at=template.updated_at,
            
            # Legacy format fields for backward compatibility
            provider_api=template.provider_api,
            max_number=template.max_instances,  # Map to legacy field name
            vm_type=template.instance_type,     # Map to legacy field name
            subnet_id=template.subnet_ids[0] if template.subnet_ids else None,  # First subnet for legacy
            key_name=None,  # Legacy field - not used in simplified structure
            fleet_type=None,  # Legacy field - not used in simplified structure
            attributes={}  # Legacy field - not used in simplified structure
        )
    
    def to_domain(self) -> Template:
        """Convert DTO back to domain Template object.
        
        Returns:
            Template domain object
        """
        return Template(
            template_id=self.template_id,
            name=self.name,
            description=self.description,
            image_id=self.image_id,
            instance_type=self.instance_type,
            max_instances=self.max_instances,
            subnet_ids=self.subnet_ids or [],
            security_group_ids=self.security_group_ids or [],
            price_type=self.price_type,
            allocation_strategy=self.allocation_strategy,
            max_price=self.max_price,
            tags=self.tags or {},
            metadata=self.metadata or {},
            provider_api=self.provider_api,
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
    
    def to_legacy_format(self, format_service: 'TemplateFormatService') -> Dict[str, Any]:
        """
        Convert to legacy camelCase format for backward compatibility.
        
        Args:
            format_service: Template format conversion service
        
        Returns:
            Dictionary in legacy format
        """
        # Convert DTO back to domain object and use format service
        domain_template = self.to_domain()
        return format_service.convert_to_legacy(domain_template)


class TemplateListResponse(BaseDTO):
    """Response for template list operations."""
    
    templates: List[TemplateDTO] = Field(default_factory=list)
    message: str = "Get available templates success."
    
    def to_dict(self, format_service: Optional['TemplateFormatService'] = None) -> Dict[str, Any]:
        """Convert to dictionary format.
        
        Args:
            format_service: Optional template format conversion service.
                          If None, uses standard Pydantic serialization.
            
        Returns:
            Dictionary with templates in requested format
        """
        if format_service is None:
            # Use standard Pydantic serialization with JSON-safe mode
            return {
                "templates": [template.model_dump(mode='json') for template in self.templates],
                "message": self.message
            }
        else:
            # Use legacy format conversion
            return {
                "templates": [template.to_legacy_format(format_service) for template in self.templates],
                "message": self.message
            }


class TemplateValidationResponse(BaseDTO):
    """Response for template validation operations."""
    
    total_templates: int = 0
    valid_templates: int = 0
    invalid_templates: int = 0
    validation_errors: List[Dict[str, Any]] = Field(default_factory=list)
    template_ids: List[str] = Field(default_factory=list)
    provider_apis: List[str] = Field(default_factory=list)
    
    @classmethod
    def from_validation_report(cls, report: Dict[str, Any]) -> 'TemplateValidationResponse':
        """Create response from validation report."""
        return cls(
            total_templates=report.get('total_templates', 0),
            valid_templates=report.get('valid_templates', 0),
            invalid_templates=report.get('invalid_templates', 0),
            validation_errors=report.get('validation_errors', []),
            template_ids=report.get('template_ids', []),
            provider_apis=report.get('provider_apis', [])
        )
