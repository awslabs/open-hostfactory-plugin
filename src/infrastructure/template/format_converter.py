"""Template format converter for legacy and new formats."""
from typing import Dict, Any, List, Optional
from src.infrastructure.logging.logger import get_logger
from src.infrastructure.utilities.common.string_utils import to_snake_case, to_camel_case


class TemplateFormatConverter:
    """Converts between legacy (camelCase) and new (snake_case) template formats."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Special field mappings that don't follow standard conversion rules
        # These take precedence over automatic conversion
        self.special_legacy_to_new_mapping = {
            "maxNumber": "max_instances",  # Special business logic mapping
            "vmType": "instance_type",     # Domain-specific naming
            "vmTypes": "vm_types",         # Keep as is for special cases
        }
        
        # Reverse mapping for special cases
        self.special_new_to_legacy_mapping = {v: k for k, v in self.special_legacy_to_new_mapping.items()}
        
        # Standard field mappings (for reference, but we'll use auto-conversion)
        self.standard_legacy_to_new_mapping = {
            "templateId": "template_id",
            "providerApi": "provider_api", 
            "imageId": "image_id",
            "subnetId": "subnet_id",
            "subnetIds": "subnet_ids",
            "keyName": "key_name",
            "securityGroupIds": "security_group_ids",
            "instanceTags": "instance_tags",
            "fleetRole": "fleet_role",
            "maxSpotPrice": "max_spot_price",
            "allocationStrategy": "allocation_strategy",
            "userData": "user_data",
            "fleetType": "fleet_type",
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
        
        # All mappings combined (special + standard)  
        self.legacy_to_new_mapping = {**self.standard_legacy_to_new_mapping, **self.special_legacy_to_new_mapping}
        self.new_to_legacy_mapping = {v: k for k, v in self.legacy_to_new_mapping.items()}
    
    def convert_field_name_to_snake(self, field_name: str) -> str:
        """Convert field name to snake_case using hybrid approach."""
        # 1. Check special mappings first
        if field_name in self.special_legacy_to_new_mapping:
            return self.special_legacy_to_new_mapping[field_name]
        
        # 2. Check standard mappings
        if field_name in self.standard_legacy_to_new_mapping:
            return self.standard_legacy_to_new_mapping[field_name]
        
        # 3. Fallback to automatic conversion
        return to_snake_case(field_name)
    
    def convert_field_name_to_camel(self, field_name: str) -> str:
        """Convert field name to camelCase using hybrid approach."""
        # 1. Check special mappings first
        if field_name in self.special_new_to_legacy_mapping:
            return self.special_new_to_legacy_mapping[field_name]
        
        # 2. Check if it's in standard mappings
        if field_name in self.new_to_legacy_mapping:
            return self.new_to_legacy_mapping[field_name]
        
        # 3. Fallback to automatic conversion
        return to_camel_case(field_name)
    
    def convert_legacy_to_new(self, legacy_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert legacy camelCase template format to snake_case format.
        
        Args:
            legacy_data: Template data in legacy camelCase format
            
        Returns:
            Template data in snake_case format
        """
        result = {}
        
        # Convert keys using hybrid approach
        for key, value in legacy_data.items():
            new_key = self.convert_field_name_to_snake(key)
            result[new_key] = value
        
        # Handle special cases
        self._handle_special_conversions(result, legacy_data)
        
        return result
    
    def convert_new_to_legacy(self, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert snake_case template format to legacy camelCase format.
        
        Args:
            new_data: Template data in snake_case format
            
        Returns:
            Template data in legacy camelCase format
        """
        result = {}
        
        # Convert keys using hybrid approach
        for key, value in new_data.items():
            legacy_key = self.convert_field_name_to_camel(key)
            result[legacy_key] = value
        
        return result
    
    def convert_legacy_templates_list(self, legacy_templates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert a list of legacy templates to new format.
        
        Args:
            legacy_templates: List of templates in legacy format
            
        Returns:
            List of templates in new format
        """
        return [self.convert_legacy_to_new(template) for template in legacy_templates]
    
    def _handle_special_conversions(self, result: Dict[str, Any], legacy_data: Dict[str, Any]) -> None:
        """
        Handle special conversion cases that need custom logic.
        
        Args:
            result: The converted data dictionary to modify
            legacy_data: Original legacy data for reference
        """
        # Handle subnet ID conversion (single to list)
        if 'subnet_id' in result and 'subnet_ids' not in result:
            subnet_id = result.pop('subnet_id')
            if subnet_id:
                result['subnet_ids'] = [subnet_id] if isinstance(subnet_id, str) else subnet_id
        
        # Ensure template_id is present
        if 'template_id' not in result and 'templateId' in legacy_data:
            result['template_id'] = legacy_data['templateId']
        
        # Handle attributes (keep as-is)
        if 'attributes' in legacy_data:
            result['attributes'] = legacy_data['attributes']
        
        # Set default values for required fields
        if 'max_instances' not in result:
            result['max_instances'] = legacy_data.get('maxNumber', 1)
        
        # Ensure provider_api is set
        if 'provider_api' not in result and 'providerApi' in legacy_data:
            result['provider_api'] = legacy_data['providerApi']
    
    def validate_conversion(self, original: Dict[str, Any], converted: Dict[str, Any]) -> bool:
        """
        Validate that conversion preserved essential data.
        
        Args:
            original: Original template data
            converted: Converted template data
            
        Returns:
            True if conversion is valid, False otherwise
        """
        # Check essential fields are present
        essential_fields = ['template_id', 'provider_api']
        
        for field in essential_fields:
            if field not in converted:
                self.logger.error(f"Conversion validation failed: missing {field}")
                return False
        
        # Check template_id matches
        original_id = original.get('templateId') or original.get('template_id')
        converted_id = converted.get('template_id')
        
        if original_id != converted_id:
            self.logger.error(f"Conversion validation failed: template_id mismatch {original_id} != {converted_id}")
            return False
        
        return True
    
    def _create_hf_attributes(self, template_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Create HF attributes object with derived values.
        
        Args:
            template_data: Template data in snake_case format
            
        Returns:
            HF attributes dictionary
        """
        instance_type = template_data.get("instance_type", "t2.micro")
        
        # Derive CPU and RAM from instance type (simplified mapping)
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
    
    def _calculate_available_number(self, template_data: Dict[str, Any]) -> Optional[int]:
        """Calculate available number of instances (placeholder implementation)."""
        max_instances = template_data.get("max_instances", 1)
        # In a real implementation, this would check current usage
        return max_instances
    
    def _get_requested_machines(self, template_data: Dict[str, Any]) -> List[str]:
        """Get list of requested machines (placeholder implementation)."""
        # In a real implementation, this would query active machines
        return []
    
    def _create_vm_types(self, template_data: Dict[str, Any]) -> Dict[str, int]:
        """Create vmTypes object from instance type."""
        instance_type = template_data.get("instance_type")
        if instance_type:
            return {instance_type: 1}
        return {}
    
    def _format_instance_tags(self, template_data: Dict[str, Any]) -> Optional[str]:
        """Format tags as HF-compatible string."""
        tags = template_data.get("tags", {})
        if not tags:
            return None
        
        # Convert dict to key=value;key=value format
        tag_pairs = [f"{key}={value}" for key, value in tags.items()]
        return ";".join(tag_pairs)
