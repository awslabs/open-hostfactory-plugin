"""JSON template repository and strategy implementation."""
import os
import json
from typing import List, Optional, Dict, Any

from src.domain.template.repository import TemplateRepository
from src.domain.template.aggregate import Template
from src.domain.base.exceptions import ConfigurationError
from src.infrastructure.logging.logger import get_logger
from src.infrastructure.persistence.base import StrategyBasedRepository
from src.infrastructure.persistence.json.strategy import JSONStorageStrategy
from src.infrastructure.patterns.singleton_registry import SingletonRegistry

class TemplateJSONStorageStrategy(JSONStorageStrategy):
    """JSON storage strategy for templates with legacy format support."""
    
    def __init__(self, file_path: str, legacy_file_path: Optional[str] = None, create_dirs: bool = True):
        """
        Initialize with both main and legacy file paths.
        
        Args:
            file_path: Path to the main templates.json file
            legacy_file_path: Optional path to the legacy templates file
            create_dirs: Whether to create directories
        """
        super().__init__(file_path, create_dirs)
        self.legacy_file_path = legacy_file_path
        self.logger = get_logger(__name__)
        
        # Log which files we found
        if os.path.exists(self.file_path) and self.legacy_file_path and os.path.exists(self.legacy_file_path):
            self.logger.info(f"Found both template files, will merge contents")
            self.logger.debug(f"Templates file: {self.file_path}")
            self.logger.debug(f"Legacy templates file: {self.legacy_file_path}")
        elif self.legacy_file_path and os.path.exists(self.legacy_file_path):
            self.logger.info(f"Found only legacy templates file: {self.legacy_file_path}")
        elif os.path.exists(self.file_path):
            self.logger.info(f"Found only templates.json: {self.file_path}")
        else:
            self.logger.warning(f"No template files found at {self.file_path} or {self.legacy_file_path}")
    
    def find_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Find entity by ID, checking both main and legacy files.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            Entity data if found, None otherwise
        """
        # First, try to find in the main file
        entity_data = super().find_by_id(entity_id)
        if entity_data:
            return entity_data
            
        # If not found in main file and legacy file exists, check there
        if self.legacy_file_path and os.path.exists(self.legacy_file_path):
            try:
                with open(self.legacy_file_path, 'r') as f:
                    legacy_data = json.load(f)
                    if isinstance(legacy_data, dict) and 'templates' in legacy_data:
                        for template in legacy_data['templates']:
                            # Check both camelCase and snake_case template IDs
                            template_id = template.get('template_id') or template.get('templateId')
                            if template_id == entity_id:
                                # Convert to snake_case format
                                self.logger.debug(f"Found template {entity_id} in legacy file {self.legacy_file_path}")
                                return self._convert_legacy_template(template)
            except Exception as e:
                self.logger.error(f"Error loading legacy template {entity_id}: {str(e)}")
                
        # Not found in either file
        return None
    
    def find_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Load templates from both files and merge them.
        
        Returns:
            Dictionary of template ID to template data
        """
        # Load templates from main file
        templates_data = {}
        
        # Load from main file if it exists
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        if 'templates' in data and isinstance(data['templates'], list):
                            # Convert list to dictionary by template_id
                            for template in data['templates']:
                                # Convert to snake_case if needed
                                template_data = self._ensure_snake_case(template)
                                template_id = template_data.get('template_id')
                                if template_id:
                                    templates_data[template_id] = template_data
                        else:
                            # Assume it's already a dictionary of template_id to template_data
                            templates_data = data
            except Exception as e:
                self.logger.error(f"Error loading templates from {self.file_path}: {str(e)}")
        
        # Load from legacy file if it exists
        if self.legacy_file_path and os.path.exists(self.legacy_file_path):
            try:
                with open(self.legacy_file_path, 'r') as f:
                    legacy_data = json.load(f)
                    if isinstance(legacy_data, dict) and 'templates' in legacy_data:
                        for template in legacy_data['templates']:
                            # Convert to snake_case format
                            template_data = self._convert_legacy_template(template)
                            
                            # Get template ID
                            template_id = template_data.get('template_id')
                            
                            # Add to templates if not already present
                            if template_id and template_id not in templates_data:
                                templates_data[template_id] = template_data
            except Exception as e:
                self.logger.error(f"Error loading legacy templates: {str(e)}")
        
        return templates_data
    
    def save(self, entity_id: str, data: Dict[str, Any]) -> None:
        """
        Save entity data.
        
        For templates, we save to the main file and update the legacy file if needed.
        
        Args:
            entity_id: Entity ID
            data: Entity data
        """
        # First, save to the main file
        super().save(entity_id, data)
        
        # If the template exists in the legacy file, update it there too
        if self.legacy_file_path and os.path.exists(self.legacy_file_path):
            try:
                # Load legacy templates
                with open(self.legacy_file_path, 'r') as f:
                    legacy_data = json.load(f)
                
                # Check if this template exists in the legacy file
                if isinstance(legacy_data, dict) and 'templates' in legacy_data:
                    updated = False
                    for i, template in enumerate(legacy_data['templates']):
                        template_id_key = 'template_id' if 'template_id' in template else 'templateId'
                        if template.get(template_id_key) == entity_id:
                            # Convert back to camelCase for legacy file
                            legacy_data['templates'][i] = self._convert_to_legacy_format(data)
                            updated = True
                            break
                    
                    # If the template was updated in the legacy file, save it
                    if updated:
                        with open(self.legacy_file_path, 'w') as f:
                            json.dump(legacy_data, f, indent=2)
                            self.logger.debug(f"Updated template {entity_id} in legacy file {self.legacy_file_path}")
            except Exception as e:
                self.logger.error(f"Error updating legacy template file: {str(e)}")
    
    def delete(self, entity_id: str) -> None:
        """
        Delete entity.
        
        For templates, we delete from both the main file and the legacy file.
        
        Args:
            entity_id: Entity ID
        """
        # First, delete from the main file
        super().delete(entity_id)
        
        # If the template exists in the legacy file, delete it there too
        if self.legacy_file_path and os.path.exists(self.legacy_file_path):
            try:
                # Load legacy templates
                with open(self.legacy_file_path, 'r') as f:
                    legacy_data = json.load(f)
                
                # Check if this template exists in the legacy file
                if isinstance(legacy_data, dict) and 'templates' in legacy_data:
                    original_length = len(legacy_data['templates'])
                    legacy_data['templates'] = [
                        t for t in legacy_data['templates'] 
                        if not (t.get('template_id') == entity_id or t.get('templateId') == entity_id)
                    ]
                    
                    # If the template was deleted from the legacy file, save it
                    if len(legacy_data['templates']) < original_length:
                        with open(self.legacy_file_path, 'w') as f:
                            json.dump(legacy_data, f, indent=2)
                            self.logger.debug(f"Deleted template {entity_id} from legacy file {self.legacy_file_path}")
            except Exception as e:
                self.logger.error(f"Error deleting from legacy template file: {str(e)}")
    
    def _ensure_snake_case(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure template data uses snake_case keys.
        
        Args:
            template_data: Template data
            
        Returns:
            Template data with snake_case keys
        """
        # Check if already in snake_case format
        if 'template_id' in template_data:
            return template_data
        
        # Convert from camelCase to snake_case
        return self._convert_legacy_template(template_data)
    
    def _convert_legacy_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert legacy camelCase template format to snake_case format.
        
        Args:
            template_data: Template data in legacy format
            
        Returns:
            Template data in snake_case format
        """
        result = {}
        
        # Mapping of camelCase to snake_case for template fields
        field_mapping = {
            "templateId": "template_id",
            "providerApi": "provider_api",
            "maxNumber": "max_number",
            "imageId": "image_id",
            "subnetId": "subnet_id",
            "subnetIds": "subnet_ids",
            "vmType": "vm_type",
            "vmTypes": "vm_types",
            "keyName": "key_name",
            "securityGroupIds": "security_group_ids",
            "instanceTags": "instance_tags",
            "fleetRole": "fleet_role",
            "maxSpotPrice": "max_spot_price",
            "allocationStrategy": "allocation_strategy",
            "userData": "user_data",
            "fleetType": "fleet_type",
            
            # Symphony-specific fields
            "priceType": "price_type",
            "rootDeviceVolumeSize": "root_device_volume_size",
            "volumeType": "volume_type",
            "iops": "iops",
            "userDataScript": "user_data_script",
            "instanceProfile": "instance_profile",
            "spotFleetRequestExpiry": "spot_fleet_request_expiry",
            "allocationStrategyOnDemand": "allocation_strategy_on_demand",
            "percentOnDemand": "percent_on_demand",
            "poolsCount": "pools_count",
            "vmTypesOnDemand": "vm_types_on_demand",
            "vmTypesPriority": "vm_types_priority",
            "launchTemplateId": "launch_template_id"
        }
        
        # Convert keys using the mapping
        for key, value in template_data.items():
            new_key = field_mapping.get(key, key)
            result[new_key] = value
        
        # Handle attributes specially
        if 'attributes' in template_data:
            result['attributes'] = template_data['attributes']
        
        return result
    
    def _convert_to_legacy_format(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert snake_case template format to legacy camelCase format.
        
        Args:
            template_data: Template data in snake_case format
            
        Returns:
            Template data in legacy camelCase format
        """
        result = {}
        
        # Mapping of snake_case to camelCase for template fields
        field_mapping = {
            "template_id": "templateId",
            "provider_api": "providerApi",
            "max_number": "maxNumber",
            "image_id": "imageId",
            "subnet_id": "subnetId",
            "subnet_ids": "subnetIds",
            "vm_type": "vmType",
            "vm_types": "vmTypes",
            "key_name": "keyName",
            "security_group_ids": "securityGroupIds",
            "instance_tags": "instanceTags",
            "fleet_role": "fleetRole",
            "max_spot_price": "maxSpotPrice",
            "allocation_strategy": "allocationStrategy",
            "user_data": "userData",
            "fleet_type": "fleetType",
            
            # Symphony-specific fields
            "price_type": "priceType",
            "root_device_volume_size": "rootDeviceVolumeSize",
            "volume_type": "volumeType",
            "iops": "iops",
            "user_data_script": "userDataScript",
            "instance_profile": "instanceProfile",
            "spot_fleet_request_expiry": "spotFleetRequestExpiry",
            "allocation_strategy_on_demand": "allocationStrategyOnDemand",
            "percent_on_demand": "percentOnDemand",
            "pools_count": "poolsCount",
            "vm_types_on_demand": "vmTypesOnDemand",
            "vm_types_priority": "vmTypesPriority",
            "launch_template_id": "launchTemplateId"
        }
        
        # Convert keys using the mapping
        for key, value in template_data.items():
            new_key = field_mapping.get(key, key)
            result[new_key] = value
        
        # Handle attributes specially
        if 'attributes' in template_data:
            result['attributes'] = template_data['attributes']
        
        return result

class JSONTemplateRepositoryImpl(TemplateRepository):
    """
    JSON repository implementation for templates.
    
    This implementation uses composition with StrategyBasedRepository and
    TemplateJSONStorageStrategy to handle template storage. It also implements
    caching to avoid repeated file I/O operations.
    
    This class should be accessed through the get_template_repository_singleton()
    function to ensure only one instance exists.
    """
    
    def __init__(self, templates_path: str, legacy_templates_path: Optional[str] = None):
        """
        Initialize the repository with template file paths.
        
        Args:
            templates_path: Path to the main templates.json file
            legacy_templates_path: Optional path to the legacy templates file
        """
        # Create logger
        self.logger = get_logger(__name__)
        
        # Create the storage strategy
        self.storage_strategy = TemplateJSONStorageStrategy(
            templates_path, 
            legacy_templates_path
        )
        
        # Create the base repository using composition
        self._repository = StrategyBasedRepository(Template, self.storage_strategy)
        
        # Store paths for reference
        self.templates_path = templates_path
        self.legacy_templates_path = legacy_templates_path
        
        # Log initialization (file logging is already done in the storage strategy)
        self.logger.debug("Initialized JSONTemplateRepositoryImpl")
        
    def find_by_id(self, template_id: str) -> Optional[Template]:
        """
        Find a template by its ID.
        
        Args:
            template_id: The ID of the template to find
            
        Returns:
            Template if found, None otherwise
        """
        template = self._repository.find_by_id(template_id)
        if template and template.image_id.startswith('/aws/service/'):
            # Resolve SSM parameter at the repository boundary
            template = self._resolve_ami_id_in_template(template)
        return template
        
    def find_all(self) -> List[Template]:
        """
        Find all templates.
        
        Returns:
            List of templates
        """
        self.logger.debug("JSONTemplateRepositoryImpl.find_all() called")
        templates = self._repository.find_all()
        
        # Resolve SSM parameters for all templates at the repository boundary
        resolved_templates = []
        for template in templates:
            if template.image_id.startswith('/aws/service/'):
                template = self._resolve_ami_id_in_template(template)
            resolved_templates.append(template)
        
        return resolved_templates
        
    def save(self, template: Template) -> None:
        """
        Save or update a template.
        
        Args:
            template: The template to save
            
        Raises:
            ConfigurationError: If there's an error saving the template
        """
        try:
            self._repository.save(template)
        except Exception as e:
            raise ConfigurationError("Template", f"Failed to save template: {str(e)}")
        
    def delete(self, template_id: str) -> None:
        """
        Delete a template.
        
        Args:
            template_id: The ID of the template to delete
        """
        self._repository.delete(template_id)
        
    def exists(self, template_id: str) -> bool:
        """
        Check if a template exists.
        
        Args:
            template_id: The ID of the template to check
            
        Returns:
            True if the template exists, False otherwise
        """
        return self._repository.exists(template_id)
        
    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[Template]:
        """
        Find templates by criteria.
        
        Args:
            criteria: Dictionary of field-value pairs to match
            
        Returns:
            List of matching templates
        """
        templates = self._repository.find_by_criteria(criteria)
        
        # Resolve SSM parameters for all templates at the repository boundary
        resolved_templates = []
        for template in templates:
            if template.image_id.startswith('/aws/service/'):
                template = self._resolve_ami_id_in_template(template)
            resolved_templates.append(template)
        
        return resolved_templates
        
    def _resolve_ami_id_in_template(self, template: Template) -> Template:
        """
        Resolve SSM parameter in template's image_id.
        
        Args:
            template: Template with SSM parameter path in image_id
            
        Returns:
            Template with resolved AMI ID
        """
        if not template.image_id.startswith('/aws/service/'):
            return template
            
        try:
            # Get AWS client from DI container directly
            from src.infrastructure.di.container import get_container
            from src.providers.aws.infrastructure.aws_client import AWSClient
            container = get_container()
            aws_client = container.get(AWSClient)
            
            # Get SSM client
            ssm_client = aws_client.ssm_client
            
            # Log at debug level since this is an implementation detail
            self.logger.debug(f"Resolving SSM parameter {template.image_id} for template {template.template_id}")
            
            # Get parameter value
            response = ssm_client.get_parameter(Name=template.image_id)
            if 'Parameter' not in response or 'Value' not in response['Parameter']:
                raise ValueError(f"Invalid SSM parameter response for {template.image_id}")
                
            ami_id = response['Parameter']['Value']
            
            # Log at debug level
            self.logger.debug(f"Resolved SSM parameter {template.image_id} to AMI ID: {ami_id}")
            
            # Create a new template with the resolved AMI ID
            return template.update_image_id(ami_id)
        except Exception as e:
            # Log the error but don't fail - return the original template
            self.logger.error(f"Failed to resolve SSM parameter {template.image_id} for template {template.template_id}: {str(e)}")
            return template
        
    # Domain-specific methods
    
    def find_by_handler_type(self, handler_type: str) -> List[Template]:
        """
        Find templates by AWS handler type.
        
        Args:
            handler_type: AWS handler type
            
        Returns:
            List of templates with the specified handler type
        """
        return self.find_by_criteria({'provider_api': handler_type})
        
    def find_available_templates(self) -> List[Template]:
        """
        Find all available templates.
        
        In this implementation, all templates in the file are considered available.
        
        Returns:
            List of available templates
        """
        return self.find_all()
        
    def find_by_capacity(self, min_capacity: int) -> List[Template]:
        """
        Find templates with specified minimum capacity.
        
        Args:
            min_capacity: Minimum capacity
            
        Returns:
            List of templates with at least the specified capacity
        """
        templates = self.find_all()
        return [template for template in templates if template.max_number >= min_capacity]
        
    def find_by_machine_type(self, machine_type: str) -> List[Template]:
        """
        Find templates for specific machine type.
        
        Args:
            machine_type: Machine type
            
        Returns:
            List of templates for the specified machine type
        """
        return self.find_by_criteria({'vm_type': machine_type})

def get_template_repository_singleton(
    templates_path: Optional[str] = None,
    legacy_templates_path: Optional[str] = None
) -> JSONTemplateRepositoryImpl:
    """
    Get or create a singleton instance of JSONTemplateRepositoryImpl.
    
    This function ensures that only one instance of JSONTemplateRepositoryImpl
    is created and reused throughout the application.
    
    Args:
        templates_path: Optional path to templates.json file (will use centralized resolution if not provided)
        legacy_templates_path: Optional path to legacy templates file (will use centralized resolution if not provided)
        
    Returns:
        Singleton instance of JSONTemplateRepositoryImpl
    """
    # Get singleton registry
    registry = SingletonRegistry.get_instance()
    
    # Check if repository is already registered
    if JSONTemplateRepositoryImpl in registry.get_all():
        return registry.get(JSONTemplateRepositoryImpl)
    
    # If paths are not provided, use centralized resolution instead of configuration
    if templates_path is None or legacy_templates_path is None:
        from src.config.manager import get_config_manager
        
        config_manager = get_config_manager()
        
        # Use centralized file resolution for consistent HF_PROVIDER_CONFDIR support
        templates_path = templates_path or config_manager.resolve_file('template', 'templates.json')
        legacy_templates_path = legacy_templates_path or config_manager.resolve_file('template', 'awsprov_templates.json')
        
        logger.info(f"Using centralized resolution for template files:")
        logger.info(f"  templates.json: {templates_path}")
        logger.info(f"  awsprov_templates.json: {legacy_templates_path}")
    
    # Create and register repository
    repository = JSONTemplateRepositoryImpl(templates_path, legacy_templates_path)
    registry.register(JSONTemplateRepositoryImpl, repository)
    
    return repository
