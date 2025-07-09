"""Template command handlers for CQRS pattern."""

from typing import Optional
from src.application.interfaces.command_handler import CommandHandler
from src.application.template.commands import (
    CreateTemplateCommand,
    UpdateTemplateCommand,
    DeleteTemplateCommand,
    ValidateTemplateCommand,
    TemplateCommandResponse
)
from src.domain.template.aggregate import Template
from src.domain.base.exceptions import EntityNotFoundError, BusinessRuleError
from src.domain.base.ports import LoggingPort, ContainerPort
from src.domain.base import UnitOfWorkFactory
from src.domain.base.dependency_injection import injectable


@injectable
class CreateTemplateHandler(CommandHandler[CreateTemplateCommand, TemplateCommandResponse]):
    """
    Handler for creating templates.
    
    Responsibilities:
    - Validate template configuration
    - Create template aggregate
    - Persist template through repository
    - Publish TemplateCreated domain event
    """
    
    def __init__(self, 
                 uow_factory: UnitOfWorkFactory,
                 logger: LoggingPort,
                 container: ContainerPort) -> None:
        self._uow_factory = uow_factory
        self._logger = logger
        self._container = container
    
    
    def handle(self, command: CreateTemplateCommand) -> TemplateCommandResponse:
        """Create new template with validation and events."""
        self._logger.info(f"Creating template: {command.template_id}")
        
        # Get template configuration port for validation
        from src.domain.base.ports.template_configuration_port import TemplateConfigurationPort
        template_port = self._container.get(TemplateConfigurationPort)
        
        # Validate template configuration
        validation_errors = template_port.validate_template_config(command.configuration)
        if validation_errors:
            self._logger.warning(f"Template validation failed for {command.template_id}: {validation_errors}")
            return TemplateCommandResponse(
                template_id=command.template_id,
                validation_errors=validation_errors
            )
        
        # Create template aggregate
        try:
            template = Template.create(
                template_id=command.template_id,
                name=command.name or command.template_id,
                description=command.description,
                provider_api=command.provider_api,
                instance_type=command.instance_type,
                image_id=command.image_id,
                subnet_ids=command.subnet_ids,
                security_group_ids=command.security_group_ids,
                tags=command.tags,
                configuration=command.configuration
            )
        except Exception as e:
            self._logger.error(f"Failed to create template aggregate: {e}")
            raise BusinessRuleError(f"Template creation failed: {str(e)}")
        
        # Persist template through repository
        with self._uow_factory.create_unit_of_work() as uow:
            try:
                # Check if template already exists
                existing_template = uow.templates.get_by_id(command.template_id)
                if existing_template:
                    raise BusinessRuleError(f"Template {command.template_id} already exists")
                
                # Add new template
                uow.templates.add(template)
                uow.commit()
                
                self._logger.info(f"Template created successfully: {command.template_id}")
                
                # Template aggregate will publish TemplateCreated event through repository
                
            except Exception as e:
                self._logger.error(f"Failed to persist template {command.template_id}: {e}")
                raise
        
        return TemplateCommandResponse(template_id=command.template_id)
    
    def _determine_provider_type(self, template_dto) -> Optional[str]:
        """Determine provider type from template DTO."""
        provider_api = template_dto.provider_api
        if provider_api:
            if provider_api in ['EC2Fleet', 'SpotFleet', 'RunInstances', 'AutoScalingGroup']:
                return 'aws'
        
        config = template_dto.configuration
        if config and ('aws' in config or any(key.startswith('aws_') for key in config.keys())):
            return 'aws'
        
        return None


