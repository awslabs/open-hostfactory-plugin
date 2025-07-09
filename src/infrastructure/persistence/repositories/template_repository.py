"""Single template repository implementation using storage strategy composition."""
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.domain.template.repository import TemplateRepository as TemplateRepositoryInterface
from src.domain.template.aggregate import Template
from src.domain.template.value_objects import TemplateId
from src.infrastructure.persistence.base.strategy import BaseStorageStrategy
from src.infrastructure.logging.logger import get_logger
from src.infrastructure.error.decorators import handle_infrastructure_exceptions


class TemplateSerializer:
    """Handles Template aggregate serialization/deserialization."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    @handle_infrastructure_exceptions(context="template_serialization")
    def to_dict(self, template: Template) -> Dict[str, Any]:
        """Convert Template aggregate to dictionary."""
        try:
            return {
                'template_id': str(template.template_id.value),
                'name': template.name,
                'description': template.description,
                'image_id': template.image_id,
                'instance_type': template.instance_type.value if template.instance_type else None,
                'key_name': template.key_name,
                'security_group_ids': template.security_group_ids,
                'subnet_ids': template.subnet_ids,
                'user_data': template.user_data,
                'tags': dict(template.tags.value) if template.tags else {},
                'metadata': template.metadata or {},
                'provider_api': template.provider_api,
                'is_active': template.is_active,
                'created_at': template.created_at.isoformat(),
                'updated_at': template.updated_at.isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to serialize template {template.template_id}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="template_deserialization")
    def from_dict(self, data: Dict[str, Any]) -> Template:
        """Convert dictionary to Template aggregate."""
        try:
            self.logger.debug(f"Converting template data: {data}")
            
            # Parse datetime fields with defaults for legacy data
            now = datetime.now()
            created_at = datetime.fromisoformat(data['created_at']) if 'created_at' in data else now
            updated_at = datetime.fromisoformat(data['updated_at']) if 'updated_at' in data else now
            
            # Convert legacy format to new format
            template_id = data.get('templateId', data.get('template_id'))
            if not template_id:
                raise ValueError(f"No template_id found in data: {list(data.keys())}")
                
            template_data = {
                'template_id': template_id,
                'name': data.get('name', template_id),
                'description': data.get('description'),
                'image_id': data.get('imageId', data.get('image_id')),
                'instance_type': data.get('vmType', data.get('instance_type')),
                'key_name': data.get('keyName', data.get('key_name')),
                'security_group_ids': data.get('securityGroupIds', data.get('security_group_ids', [])),
                'subnet_ids': [data.get('subnetId')] if data.get('subnetId') else data.get('subnet_ids', []),
                'user_data': data.get('user_data'),
                'tags': data.get('tags', {}),
                'metadata': data.get('metadata', {}),
                'provider_api': data.get('providerApi', data.get('provider_api')),
                'is_active': data.get('is_active', True),
                'created_at': created_at,
                'updated_at': updated_at,
                'max_instances': data.get('maxNumber', data.get('max_instances', 1)),
                'attributes': data.get('attributes', {}),
                'fleet_type': data.get('fleetType', data.get('fleet_type'))
            }
            
            self.logger.debug(f"Converted template_data: {template_data}")
            
            # Create template using standard constructor
            template = Template(
                template_id=template_data['template_id'],
                name=template_data['name'],
                description=template_data['description'],
                image_id=template_data['image_id'],
                instance_type=template_data['instance_type'],
                max_instances=template_data['max_instances'],
                subnet_ids=template_data['subnet_ids'],
                security_group_ids=template_data['security_group_ids'],
                tags=template_data['tags'],
                metadata=template_data['metadata'],
                provider_config={
                    'provider_api': template_data['provider_api'],
                    'key_name': template_data['key_name'],
                    'user_data': template_data['user_data'],
                    'attributes': template_data['attributes'],
                    'fleet_type': template_data['fleet_type']
                },
                created_at=template_data['created_at'],
                updated_at=template_data['updated_at']
            )
            
            return template
            
        except Exception as e:
            self.logger.error(f"Failed to deserialize template data: {e}")
            raise


class TemplateRepositoryImpl(TemplateRepositoryInterface):
    """Single template repository implementation using storage strategy composition."""
    
    def __init__(self, storage_strategy: BaseStorageStrategy):
        """Initialize repository with storage strategy."""
        self.storage_strategy = storage_strategy
        self.serializer = TemplateSerializer()
        self.logger = get_logger(__name__)
    
    @handle_infrastructure_exceptions(context="template_save")
    def save(self, template: Template) -> List[Any]:
        """Save template using storage strategy and return extracted events."""
        try:
            # Save the template
            template_data = self.serializer.to_dict(template)
            self.storage_strategy.save(str(template.template_id.value), template_data)
            
            # Extract events from the aggregate
            events = template.get_domain_events()
            template.clear_domain_events()
            
            self.logger.debug(f"Saved template {template.template_id} and extracted {len(events)} events")
            return events
            
        except Exception as e:
            self.logger.error(f"Failed to save template {template.template_id}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="template_retrieval")
    def get_by_id(self, template_id: TemplateId) -> Optional[Template]:
        """Get template by ID using storage strategy."""
        try:
            data = self.storage_strategy.find_by_id(str(template_id.value))
            if data:
                return self.serializer.from_dict(data)
            return None
        except Exception as e:
            self.logger.error(f"Failed to get template {template_id}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="template_retrieval")
    def find_by_id(self, template_id: TemplateId) -> Optional[Template]:
        """Find template by ID (alias for get_by_id)."""
        return self.get_by_id(template_id)
    
    @handle_infrastructure_exceptions(context="template_search")
    def find_by_template_id(self, template_id: str) -> Optional[Template]:
        """Find template by template ID string."""
        try:
            return self.get_by_id(TemplateId(value=template_id))  # Fix: use value parameter
        except Exception as e:
            self.logger.error(f"Failed to find template by template_id {template_id}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="template_search")
    def find_by_name(self, name: str) -> Optional[Template]:
        """Find template by name."""
        try:
            criteria = {"name": name}
            data_list = self.storage_strategy.find_by_criteria(criteria)
            if data_list:
                return self.serializer.from_dict(data_list[0])
            return None
        except Exception as e:
            self.logger.error(f"Failed to find template by name {name}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="template_search")
    def find_active_templates(self) -> List[Template]:
        """Find active templates."""
        try:
            criteria = {"is_active": True}
            data_list = self.storage_strategy.find_by_criteria(criteria)
            return [self.serializer.from_dict(data) for data in data_list]
        except Exception as e:
            self.logger.error(f"Failed to find active templates: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="template_search")
    def find_by_provider_api(self, provider_api: str) -> List[Template]:
        """Find templates by provider API."""
        try:
            criteria = {"provider_api": provider_api}
            data_list = self.storage_strategy.find_by_criteria(criteria)
            return [self.serializer.from_dict(data) for data in data_list]
        except Exception as e:
            self.logger.error(f"Failed to find templates by provider_api {provider_api}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="template_search")
    def find_all(self) -> List[Template]:
        """Find all templates."""
        try:
            all_data = self.storage_strategy.find_all()
            return [self.serializer.from_dict(data) for data in all_data.values()]
        except Exception as e:
            self.logger.error(f"Failed to find all templates: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="template_search")
    def search_templates(self, criteria: Dict[str, Any]) -> List[Template]:
        """Search templates by criteria."""
        try:
            data_list = self.storage_strategy.find_by_criteria(criteria)
            return [self.serializer.from_dict(data) for data in data_list]
        except Exception as e:
            self.logger.error(f"Failed to search templates with criteria {criteria}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="template_deletion")
    def delete(self, template_id: TemplateId) -> None:
        """Delete template by ID."""
        try:
            self.storage_strategy.delete(str(template_id.value))
            self.logger.debug(f"Deleted template {template_id}")
        except Exception as e:
            self.logger.error(f"Failed to delete template {template_id}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="template_existence_check")
    def exists(self, template_id: TemplateId) -> bool:
        """Check if template exists."""
        try:
            return self.storage_strategy.exists(str(template_id.value))
        except Exception as e:
            self.logger.error(f"Failed to check if template {template_id} exists: {e}")
            raise
