"""Template loader for loading templates from various sources."""
import os
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from .dtos import TemplateDTO
from .mappers import TemplateMapper
from src.infrastructure.template.format_converter import TemplateFormatConverter
from src.infrastructure.logging.logger import get_logger


class TemplateLoader:
    """Loads templates from files with format conversion support."""
    
    def __init__(self, legacy_path: str, new_path: Optional[str] = None):
        """
        Initialize template loader.
        
        Args:
            legacy_path: Path to legacy templates file (awsprov_templates.json)
            new_path: Optional path to new templates file (templates.json)
        """
        self.legacy_path = legacy_path
        self.new_path = new_path
        self.format_converter = TemplateFormatConverter()
        self.logger = get_logger(__name__)
        
        # Log which files are available
        self._log_available_files()
    
    def load_all(self) -> List[TemplateDTO]:
        """
        Load templates from all available sources.
        
        Returns:
            List of Template objects
            
        Raises:
            Exception: If no template files are found or loading fails
        """
        templates = []
        
        # Load from legacy file first
        legacy_templates = self._load_from_legacy_file()
        if legacy_templates:
            templates.extend(legacy_templates)
            self.logger.info(f"Loaded {len(legacy_templates)} templates from legacy file")
        
        # Load from new file if it exists
        if self.new_path and os.path.exists(self.new_path):
            new_templates = self._load_from_new_file()
            if new_templates:
                # Merge with legacy templates (new file takes precedence)
                templates = self._merge_templates(templates, new_templates)
                self.logger.info(f"Merged with {len(new_templates)} templates from new file")
        
        if not templates:
            raise Exception(f"No templates found in {self.legacy_path} or {self.new_path}")
        
        self.logger.info(f"Total templates loaded: {len(templates)}")
        return templates
    
    def _load_from_legacy_file(self) -> List[TemplateDTO]:
        """
        Load templates from legacy format file.
        
        Returns:
            List of Template objects from legacy file
        """
        if not os.path.exists(self.legacy_path):
            self.logger.warning(f"Legacy templates file not found: {self.legacy_path}")
            return []
        
        try:
            with open(self.legacy_path, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, dict) or 'templates' not in data:
                self.logger.error(f"Invalid legacy template file format: {self.legacy_path}")
                return []
            
            legacy_templates = data['templates']
            if not isinstance(legacy_templates, list):
                self.logger.error(f"Templates should be a list in: {self.legacy_path}")
                return []
            
            # Convert legacy format to new format
            converted_templates = []
            for template_data in legacy_templates:
                try:
                    # Convert format
                    new_format_data = self.format_converter.convert_legacy_to_new(template_data)
                    
                    # Validate conversion
                    if not self.format_converter.validate_conversion(template_data, new_format_data):
                        self.logger.error(f"Failed to validate conversion for template: {template_data.get('templateId', 'unknown')}")
                        continue
                    
                    # Add timestamps if missing
                    self._add_default_timestamps(new_format_data)
                    
                    # Create Template object
                    template = self._create_template_from_data(new_format_data)
                    if template:
                        converted_templates.append(template)
                    
                except Exception as e:
                    template_id = template_data.get('templateId', 'unknown')
                    self.logger.error(f"Failed to convert legacy template {template_id}: {e}")
                        
            return converted_templates
            
        except Exception as e:
            self.logger.error(f"Failed to load legacy templates from {self.legacy_path}: {e}")
            return []
    
    def _load_from_new_file(self) -> List[TemplateDTO]:
        """
        Load templates from new format file.
        
        Returns:
            List of Template objects from new file
        """
        if not self.new_path or not os.path.exists(self.new_path):
            return []
        
        try:
            with open(self.new_path, 'r') as f:
                data = json.load(f)
            
            templates = []
            
            # Handle different file formats
            if isinstance(data, dict):
                if 'templates' in data and isinstance(data['templates'], list):
                    # Format: {"templates": [...]}
                    template_list = data['templates']
                else:
                    # Format: {"template_id": {...}, ...}
                    template_list = list(data.values())
            elif isinstance(data, list):
                # Format: [...]
                template_list = data
            else:
                self.logger.error(f"Invalid new template file format: {self.new_path}")
                return []
            
            for template_data in template_list:
                try:
                    # Add timestamps if missing
                    self._add_default_timestamps(template_data)
                    
                    # Create Template object
                    template = self._create_template_from_data(template_data)
                    if template:
                        templates.append(template)
                        
                except Exception as e:
                    template_id = template_data.get('template_id', 'unknown')
                    self.logger.error(f"Failed to create template {template_id}: {e}")
            
            return templates
            
        except Exception as e:
            self.logger.error(f"Failed to load new templates from {self.new_path}: {e}")
            return []
    
    def _create_template_from_data(self, template_data: Dict[str, Any]) -> Optional[TemplateDTO]:
        """
        Create TemplateDTO object from template data.
        
        Args:
            template_data: Template data dictionary
            
        Returns:
            TemplateDTO object or None if creation fails
        """
        try:
            # Ensure required fields are present
            if not template_data.get('template_id'):
                self.logger.error(f"Template missing template_id: {template_data}")
                return None
            
            # Create TemplateDTO directly
            template = TemplateDTO(
                template_id=template_data.get('template_id'),
                name=template_data.get('name', template_data.get('template_id')),
                provider_api=template_data.get('provider_api', 'aws'),
                configuration=template_data
            )
            return template
            
        except Exception as e:
            template_id = template_data.get('template_id', 'unknown')
            self.logger.error(f"Failed to create TemplateDTO object for {template_id}: {e}")
            return None
    
    def _merge_templates(self, legacy_templates: List[TemplateDTO], new_templates: List[TemplateDTO]) -> List[TemplateDTO]:
        """
        Merge legacy and new templates, with new templates taking precedence.
        
        Args:
            legacy_templates: Templates from legacy file
            new_templates: Templates from new file
            
        Returns:
            Merged list of templates
        """
        # Create lookup for new templates by ID
        new_template_ids = {t.template_id for t in new_templates}
        
        # Start with new templates
        merged = list(new_templates)
        
        # Add legacy templates that don't exist in new templates
        for legacy_template in legacy_templates:
            if legacy_template.template_id not in new_template_ids:
                merged.append(legacy_template)
        
        return merged
    
    def _add_default_timestamps(self, template_data: Dict[str, Any]) -> None:
        """
        Add default timestamps to template data if missing.
        
        Args:
            template_data: Template data dictionary to modify
        """
        now = datetime.now()
        
        if 'created_at' not in template_data:
            template_data['created_at'] = now
        
        if 'updated_at' not in template_data:
            template_data['updated_at'] = now
    
    def _log_available_files(self) -> None:
        """Log information about available template files."""
        legacy_exists = os.path.exists(self.legacy_path)
        new_exists = self.new_path and os.path.exists(self.new_path)
        
        if legacy_exists and new_exists:
            self.logger.info(f"Found both template files - will merge contents")
            self.logger.debug(f"Legacy file: {self.legacy_path}")
            self.logger.debug(f"New file: {self.new_path}")
        elif legacy_exists:
            self.logger.info(f"Found legacy templates file: {self.legacy_path}")
        elif new_exists:
            self.logger.info(f"Found new templates file: {self.new_path}")
        else:
            self.logger.warning(f"No template files found at {self.legacy_path} or {self.new_path}")
    
    def reload(self) -> None:
        """
        Reload templates from files.
        
        This method can be called to refresh templates without recreating the loader.
        """
        self.logger.info("Reloading templates from files")
        self._log_available_files()
    
    def get_file_info(self) -> Dict[str, Any]:
        """
        Get information about template files.
        
        Returns:
            Dictionary with file information
        """
        info = {
            'legacy_path': self.legacy_path,
            'legacy_exists': os.path.exists(self.legacy_path),
            'new_path': self.new_path,
            'new_exists': self.new_path and os.path.exists(self.new_path)
        }
        
        # Add file modification times
        if info['legacy_exists']:
            info['legacy_mtime'] = os.path.getmtime(self.legacy_path)
        
        if info['new_exists']:
            info['new_mtime'] = os.path.getmtime(self.new_path)
        
        return info
