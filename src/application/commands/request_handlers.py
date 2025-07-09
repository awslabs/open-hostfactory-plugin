"""Command handlers for request operations."""
from src.application.interfaces.command_handler import CommandHandler
from src.application.dto.commands import (
    CreateRequestCommand,
    CreateReturnRequestCommand,
    UpdateRequestStatusCommand,
    CancelRequestCommand,
    CompleteRequestCommand
)
from src.domain.request.repository import RequestRepository
from src.domain.machine.repository import MachineRepository
from src.domain.base.exceptions import EntityNotFoundError  # Add this import
from src.domain.base.ports import EventPublisherPort, LoggingPort, ContainerPort

# Exception handling infrastructure
from src.domain.base.dependency_injection import injectable


@injectable
class CreateMachineRequestHandler(CommandHandler):
    """Handler for creating machine requests."""
    
    def __init__(self, 
                 request_repository: RequestRepository,
                 machine_repository: MachineRepository,
                 template_repository,  # Keep for now, will remove in Phase 4
                 event_publisher: EventPublisherPort,
                 logger: LoggingPort,
                 container: ContainerPort,
                 query_bus=None):  # Add QueryBus for template lookup
        self._request_repository = request_repository
        self._machine_repository = machine_repository
        self._template_repository = template_repository
        self._event_publisher = event_publisher
        self._logger = logger
        self._container = container
        self._query_bus = query_bus
    
    
    def handle(self, command: CreateRequestCommand) -> str:
        """Handle machine request creation command."""
        # Create request aggregate
        from src.domain.request.aggregate import Request
        from src.domain.request.value_objects import RequestType
        
        # Get provider type from configuration using injected container
        from src.config.manager import ConfigurationManager
        config_manager = self._container.get(ConfigurationManager)
        provider_type = config_manager.get("provider.type", "aws")
        
        request = Request.create_new_request(
            request_type=RequestType.ACQUIRE,
            template_id=command.template_id,
            machine_count=command.machine_count,
            provider_type=provider_type,
            metadata={
                **command.metadata,
                'dry_run': command.dry_run  # Pass dry-run context through metadata
            }
        )
        
        # ADD: Actual AWS Provisioning
        try:
            # Get template using CQRS QueryBus (proper architecture)
            if self._query_bus:
                from src.application.dto.queries import GetTemplateQuery
                template_query = GetTemplateQuery(template_id=command.template_id)
                template_dto = self._query_bus.dispatch(template_query)
                # Convert DTO back to domain object for provisioning
                from src.domain.template.aggregate import Template
                template = Template(**template_dto.model_dump())
            else:
                # Fallback to direct repository access (deprecated - Phase 4 cleanup)
                template = self._template_repository.find_by_template_id(command.template_id)
                if not template:
                    raise EntityNotFoundError("Template", command.template_id)
            
            # Get AWS provisioning service from injected DI container
            # Get provisioning port
            from src.infrastructure.ports.resource_provisioning_port import ResourceProvisioningPort
            provisioning_service = self._container.get(ResourceProvisioningPort)
            
            # Actually provision AWS resources with correct interface
            self._logger.info(f"Provisioning AWS resources for request {request.request_id}")
            provisioning_result = provisioning_service.provision_resources(
                request=request,    # Pass Request aggregate
                template=template   # Pass Template aggregate
            )
            
            # Update request with provisioning results
            request.update_with_provisioning_result(provisioning_result)
            self._logger.info(f"AWS provisioning successful for request {request.request_id}")
            
        except Exception as provisioning_error:
            # Update request status to failed
            from src.domain.request.value_objects import RequestStatus
            request.update_status(
                RequestStatus.FAILED, 
                f"AWS provisioning failed: {str(provisioning_error)}"
            )
            self._logger.error(f"AWS provisioning failed for request {request.request_id}: {provisioning_error}")
        
        # Save request and get extracted events
        events = self._request_repository.save(request)
        
        # Publish events
        for event in events:
            self._event_publisher.publish(event)
        
        self._logger.info(f"Machine request created: {request.request_id}")
        return str(request.request_id)


