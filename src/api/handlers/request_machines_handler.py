"""Enhanced API handler for requesting machines."""
from typing import Dict, Any, Optional, Union, TYPE_CHECKING
import uuid
import json

from src.infrastructure.handlers.base.api_handler import BaseAPIHandler
from src.application.dto.commands import CreateRequestCommand
from src.application.dto.queries import ListTemplatesQuery
from src.monitoring.metrics import MetricsCollector
from src.api.validation import RequestValidator, ValidationException
from src.api.models import RequestMachinesModel
from src.application.request.dto import RequestMachinesResponse
from src.infrastructure.error.decorators import handle_interface_exceptions

class RequestMachinesRESTHandler(BaseAPIHandler):
    """Enhanced API handler for requesting machines - Pure CQRS Implementation."""

    def __init__(self, 
                 query_bus: 'QueryBus',
                 command_bus: 'CommandBus',
                 metrics: Optional[MetricsCollector] = None):
        """
        Initialize handler with pure CQRS dependencies.
        
        Args:
            query_bus: Query bus for CQRS queries
            command_bus: Command bus for CQRS commands
            metrics: Optional metrics collector
        """
        # Initialize without service dependency
        super().__init__(None, metrics)
        # Use helper method to eliminate CQRS initialization duplication
        self._init_cqrs_dependencies(query_bus, command_bus)
        self.validator = RequestValidator()
        
    def handle(self,
               input_data: Optional[Union[Dict[str, Any], str]] = None,
               all_flag: bool = False,
               long: bool = False,
               clean: bool = False,
               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Request machines using specified template.

        Args:
            input_data: Request input data (dict or JSON string)
            all_flag: Whether to request machines for all templates
            long: Not used for this endpoint but included for interface consistency
            clean: Not used for this endpoint but included for interface consistency
            context: Request context information

        Returns:
            Dict containing request status and details
        """
        # Apply middleware in standardized order
        return self.apply_middleware(self._handle, service_name="request_service")(
            input_data=input_data,
            all_flag=all_flag,
            long=long,
            clean=clean,
            context=context
        )
        
    @handle_interface_exceptions(context="request_machines_api", interface_type="api")
    def _handle(self,
                input_data: Optional[Union[Dict[str, Any], str]] = None,
                all_flag: bool = False,
                long: bool = False,
                clean: bool = False,
                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Internal implementation of handle method.
        
        Args:
            input_data: Request input data (dict or JSON string)
            all_flag: Whether to request machines for all templates
            long: Not used for this endpoint but included for interface consistency
            clean: Not used for this endpoint but included for interface consistency
            context: Request context information
            
        Returns:
            Dict containing request status and details
        """
        context = context or {}
        correlation_id = context.get('correlation_id', str(uuid.uuid4()))
        start_time = self.metrics.start_timer() if self.metrics else None

        if all_flag:
            return self._handle_all_templates(input_data, context, correlation_id)

        # Validate input using Pydantic model
        validated_data = self._validate_input(input_data)

        # Extract request parameters from validated model
        template_id = validated_data.template_id
        machine_count = validated_data.machine_count

        # Create metadata for request
        metadata = {
            'source_ip': context.get('client_ip'),
            'user_agent': context.get('user_agent'),
            'created_by': context.get('user_id'),
            'correlation_id': correlation_id,
            'timeout': validated_data.template.get('timeout', 3600),
            'tags': validated_data.template.get('tags')
        }

        # Create request using CQRS command
        command = CreateRequestCommand(
            template_id=template_id,
            machine_count=machine_count,
            timeout=validated_data.template.get('timeout', 3600),
            tags=validated_data.template.get('tags', {}),
            metadata=metadata
        )
        request_id = self._command_bus.execute(command)

        # Record metrics
        if self.metrics:
            self.metrics.record_success(
                'request_machines',
                start_time,
                {
                    'template_id': template_id,
                    'machine_count': machine_count,
                    'correlation_id': correlation_id,
                    'request_id': request_id
                }
            )

        # Create response using DTO
        response = RequestMachinesResponse(
            request_id=request_id,
            message=f"Request VM success from AWS.",  # Removed service dependency
            metadata={
                "correlation_id": correlation_id,
                "template_id": template_id,
                "machine_count": machine_count,
                "timestamp": context.get('timestamp'),
                "request_id": request_id
            }
        )

        # Return response in HostFactory format
        return response.to_dict()

    @handle_interface_exceptions(context="request_all_templates_api", interface_type="api")
    def _handle_all_templates(self, 
                             input_data: Optional[Union[Dict[str, Any], str]],
                             context: Dict[str, Any],
                             correlation_id: str) -> Dict[str, Any]:
        """
        Handle requesting machines for all templates.
        
        Args:
            input_data: Request input data
            context: Request context information
            correlation_id: Correlation ID
            
        Returns:
            Dict containing results for all templates
        """
        # Get all templates using CQRS query
        query = ListTemplatesQuery(active_only=True, include_configuration=False)
        domain_templates = self._query_bus.execute(query)  # List[Template]
        
        # Convert to DTOs for processing
        from src.application.template.dto import TemplateDTO
        templates = [TemplateDTO.from_domain(template) for template in domain_templates]
        results = []
        
        # Parse input data if it's a string
        parsed_input = None
        if isinstance(input_data, str):
            try:
                parsed_input = json.loads(input_data)
            except json.JSONDecodeError:
                parsed_input = None
        else:
            parsed_input = input_data
        
        for template in templates:
            try:
                # Create metadata for request
                metadata = {
                    'source_ip': context.get('client_ip'),
                    'user_agent': context.get('user_agent'),
                    'created_by': context.get('user_id'),
                    'correlation_id': correlation_id,
                    'timeout': parsed_input.get('timeout', 3600) if parsed_input else 3600,
                    'tags': parsed_input.get('tags') if parsed_input else None
                }
                
                # Create request using CQRS command
                command = CreateRequestCommand(
                    template_id=template.template_id,
                    machine_count=template.max_number,
                    timeout=parsed_input.get('timeout', 3600) if parsed_input else 3600,
                    tags=parsed_input.get('tags', {}) if parsed_input else {},
                    metadata=metadata
                )
                request_id = self._command_bus.execute(command)
                
                results.append({
                    "templateId": template.template_id,
                    "requestId": request_id,
                    "numRequested": template.max_number
                })
                
                self.logger.info(
                    f"Created request for template {template.template_id}",
                    extra={
                        'request_id': request_id,
                        'correlation_id': correlation_id,
                        'template_id': template.template_id
                    }
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to create request for template {template.template_id}",
                    exc_info=True,
                    extra={
                        'correlation_id': correlation_id,
                        'template_id': template.template_id,
                        'error': str(e)
                    }
                )
                results.append({
                    "templateId": template.template_id,
                    "error": str(e)
                })

        return {
            "message": "Processed all templates",
            "results": results,
            "metadata": {
                "correlation_id": correlation_id,
                "timestamp": context.get('timestamp')
            }
        }

    @handle_interface_exceptions(context="request_input_validation", interface_type="api")
    def _validate_input(self, input_data: Union[Dict[str, Any], str, None]) -> RequestMachinesModel:
        """
        Validate request input data using Pydantic model.
        
        Args:
            input_data: Request input data (dict or JSON string)
            
        Returns:
            Validated RequestMachinesModel
            
        Raises:
            ValueError: If input data is invalid
        """
        if input_data is None:
            raise ValueError("Input data cannot be None")
            
        try:
            # Use RequestValidator to validate input against RequestMachinesModel
            validated_data = self.validator.validate(RequestMachinesModel, input_data)
            
            # Additional validation for machine count
            machine_count = validated_data.machine_count
            if machine_count <= 0:
                raise ValueError("Machine count must be positive")
                
            return validated_data
            
        except ValidationException as e:
            # Convert ValidationException to ValueError for backward compatibility
            raise ValueError(f"Validation error: {e.message}")

if TYPE_CHECKING:
    from src.infrastructure.di.buses import QueryBus, CommandBus
