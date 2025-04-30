# src/domain/template/template_wizard.py
from typing import Dict, Any, Optional
import json
from src.domain.template.template_aggregate import Template
from src.domain.template.template_service import TemplateService
from src.domain.template.value_objects import TemplateId
from src.domain.template.exceptions import TemplateValidationError

class TemplateWizard:
    """Handles template creation and modification through interactive wizard."""
    
    def __init__(self, template_service: TemplateService):
        self._service = template_service

    def create_template(self) -> Template:
        """Interactive creation of a new template."""
        template_data = self._gather_basic_info()
        
        # Get AWS handler specific configuration
        handler_config = self._gather_handler_config(template_data["awsHandler"])
        template_data.update(handler_config)
        
        # Validate and save template
        try:
            return self._service.create_template(template_data)
        except TemplateValidationError as e:
            print("Template validation failed:")
            for field, error in e.errors.items():
                print(f"  {field}: {error}")
            raise

    def modify_template(self, template_id: TemplateId) -> Template:
        """Interactive modification of an existing template."""
        template = self._service.get_template(template_id)
        template_data = template.to_dict()
        
        # Show current values and allow modifications
        print("\nCurrent template configuration:")
        print(json.dumps(template_data, indent=2))
        
        if input("\nDo you want to modify this template? (y/n): ").lower() != 'y':
            return template
        
        # Allow modification of fields
        modified_data = self._gather_modifications(template_data)
        
        # Validate and save modifications
        try:
            return self._service.update_template(template_id, modified_data)
        except TemplateValidationError as e:
            print("Template validation failed:")
            for field, error in e.errors.items():
                print(f"  {field}: {error}")
            raise

    def _gather_basic_info(self) -> Dict[str, Any]:
        """Gather basic template information."""
        return {
            "templateId": input("Template ID: "),
            "awsHandler": self._get_aws_handler_type(),
            "maxNumber": int(input("Maximum number of instances: ")),
            "attributes": self._gather_attributes(),
            "imageId": input("Image ID: "),
            "securityGroupIds": self._gather_security_groups()
        }

    def _gather_handler_config(self, handler_type: str) -> Dict[str, Any]:
        """Gather handler-specific configuration."""
        config = {}
        
        if handler_type == "SpotFleet":
            config["fleetRole"] = input("Fleet Role ARN: ")
            config["maxSpotPrice"] = float(input("Max Spot Price (optional): ") or 0)
        
        # Add VM type configuration
        vm_type_choice = input("Use single VM type (1) or multiple types (2)? ")
        if vm_type_choice == "1":
            config["vmType"] = input("VM Type: ")
        else:
            config["vmTypes"] = self._gather_vm_types()
        
        return config

    def _gather_attributes(self) -> Dict[str, Any]:
        """Gather template attributes."""
        return {
            "type": ["String", input("Machine type (e.g., X86_64): ")],
            "ncores": ["Numeric", input("Number of cores: ")],
            "ncpus": ["Numeric", input("Number of CPUs: ")],
            "nram": ["Numeric", input("RAM in MB: ")]
        }

    def _gather_security_groups(self) -> List[str]:
        """Gather security group IDs."""
        groups = []
        while True:
            group = input("Security Group ID (empty to finish): ")
            if not group:
                break
            groups.append(group)
        return groups

    def _gather_vm_types(self) -> Dict[str, int]:
        """Gather VM types and their weights."""
        types = {}
        while True:
            vm_type = input("VM Type (empty to finish): ")
            if not vm_type:
                break
            weight = int(input(f"Weight for {vm_type}: "))
            types[vm_type] = weight
        return types

    def _gather_modifications(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Gather modifications to existing template."""
        modified = current_data.copy()
        
        for key, value in current_data.items():
            if key == "templateId":
                continue  # Don't allow templateId modification
                
            print(f"\nCurrent {key}: {value}")
            if input(f"Modify {key}? (y/n): ").lower() == 'y':
                if isinstance(value, dict):
                    modified[key] = self._modify_dict(value)
                elif isinstance(value, list):
                    modified[key] = self._modify_list(value)
                else:
                    modified[key] = input(f"New value for {key}: ")
                    
                    # Convert to appropriate type
                    if isinstance(value, int):
                        modified[key] = int(modified[key])
                    elif isinstance(value, float):
                        modified[key] = float(modified[key])
        
        return modified

    def _modify_dict(self, current: Dict) -> Dict:
        """Modify a dictionary value."""
        modified = current.copy()
        print("\nCurrent values:")
        for k, v in current.items():
            print(f"{k}: {v}")
            if input(f"Modify {k}? (y/n): ").lower() == 'y':
                modified[k] = input(f"New value for {k}: ")
        return modified

    def _modify_list(self, current: List) -> List:
        """Modify a list value."""
        modified = current.copy()
        print("\nCurrent values:", modified)
        if input("Replace entire list? (y/n): ").lower() == 'y':
            modified = []
            while True:
                value = input("Enter value (empty to finish): ")
                if not value:
                    break
                modified.append(value)
        return modified

    def _get_aws_handler_type(self) -> str:
        """Get AWS handler type with validation."""
        valid_handlers = [
            "EC2Fleet", "SpotFleet", "ASG", "RunInstances"
        ]
        print("\nAvailable AWS handlers:")
        for i, handler in enumerate(valid_handlers, 1):
            print(f"{i}. {handler}")
        
        while True:
            try:
                choice = int(input("\nSelect handler (1-4): "))
                if 1 <= choice <= len(valid_handlers):
                    return valid_handlers[choice - 1]
            except ValueError:
                pass
            print("Invalid choice. Please try again.")