# src/domain/template/template_service.py
from typing import List, Optional, Dict, Any
from src.domain.template.template_aggregate import Template
from src.domain.template.value_objects import TemplateId, AWSHandlerType, TemplateAttributes, AWSConfiguration
from src.domain.template.exceptions import TemplateNotFoundError, TemplateValidationError
from src.domain.core.events import EventPublisher

class TemplateService:
    """Domain service for template operations."""
    
    def __init__(self, template_repository, event_publisher: Optional[EventPublisher] = None):
        self._repository = template_repository
        self._event_publisher = event_publisher

    def get_template(self, template_id: TemplateId) -> Template:
        """Get a template by ID with validation."""
        template = self._repository.find_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(str(template_id))
        return template

    def validate_template_request(self, template: Template, num_machines: int) -> None:
        """Domain validation for template requests."""
        errors: Dict[str, str] = {}

        # Validate machine count
        if num_machines <= 0:
            errors["num_machines"] = "Must be greater than zero"
        if num_machines > template.max_number:
            errors["num_machines"] = f"Exceeds template maximum of {template.max_number}"

        # Validate AWS handler type
        try:
            AWSHandlerType.validate(template.aws_handler)
        except ValidationError as e:
            errors["aws_handler"] = str(e)

        # Validate Spot Fleet specific requirements
        if template.aws_handler in ['SpotFleet', 'SpotFleetRequest']:
            if not template.fleet_role:
                errors["fleet_role"] = "Fleet role is required for Spot Fleet templates"
            if template.max_spot_price is not None and template.max_spot_price <= 0:
                errors["max_spot_price"] = "Must be greater than zero"

        if errors:
            raise TemplateValidationError(str(template.template_id), errors)

    def create_template(self, template_data: Dict[str, Any]) -> Template:
        """Create a new template with validation."""
        # Validate template ID format
        template_id = TemplateId(template_data["templateId"])

        # Check for existing template
        if self._repository.exists(template_id):
            raise TemplateValidationError(
                str(template_id),
                {"templateId": "Template ID already exists"}
            )

        # Create and validate template
        template = Template.from_dict(template_data)
        template.validate()

        # Save template
        self._repository.save(template)

        # Publish event if available
        if self._event_publisher:
            self._event_publisher.publish_template_created(template)

        return template

    def update_template(self, template_id: TemplateId, template_data: Dict[str, Any]) -> Template:
        """Update an existing template with validation."""
        # Check existing template
        existing_template = self.get_template(template_id)

        # Create new template instance
        updated_template = Template.from_dict({
            **existing_template.to_dict(),
            **template_data,
            "templateId": str(template_id)  # Ensure ID doesn't change
        })

        # Validate template
        updated_template.validate()

        # Save template
        self._repository.save(updated_template)

        # Publish event if available
        if self._event_publisher:
            self._event_publisher.publish_template_updated(
                template_id=template_id,
                old_template=existing_template,
                new_template=updated_template
            )

        return updated_template

    def delete_template(self, template_id: TemplateId) -> None:
        """Delete a template."""
        template = self.get_template(template_id)
        self._repository.delete(template_id)

        # Publish event if available
        if self._event_publisher:
            self._event_publisher.publish_template_deleted(template)

    def get_templates_by_handler(self, handler_type: str) -> List[Template]:
        """Get templates for a specific AWS handler type."""
        AWSHandlerType.validate(handler_type)
        return self._repository.find_by_handler_type(handler_type)

    def validate_aws_configuration(self, config: AWSConfiguration) -> None:
        """Validate AWS-specific configuration."""
        try:
            if config.vm_types:
                total_weight = sum(config.vm_types.values())
                if total_weight <= 0:
                    raise ValidationError("Total instance weights must be greater than zero")

            if config.subnet_ids and len(config.subnet_ids) > 10:
                raise ValidationError("Maximum of 10 subnets allowed")

            if config.instance_tags and len(config.instance_tags) > 50:
                raise ValidationError("Maximum of 50 tags allowed")

        except Exception as e:
            raise TemplateValidationError("AWS Configuration", {"validation": str(e)})