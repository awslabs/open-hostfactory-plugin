"""Query handlers for application services."""
from __future__ import annotations
from typing import List, Dict, Any, TypeVar

from src.application.base.handlers import BaseQueryHandler
from src.application.interfaces.command_query import QueryHandler
from src.domain.base.ports import LoggingPort, ErrorHandlingPort, ContainerPort
from src.application.dto.queries import (
    GetRequestQuery,
    GetRequestStatusQuery,
    ListActiveRequestsQuery,
    ListReturnRequestsQuery,
    GetTemplateQuery,
    ListTemplatesQuery,
    ValidateTemplateQuery,
    GetMachineQuery,
    ListMachinesQuery
)
from src.application.dto.responses import (
    RequestDTO,
    MachineDTO,
    TemplateDTO
)

# Exception handling through BaseQueryHandler (Clean Architecture compliant)
from src.domain.base.dependency_injection import injectable
from src.domain.base.exceptions import EntityNotFoundError
from src.domain.base import UnitOfWorkFactory
from src.application.decorators import query_handler

T = TypeVar('T')

# Query handlers
@query_handler(GetRequestQuery)
class GetRequestHandler(BaseQueryHandler[GetRequestQuery, RequestDTO]):
    """Handler for getting request details using enhanced base handler."""

    def __init__(self, 
                 uow_factory: UnitOfWorkFactory, 
                 logger: LoggingPort,
                 error_handler: ErrorHandlingPort,
                 container: ContainerPort) -> None:
        super().__init__(logger, error_handler)
        self.uow_factory = uow_factory
        self._container = container

    def handle(self, query: GetRequestQuery) -> RequestDTO:
        """Handle get request query - error handling via base handler."""
        # Validate request_id is not None
        if query.request_id is None:
            raise ValueError("Request ID cannot be None. This typically happens when a request fails to be created properly.")
            
        # Get unit of work from factory
        uow = self.uow_factory.create_unit_of_work()
        
        with uow:
            # Convert string to RequestId value object
            from src.domain.request.value_objects import RequestId
            request_id = RequestId(value=query.request_id)
            request = uow.requests.find_by_id(request_id)
            if not request:
                raise EntityNotFoundError("Request", query.request_id)

            # Create DTO from domain object with long parameter
            request_dto = RequestDTO.from_domain(request, long=query.long)
            
            return request_dto

@query_handler(GetRequestStatusQuery)
class GetRequestStatusQueryHandler(QueryHandler[GetRequestStatusQuery, str]):
    """Handler for getting request status."""

    def __init__(self, 
                 uow_factory: UnitOfWorkFactory, 
                 logger: LoggingPort,
                 container: ContainerPort) -> None:
        self.uow_factory = uow_factory
        self._logger = logger
        self._container = container

    
    def handle(self, query: GetRequestStatusQuery) -> str:
        """Handle get request status query."""
        # Validate request_id is not None
        if query.request_id is None:
            raise ValueError("Request ID cannot be None. This typically happens when a request fails to be created properly.")
            
        # Get unit of work from factory
        uow = self.uow_factory.create_unit_of_work()
        
        with uow:
            # Convert string to RequestId value object
            from src.domain.request.value_objects import RequestId
            request_id = RequestId(value=query.request_id)
            request = uow.requests.find_by_id(request_id)
            if not request:
                raise EntityNotFoundError("Request", query.request_id)
            return request.status.value

@query_handler(ListActiveRequestsQuery)
class ListActiveRequestsHandler(QueryHandler[ListActiveRequestsQuery, List[RequestDTO]]):
    """Handler for listing active requests."""

    def __init__(self, uow_factory: UnitOfWorkFactory, logger: LoggingPort, container: ContainerPort) -> None:
        self._logger = logger
        self._container = container
        self.uow_factory = uow_factory

    
    def handle(self, query: ListActiveRequestsQuery) -> List[RequestDTO]:
        """Handle list active requests query."""
        # Get unit of work from factory
        uow = self.uow_factory.create_unit_of_work()
        
        with uow:
            requests = uow.requests.find_active_requests()
            # Create DTOs with long flag set to True for active requests
            dtos = [RequestDTO.from_domain(r, long=True) for r in requests]
            return dtos

@query_handler(ListReturnRequestsQuery)
class ListReturnRequestsHandler(QueryHandler[ListReturnRequestsQuery, List[RequestDTO]]):
    """Handler for listing return requests."""

    def __init__(self, uow_factory: UnitOfWorkFactory, logger: LoggingPort, container: ContainerPort) -> None:
        self._logger = logger
        self._container = container
        self.uow_factory = uow_factory

    
    def handle(self, query: ListReturnRequestsQuery) -> List[RequestDTO]:
        """Handle list return requests query."""
        # Get unit of work from factory
        uow = self.uow_factory.create_unit_of_work()
        
        with uow:
            requests = uow.requests.find_return_requests()
            # Create DTOs with long flag set to True for return requests
            dtos = [RequestDTO.from_domain(r, long=True) for r in requests]
            return dtos

