"""Template configuration adapter implementing TemplateConfigurationPort."""
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from src.domain.base.ports.template_configuration_port import TemplateConfigurationPort
from src.infrastructure.template.sync_configuration_store import SyncTemplateConfigurationStore
from src.infrastructure.template.configuration_store import TemplateConfigurationStore
from src.infrastructure.template.dtos import TemplateDTO
from src.infrastructure.template.mappers import TemplateMapper

# Use TYPE_CHECKING to avoid direct domain import
if TYPE_CHECKING:
    from src.domain.template.aggregate import Template


class TemplateConfigurationAdapter(TemplateConfigurationPort):
    """Adapter implementing TemplateConfigurationPort using new unified configuration store."""

    def __init__(self, sync_config_store: SyncTemplateConfigurationStore):
        """
        Initialize adapter with synchronous configuration store.
        
        Args:
            sync_config_store: Synchronous template configuration store
        """
        self._sync_store = sync_config_store
    
    def get_template_manager(self) -> Any:
        """Get template configuration store (replaces manager)."""
        return self._sync_store
    
    def load_templates(self) -> List['Template']:
        """Load all templates from configuration."""
        # Load DTOs from configuration store and convert to domain objects
        template_dtos = self._sync_store.get_templates()
        return [TemplateMapper.from_dto(dto) for dto in template_dtos]
    
    def get_template_config(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for specific template."""
        template_dto = self._sync_store.get_template_by_id(template_id)
        if template_dto:
            return template_dto.configuration
        return None
    
    def validate_template_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate template configuration and return errors."""
        errors = []
        
        # Basic validation
        if not config.get('template_id'):
            errors.append("Template ID is required")
        
        if not config.get('provider_api'):
            errors.append("Provider API is required")
        
        if not config.get('image_id'):
            errors.append("Image ID is required")
        
        # Use template extensions for provider-specific validation
        try:
            from src.infrastructure.template.extensions import get_template_extension
            
            # Determine provider type from config
            provider_type = self._determine_provider_type(config)
            if provider_type:
                extension = get_template_extension(provider_type)
                
                # Create a temporary template for validation
                from src.domain.template.aggregate import Template
                temp_template = Template(
                    template_id=config.get('template_id', 'temp'),
                    image_id=config.get('image_id', ''),
                    instance_type=config.get('instance_type', ''),
                    subnet_ids=config.get('subnet_ids', []),
                    security_group_ids=config.get('security_group_ids', []),
                    price_type=config.get('price_type', 'ondemand'),
                    provider_api=config.get('provider_api', ''),
                    metadata=config.get('metadata', {})
                )
                
                # Apply extension validation
                extension_errors = extension.validate_template(temp_template)
                errors.extend(extension_errors)
                
        except Exception as e:
            # Don't fail validation if extension validation fails
            pass
        
        return errors
    
    def _determine_provider_type(self, config: Dict[str, Any]) -> Optional[str]:
        """Determine provider type from configuration."""
        provider_api = config.get('provider_api', '')
        
        # Map provider APIs to provider types
        if provider_api in ['EC2Fleet', 'SpotFleet', 'RunInstances', 'AutoScalingGroup']:
            return 'aws'
        
        # Check for AWS-specific fields
        aws_fields = ['fleet_type', 'allocation_strategy', 'spot_fleet_request_expiry', 'fleet_role']
        if any(field in config for field in aws_fields):
            return 'aws'
        
        return None
