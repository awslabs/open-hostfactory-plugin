"""Enhanced API handler for retrieving available templates."""
from typing import Dict, Any, Optional

from src.infrastructure.handlers.base.api_handler import BaseAPIHandler
from src.application.dto.responses import TemplateListResponse
from src.application.dto.queries import ListTemplatesQuery
from src.monitoring.metrics import MetricsCollector
from src.infrastructure.di.buses import QueryBus, CommandBus
from src.application.template.format_service import TemplateFormatService

# Exception handling infrastructure
from src.infrastructure.error.decorators import handle_interface_exceptions

class GetAvailableTemplatesRESTHandler(BaseAPIHandler):
    """Enhanced API handler for retrieving available templates - Pure CQRS Implementation."""

    def __init__(self, 
                 query_bus: QueryBus,
                 command_bus: CommandBus,
                 format_service: TemplateFormatService,
                 metrics: Optional[MetricsCollector] = None):
        """
        Initialize handler with injected CQRS dependencies.
        
        Args:
            query_bus: Query bus for CQRS queries (injected)
            command_bus: Command bus for CQRS commands (injected)
            format_service: Template format conversion service (injected)
            metrics: Optional metrics collector
            
        Note:
            Now uses constructor injection instead of service locator pattern.
            All dependencies are explicitly provided via constructor.
        """
        super().__init__(None, metrics)
        self._query_bus = query_bus
        self._command_bus = command_bus
        self._format_service = format_service
        
    def handle(self,
                input_data: Optional[Dict[str, Any]] = None,
                all_flag: bool = False,
                long: bool = False,
                clean: bool = False,
                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get all available templates with enhanced functionality.

        Args:
            input_data: Optional input data
            all_flag: Whether to return all templates
            long: Whether to return detailed information
            clean: Whether to return clean output
            context: Request context information

        Returns:
            Dict containing templates and status information
        """
        # Apply middleware in standardized order
        return self.apply_middleware(self._handle, service_name="template_service")(
            input_data=input_data,
            all_flag=all_flag,
            long=long,
            clean=clean,
            context=context
        )
        
    @handle_interface_exceptions(context="get_available_templates_api", interface_type="api")
    def _handle(self,
                input_data: Optional[Dict[str, Any]] = None,
                all_flag: bool = False,
                long: bool = False,
                clean: bool = False,
                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Internal implementation of handle method - Pure CQRS.
        
        Args:
            input_data: Optional input data
            all_flag: Whether to return all templates
            long: Whether to return detailed information
            clean: Whether to return clean output
            context: Request context information
            
        Returns:
            Dict containing templates and status information
        """
        correlation_id = context.get('correlation_id') if context else None
        start_time = self.metrics.start_timer() if self.metrics else None

        # Get templates using CQRS query
        query = ListTemplatesQuery(
            active_only=not all_flag,
            include_configuration=long
        )
        
        # Use injected query bus
        domain_templates = self._query_bus.execute(query)  # List[Template]
        
        # Convert to DTOs
        from src.application.template.dto import TemplateDTO
        template_dtos = [TemplateDTO.from_domain(template) for template in domain_templates]
        
        # Create response object
        response = TemplateListResponse(templates=template_dtos)
        
        # Convert to API format with camelCase keys using format service
        result = response.to_dict(format_service=self._format_service)

        # Add request metadata
        result['metadata'] = {
            'correlation_id': correlation_id,
            'timestamp': context.get('timestamp') if context else None,
            'request_id': context.get('request_id') if context else None
        }

        # Record metrics
        if self.metrics:
            self.metrics.record_success(
                'get_available_templates',
                start_time,
                {
                    'template_count': len(result.get('templates', [])),
                    'correlation_id': correlation_id
                }
            )

        return result
