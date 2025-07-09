"""Template configuration value object - core template domain logic."""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import datetime



class Template(BaseModel):
    """Template configuration value object - represents VM template configuration."""
    model_config = ConfigDict(frozen=False, validate_assignment=True)
    
    # Core template fields (provider-agnostic)
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
    
    # Provider API (direct field for simplicity)
    provider_api: Optional[str] = None
    
    # Timestamps for tracking
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Active status flag
    is_active: bool = True
    
    def __init__(self, **data):
        """Initialize template with default values and validation.
        
        Args:
            **data: Template configuration data
            
        Note:
            Sets default name from template_id if not provided.
            Sets default timestamps if not provided.
        """
        # Set default name if not provided
        if 'name' not in data and 'template_id' in data:
            data['name'] = data['template_id']
        
        # Set default timestamps if not provided
        if 'created_at' not in data:
            data['created_at'] = datetime.now()
        
        if 'updated_at' not in data:
            data['updated_at'] = datetime.now()
        
        super().__init__(**data)
    
    @model_validator(mode='after')
    
    def validate_template(self) -> 'Template':
        """Validate template configuration."""
        if self.max_instances <= 0:
            raise ValueError("max_instances must be greater than 0")
        
        if not self.image_id:
            raise ValueError("image_id is required")
        
        if not self.subnet_ids:
            raise ValueError("At least one subnet_id is required")
        
        if not self.template_id:
            raise ValueError("template_id is required")
        
        return self
    
    # Host Factory standard fields (provider-agnostic interface)
    vm_type: Optional[str] = None
    vm_types: Dict[str, Any] = Field(default_factory=dict)
    key_name: Optional[str] = None
    user_data: Optional[str] = None
    
    @property
    def subnet_id(self) -> Optional[str]:
        """Convenience property for single subnet access."""
        return self.subnet_ids[0] if self.subnet_ids else None
    
    def update_image_id(self, new_image_id: str) -> 'Template':
        """Update the image ID and return a new template instance."""
        data = self.model_dump()
        data['image_id'] = new_image_id
        data['updated_at'] = datetime.now()
        return Template.model_validate(data)
    
    
    def add_subnet(self, subnet_id: str) -> 'Template':
        """Add a subnet ID."""
        if subnet_id not in self.subnet_ids:
            new_subnets = self.subnet_ids + [subnet_id]
            data = self.model_dump()
            data['subnet_ids'] = new_subnets
            data['updated_at'] = datetime.now()
            return Template.model_validate(data)
        return self
    
    
    def remove_subnet(self, subnet_id: str) -> 'Template':
        """Remove a subnet ID."""
        if subnet_id in self.subnet_ids:
            new_subnets = [s for s in self.subnet_ids if s != subnet_id]
            data = self.model_dump()
            data['subnet_ids'] = new_subnets
            data['updated_at'] = datetime.now()
            return Template.model_validate(data)
        return self
    
    
    def add_security_group(self, security_group_id: str) -> 'Template':
        """Add a security group ID."""
        if security_group_id not in self.security_group_ids:
            new_sgs = self.security_group_ids + [security_group_id]
            data = self.model_dump()
            data['security_group_ids'] = new_sgs
            data['updated_at'] = datetime.now()
            return Template.model_validate(data)
        return self
    
    
    def remove_security_group(self, security_group_id: str) -> 'Template':
        """Remove a security group ID."""
        if security_group_id in self.security_group_ids:
            new_sgs = [sg for sg in self.security_group_ids if sg != security_group_id]
            data = self.model_dump()
            data['security_group_ids'] = new_sgs
            data['updated_at'] = datetime.now()
            return Template.model_validate(data)
        return self
    
    
    def set_provider_config(self, config: Dict[str, Any]) -> 'Template':
        """Set provider-specific configuration."""
        data = self.model_dump()
        data['provider_config'] = {**self.provider_config, **config}
        data['updated_at'] = datetime.now()
        return Template.model_validate(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        return self.model_dump()
    
    
    def to_legacy_format(self) -> Dict[str, Any]:
        """
        Convert template to legacy camelCase format.
        
        Returns:
            Dictionary representation of template
        """
        return self.model_dump()
    
    def __str__(self) -> str:
        """String representation of template."""
        return f"Template(id={self.template_id}, provider={self.provider_api}, instances={self.max_instances})"
    
    def __repr__(self) -> str:
        """Detailed string representation of template."""
        return (f"Template(template_id='{self.template_id}', name='{self.name}', "
                f"provider_api='{self.provider_api}', max_instances={self.max_instances})")


# Provider-specific template extensions should be implemented in their respective provider packages
# e.g., src/providers/aws/domain/template/aggregate.py for AWS-specific extensions
