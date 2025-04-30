# src/domain/template/template_repository.py
import json
import os
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
from src.domain.template.template_aggregate import Template
from src.domain.template.value_objects import TemplateId, AWSHandlerType
from src.domain.core.exceptions import ConfigurationError

class TemplateRepository(ABC):
    """Repository interface for template persistence."""
    
    @abstractmethod
    def find_by_id(self, template_id: TemplateId) -> Optional[Template]:
        """
        Find a template by its ID.
        
        Args:
            template_id: The ID of the template to find
        Returns:
            Template if found, None otherwise
        """
        pass

    @abstractmethod
    def find_all(self) -> List[Template]:
        """
        Find all templates.
        
        Returns:
            List of all templates
        """
        pass

    @abstractmethod
    def save(self, template: Template) -> None:
        """
        Save or update a template.
        
        Args:
            template: The template to save
        Raises:
            ConfigurationError: If there's an error saving the template
        """
        pass

    @abstractmethod
    def delete(self, template_id: TemplateId) -> None:
        """
        Delete a template.
        
        Args:
            template_id: The ID of the template to delete
        """
        pass

    @abstractmethod
    def find_by_handler_type(self, handler_type: str) -> List[Template]:
        """
        Find templates by AWS handler type.
        
        Args:
            handler_type: The AWS handler type to filter by
        Returns:
            List of matching templates
        """
        pass

    @abstractmethod
    def find_available_templates(self) -> List[Template]:
        """
        Find all available templates.
        
        Returns:
            List of available templates
        """
        pass

    @abstractmethod
    def exists(self, template_id: TemplateId) -> bool:
        """
        Check if a template exists.
        
        Args:
            template_id: The ID of the template to check
        Returns:
            True if the template exists, False otherwise
        """
        pass

    def find_by_capacity(self, min_capacity: int) -> List[Template]:
        """
        Find templates with specified minimum capacity.
        
        Args:
            min_capacity: Minimum number of machines the template should support
            
        Returns:
            List of templates meeting the capacity requirement
        """
        pass

    def find_by_machine_type(self, machine_type: str) -> List[Template]:
        """
        Find templates for specific machine type.
        
        Args:
            machine_type: Type of machine to find templates for
            
        Returns:
            List of templates supporting the specified machine type
        """
        pass

class FileTemplateRepository(TemplateRepository):
    """Implementation that manages templates in awsprov_templates.json"""
    
    def __init__(self):
        self.template_file = os.path.join(
            os.environ.get('HF_PROVIDER_CONFDIR', ''),
            'awsprov_templates.json'
        )
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensure the templates file exists with valid structure."""
        if not os.path.exists(self.template_file):
            os.makedirs(os.path.dirname(self.template_file), exist_ok=True)
            self._save_templates({"templates": []})

    def _load_templates(self) -> Dict[str, Any]:
        """Load templates from the JSON file."""
        try:
            with open(self.template_file, 'r') as f:
                data = json.load(f)
                if not isinstance(data, dict) or 'templates' not in data:
                    raise ConfigurationError(
                        f"Invalid template file structure in {self.template_file}"
                    )
                return data
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in template file {self.template_file}: {str(e)}"
            )

    def _save_templates(self, data: Dict[str, Any]) -> None:
        """Save templates to the JSON file."""
        try:
            with open(self.template_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            raise ConfigurationError(
                f"Failed to save templates to {self.template_file}: {str(e)}"
            )

    def find_by_id(self, template_id: TemplateId) -> Optional[Template]:
        """Find a template by its ID."""
        data = self._load_templates()
        for template_dict in data['templates']:
            if template_dict['templateId'] == str(template_id):
                return Template.from_dict(template_dict)
        return None

    def find_all(self) -> List[Template]:
        """Find all templates without validation."""
        try:
            data = self._load_templates()
            return [Template.from_dict(t, validate=False) for t in data['templates']]
        except Exception as e:
            raise ConfigurationError(f"Failed to load templates: {str(e)}")

    def save(self, template: Template) -> None:
        """Save or update a template."""
        data = self._load_templates()
        templates = data['templates']
        
        template_dict = template.to_dict()
        
        # Update existing or add new
        for i, existing in enumerate(templates):
            if existing['templateId'] == str(template.template_id):
                templates[i] = template_dict
                break
        else:
            templates.append(template_dict)
        
        self._save_templates(data)

    def delete(self, template_id: TemplateId) -> None:
        """Delete a template."""
        data = self._load_templates()
        data['templates'] = [
            t for t in data['templates'] 
            if t['templateId'] != str(template_id)
        ]
        self._save_templates(data)

    def find_by_handler_type(self, handler_type: str) -> List[Template]:
        """Find templates by AWS handler type."""
        data = self._load_templates()
        return [
            Template.from_dict(t) for t in data['templates']
            if t.get('awsHandler') == handler_type
        ]

    def find_available_templates(self) -> List[Template]:
        """
        Find all available templates.
        In this implementation, all templates in the file are considered available.
        """
        return self.find_all()

    def exists(self, template_id: TemplateId) -> bool:
        """Check if a template exists."""
        data = self._load_templates()
        return any(
            t['templateId'] == str(template_id) 
            for t in data['templates']
        )

    def find_by_capacity(self, min_capacity: int) -> List[Template]:
        """Find templates with specified minimum capacity."""
        all_templates = self.find_all()
        return [
            template for template in all_templates
            if template.max_number >= min_capacity
        ]

    def find_by_machine_type(self, machine_type: str) -> List[Template]:
        """Find templates for specific machine type."""
        return self.find_by_criteria({"vm_type": machine_type})