@injectable
class UpdateTemplateHandler(CommandHandler[UpdateTemplateCommand, TemplateCommandResponse]):
    """
    Handler for updating templates.
    
    Responsibilities:
    - Validate template exists
    - Validate updated configuration
    - Update template aggregate
    - Persist changes through repository
    - Publish TemplateUpdated domain event
    """
    
    def __init__(self, 
                 uow_factory: UnitOfWorkFactory,
                 logger: LoggingPort,
                 container: ContainerPort) -> None:
        self._uow_factory = uow_factory
        self._logger = logger
        self._container = container
    
    
    def handle(self, command: UpdateTemplateCommand) -> TemplateCommandResponse:
        """Update existing template with validation and events."""
        self._logger.info(f"Updating template: {command.template_id}")
        
        # Get template configuration port for validation
        from src.domain.base.ports.template_configuration_port import TemplateConfigurationPort
        template_port = self._container.get(TemplateConfigurationPort)
        
        # Validate updated configuration if provided
        validation_errors = []
        if command.configuration:
            validation_errors = template_port.validate_template_config(command.configuration)
            if validation_errors:
                self._logger.warning(f"Template update validation failed for {command.template_id}: {validation_errors}")
                return TemplateCommandResponse(
                    template_id=command.template_id,
                    validation_errors=validation_errors
                )
        
        # Update template through repository
        with self._uow_factory.create_unit_of_work() as uow:
            try:
                # Get existing template
                template = uow.templates.get_by_id(command.template_id)
                if not template:
                    raise EntityNotFoundError("Template", command.template_id)
                
                # Track changes for event
                changes = {}
                
                # Update template properties
                if command.name is not None:
                    template.update_name(command.name)
                    changes['name'] = command.name
                
                if command.description is not None:
                    template.update_description(command.description)
                    changes['description'] = command.description
                
                if command.configuration:
                    template.update_configuration(command.configuration)
                    changes['configuration'] = command.configuration
                
                # Save changes
                uow.templates.update(template)
                uow.commit()
                
                self._logger.info(f"Template updated successfully: {command.template_id}")
                
                # Template aggregate will publish TemplateUpdated event through repository
                
            except EntityNotFoundError:
                self._logger.error(f"Template not found for update: {command.template_id}")
                raise
            except Exception as e:
                self._logger.error(f"Failed to update template {command.template_id}: {e}")
                raise
        
        return TemplateCommandResponse(template_id=command.template_id)


@injectable
class DeleteTemplateHandler(CommandHandler[DeleteTemplateCommand, TemplateCommandResponse]):
    """
    Handler for deleting templates.
    
    Responsibilities:
    - Validate template exists
    - Check if template is in use
    - Delete template through repository
    - Publish TemplateDeleted domain event
    """
    
    def __init__(self, 
                 uow_factory: UnitOfWorkFactory,
                 logger: LoggingPort,
                 container: ContainerPort) -> None:
        self._uow_factory = uow_factory
        self._logger = logger
        self._container = container
    
    
    def handle(self, command: DeleteTemplateCommand) -> TemplateCommandResponse:
        """Delete template with validation and events."""
        self._logger.info(f"Deleting template: {command.template_id}")
        
        # Delete template through repository
        with self._uow_factory.create_unit_of_work() as uow:
            try:
                # Get existing template
                template = uow.templates.get_by_id(command.template_id)
                if not template:
                    raise EntityNotFoundError("Template", command.template_id)
                
                # Check if template is in use (business rule)
                # This could be expanded to check for active requests using this template
                if template.is_in_use():
                    raise BusinessRuleError(f"Cannot delete template {command.template_id}: template is in use")
                
                # Delete template
                uow.templates.remove(template)
                uow.commit()
                
                self._logger.info(f"Template deleted successfully: {command.template_id}")
                
                # Template aggregate will publish TemplateDeleted event through repository
                
            except EntityNotFoundError:
                self._logger.error(f"Template not found for deletion: {command.template_id}")
                raise
            except BusinessRuleError:
                self._logger.error(f"Cannot delete template {command.template_id}: business rule violation")
                raise
            except Exception as e:
                self._logger.error(f"Failed to delete template {command.template_id}: {e}")
                raise
        
        return TemplateCommandResponse(template_id=command.template_id)


@injectable
class ValidateTemplateCommandHandler(CommandHandler[ValidateTemplateCommand, TemplateCommandResponse]):
    """
    Handler for validating template configurations.
    
    Responsibilities:
    - Validate template configuration against schema
    - Validate provider-specific rules
    - Return detailed validation results
    - Publish TemplateValidated domain event
    """
    
    def __init__(self, 
                 logger: LoggingPort,
                 container: ContainerPort) -> None:
        self._logger = logger
        self._container = container
    
    
    def handle(self, command: ValidateTemplateCommand) -> TemplateCommandResponse:
        """Validate template configuration with detailed results."""
        self._logger.info(f"Validating template configuration: {command.template_id}")
        
        # Get template configuration port for validation
        from src.domain.base.ports.template_configuration_port import TemplateConfigurationPort
        template_port = self._container.get(TemplateConfigurationPort)
        
        try:
            # Validate template configuration
            validation_errors = template_port.validate_template_config(command.configuration)
            
            # Log validation results
            if validation_errors:
                self._logger.warning(f"Template validation failed for {command.template_id}: {validation_errors}")
            else:
                self._logger.info(f"Template validation passed for {command.template_id}")
            
            # Publish validation event (could be useful for monitoring/auditing)
            # This would be handled by the domain event system
            
            return TemplateCommandResponse(
                template_id=command.template_id,
                validation_errors=validation_errors
            )
            
        except Exception as e:
            self._logger.error(f"Template validation failed for {command.template_id}: {e}")
            return TemplateCommandResponse(
                template_id=command.template_id,
                validation_errors=[f"Validation error: {str(e)}"]
            )