@injectable
class CreateReturnRequestHandler(CommandHandler):
    """Handler for creating return requests."""
    
    def __init__(self, 
                 request_repository: RequestRepository,
                 machine_repository: MachineRepository,
                 template_repository,  # Add template repository
                 event_publisher: EventPublisherPort,
                 logger: LoggingPort,
                 container: ContainerPort):
        self._request_repository = request_repository
        self._machine_repository = machine_repository
        self._template_repository = template_repository
        self._event_publisher = event_publisher
        self._logger = logger
        self._container = container
    
    
    def handle(self, command: CreateReturnRequestCommand) -> str:
        """Handle return request creation command."""
        # Create return request aggregate
        from src.domain.request.aggregate import Request
        from src.domain.request.value_objects import RequestType
        # Get provider type from configuration using injected container
        from src.config.manager import ConfigurationManager
        config_manager = self._container.get(ConfigurationManager)
        provider_type = config_manager.get("provider.type", "aws")
        
        # Create return request with proper business logic
        # Use first machine's template if available, otherwise use generic return template
        template_id = "return-machines"  # Business template for return operations
        if command.machine_ids:
            # Try to get template from first machine
            try:
                machine = self._machine_repository.find_by_id(command.machine_ids[0])
                if machine and machine.template_id:
                    template_id = f"return-{machine.template_id}"
            except Exception as e:
                # Fallback to generic return template
                self._logger.warning(
                    f"Failed to determine return template ID from machine: {e}",
                    extra={"machine_ids": command.machine_ids, "request_id": command.request_id}
                )
        
        request = Request.create_new_request(
            request_type=RequestType.RETURN,
            template_id=template_id,
            machine_count=len(command.machine_ids),
            provider_type=provider_type,
            metadata=command.metadata or {}
        )
        
        # Save request
        # Save and get extracted events

        events = self._request_repository.save(request)
        # Publish events
        for event in events:
            self._event_publisher.publish(event)
        
        self._logger.info(f"Return request created: {request.request_id}")
        return str(request.request_id)


@injectable
class UpdateRequestStatusHandler(CommandHandler):
    """Handler for updating request status."""
    
    def __init__(self, request_repository: RequestRepository, event_publisher: EventPublisherPort, logger: LoggingPort):
        self._request_repository = request_repository
        self._event_publisher = event_publisher
        self._logger = logger
    
    def handle(self, command: UpdateRequestStatusCommand) -> None:
        """Handle request status update command."""
    
    def handle(self, command: UpdateRequestStatusCommand) -> None:
        """Handle request status update command."""
        # Get request
        request = self._request_repository.get_by_id(command.request_id)
        if not request:
            raise ValueError(f"Request not found: {command.request_id}")
        
        # Update status
        request.update_status(
            status=command.status,
            status_message=command.status_message,
            metadata=command.metadata
        )
        
        # Save changes
        # Save and get extracted events

        events = self._request_repository.save(request)
        # Publish events
        for event in events:
            self._event_publisher.publish(event)
        
        self._logger.info(f"Request status updated: {command.request_id} -> {command.status}")


@injectable
class CancelRequestHandler(CommandHandler):
    """Handler for canceling requests."""
    
    def __init__(self, request_repository: RequestRepository, event_publisher: EventPublisherPort, logger: LoggingPort):
        self._request_repository = request_repository
        self._event_publisher = event_publisher
        self._logger = logger
    
    def handle(self, command: CancelRequestCommand) -> None:
        """Handle request cancellation command."""
    
    def handle(self, command: CancelRequestCommand) -> None:
        """Handle request cancellation command."""
        # Get request
        request = self._request_repository.get_by_id(command.request_id)
        if not request:
            raise ValueError(f"Request not found: {command.request_id}")
        
        # Cancel request
        request.cancel(reason=command.reason, metadata=command.metadata)
        
        # Save changes
        # Save and get extracted events

        events = self._request_repository.save(request)
        # Publish events
        for event in events:
            self._event_publisher.publish(event)
        
        self._logger.info(f"Request canceled: {command.request_id}")


@injectable
class CompleteRequestHandler(CommandHandler):
    """Handler for completing requests."""
    
    def __init__(self, request_repository: RequestRepository, event_publisher: EventPublisherPort, logger: LoggingPort):
        self._request_repository = request_repository
        self._event_publisher = event_publisher
        self._logger = logger
    
    def handle(self, command: CompleteRequestCommand) -> None:
        """Handle request completion command."""
    
    def handle(self, command: CompleteRequestCommand) -> None:
        """Handle request completion command."""
        # Get request
        request = self._request_repository.get_by_id(command.request_id)
        if not request:
            raise ValueError(f"Request not found: {command.request_id}")
        
        # Complete request
        request.complete(result_data=command.result_data, metadata=command.metadata)
        
        # Save changes
        # Save and get extracted events

        events = self._request_repository.save(request)
        # Publish events
        for event in events:
            self._event_publisher.publish(event)
        
        self._logger.info(f"Request completed: {command.request_id}")