@query_handler(GetTemplateQuery)
class GetTemplateHandler(QueryHandler[GetTemplateQuery, TemplateDTO]):
    """Handler for getting template details."""

    def __init__(self, uow_factory: UnitOfWorkFactory, logger: LoggingPort, container: ContainerPort) -> None:
        self._logger = logger
        self._container = container
        self.uow_factory = uow_factory

    
    def handle(self, query: GetTemplateQuery) -> TemplateDTO:
        """Handle get template query."""
        # Use new unified configuration store with sync wrapper
        from src.infrastructure.template.sync_configuration_store import SyncTemplateConfigurationStore
        from src.infrastructure.template.configuration_store import TemplateConfigurationStore
        
        async_store = self._container.get(TemplateConfigurationStore)
        sync_store = SyncTemplateConfigurationStore(async_store, self._logger)
        
        template = sync_store.get_template_by_id(query.template_id)
        if not template:
            raise EntityNotFoundError("Template", query.template_id)

        return template  # TemplateDTO is already returned from store

@query_handler(ListTemplatesQuery)
class ListTemplatesHandler(QueryHandler[ListTemplatesQuery, List[TemplateDTO]]):
    """Handler for listing templates."""

    def __init__(self, uow_factory: UnitOfWorkFactory, logger: LoggingPort, container: ContainerPort) -> None:
        self._logger = logger
        self._container = container
        self.uow_factory = uow_factory

    
    def handle(self, query: ListTemplatesQuery) -> List[TemplateDTO]:
        """Handle list templates query."""
        # Use new unified configuration store with sync wrapper
        from src.infrastructure.template.sync_configuration_store import SyncTemplateConfigurationStore
        from src.infrastructure.template.configuration_store import TemplateConfigurationStore
        from src.application.template.mappers import TemplateDTOMapper
        
        async_store = self._container.get(TemplateConfigurationStore)
        sync_store = SyncTemplateConfigurationStore(async_store, self._logger)
        
        if query.provider_api:
            infra_templates = sync_store.get_templates_by_provider(query.provider_api)
        else:
            infra_templates = sync_store.get_templates()

        self._logger.debug(f"Found {len(infra_templates)} templates from infrastructure")
        
        # Convert infrastructure DTOs to application DTOs
        app_templates = TemplateDTOMapper.infrastructure_list_to_application(infra_templates)
        
        self._logger.debug(f"Converted to {len(app_templates)} application DTOs")
        return app_templates

@query_handler(ValidateTemplateQuery)
class ValidateTemplateHandler(QueryHandler[ValidateTemplateQuery, Dict[str, Any]]):
    """Handler for validating template configuration."""

    def __init__(self, uow_factory: UnitOfWorkFactory, logger: LoggingPort, container: ContainerPort) -> None:
        self._logger = logger
        self._container = container
        self.uow_factory = uow_factory

    
    def handle(self, query: ValidateTemplateQuery) -> Dict[str, Any]:
        """Handle validate template query."""
        try:
            # Basic validation logic - can be enhanced
            config = query.template_config
            
            # Check required fields
            required_fields = ['template_id', 'instance_type', 'image_id']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                return {
                    'valid': False,
                    'errors': [f'Missing required field: {field}' for field in missing_fields]
                }
            
            # Additional validation can be added here
            return {
                'valid': True,
                'message': 'Template configuration is valid'
            }
            
        except Exception as e:
            self.logger.error(f"Error validating template: {e}")
            return {
                'valid': False,
                'errors': [f'Validation error: {str(e)}']
            }

@query_handler(GetMachineQuery)
class GetMachineHandler(QueryHandler[GetMachineQuery, MachineDTO]):
    """Handler for getting machine details."""

    def __init__(self, uow_factory: UnitOfWorkFactory, logger: LoggingPort, container: ContainerPort) -> None:
        self._logger = logger
        self._container = container
        self.uow_factory = uow_factory

    
    def handle(self, query: GetMachineQuery) -> MachineDTO:
        """Handle get machine query."""
        # Get unit of work from factory
        uow = self.uow_factory.create_unit_of_work()
        
        with uow:
            machine = uow.machines.find_by_id(query.machine_id)
            if not machine:
                raise EntityNotFoundError("Machine", query.machine_id)

            return MachineDTO.from_domain(machine)

@query_handler(ListMachinesQuery)
class ListMachinesHandler(QueryHandler[ListMachinesQuery, List[MachineDTO]]):
    """Handler for listing machines."""

    def __init__(self, uow_factory: UnitOfWorkFactory, logger: LoggingPort, container: ContainerPort) -> None:
        self._logger = logger
        self._container = container
        self.uow_factory = uow_factory

    
    def handle(self, query: ListMachinesQuery) -> List[MachineDTO]:
        """Handle list machines query."""
        # Get unit of work from factory
        uow = self.uow_factory.create_unit_of_work()
        
        with uow:
            if query.active_only:
                machines = uow.machines.find_active_machines()
            elif query.request_id:
                machines = uow.machines.find_by_request_id(query.request_id)
            else:
                machines = uow.machines.find_all()

            return [MachineDTO.from_domain(m) for m in machines]
