"""Enhanced API handler for checking request status."""
from typing import Dict, Any, Optional, Union, TYPE_CHECKING
import uuid

from src.infrastructure.handlers.base.api_handler import BaseAPIHandler
from src.application.request.queries import GetRequestStatusQuery, GetActiveRequestsQuery
from src.application.request.dto import RequestStatusResponse
from src.domain.request.exceptions import RequestNotFoundError
from src.monitoring.metrics import MetricsCollector
from src.api.validation import RequestValidator, ValidationException
from src.api.models import RequestStatusModel
from src.infrastructure.error.decorators import handle_interface_exceptions

class GetRequestStatusRESTHandler(BaseAPIHandler):
    """Enhanced API handler for checking request status - Pure CQRS Implementation."""

    def __init__(self, 
                 query_bus: 'QueryBus',
                 command_bus: 'CommandBus',
                 metrics: Optional[MetricsCollector] = None,
                 max_retries: int = 3):
        """
        Initialize handler with pure CQRS dependencies.
        
        Args:
            query_bus: Query bus for CQRS queries
            command_bus: Command bus for CQRS commands
            metrics: Optional metrics collector
            max_retries: Maximum number of retries for failed requests
        """
        # Initialize without service dependency
        super().__init__(None, metrics)
        self._query_bus = query_bus
        self._command_bus = command_bus
        self._max_retries = max_retries
        self.validator = RequestValidator()
        
    def handle(self, request: Any, **kwargs) -> Dict[str, Any]:
        """
        Get status of requests with enhanced functionality.

        Args:
            input_data: Optional input data containing request IDs (dict or JSON string)
            all_flag: Whether to return all active requests
            long: Whether to return detailed information
            clean: Not used for this endpoint but included for interface consistency
            context: Request context information

        Returns:
            Dict containing request status information
        """
        # Extract parameters from kwargs
        input_data = kwargs.get('input_data')
        all_flag = kwargs.get('all_flag', False)
        long = kwargs.get('long', False)
        clean = kwargs.get('clean', False)
        context = kwargs.get('context', {})
        
        # Apply middleware in standardized order
        return self.apply_middleware(self._handle, service_name="request_service")(
            input_data=input_data,
            all_flag=all_flag,
            long=long,
            clean=clean,
            context=context
        )
        
    @handle_interface_exceptions(context="get_request_status_api", interface_type="api")
    def _handle(self,
                input_data: Optional[Union[Dict[str, Any], str]] = None,
                all_flag: bool = False,
                long: bool = False,
                clean: bool = False,
                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Internal implementation of handle method.
        
        Args:
            input_data: Optional input data containing request IDs (dict or JSON string)
            all_flag: Whether to return all active requests
            long: Whether to return detailed information
            clean: Not used for this endpoint but included for interface consistency
            context: Request context information
            
        Returns:
            Dict containing request status information
        """
        context = context or {}
        correlation_id = context.get('correlation_id', str(uuid.uuid4()))
        start_time = self.metrics.start_timer() if self.metrics else None

        try:
            # Log request
            self.logger.info(
                "Getting request status",
                extra={
                    'correlation_id': correlation_id,
                    'all_flag': all_flag,
                    'long_format': long,
                    'client_ip': context.get('client_ip')
                }
            )

            if all_flag:
                # Get all active requests using CQRS query
                query = GetActiveRequestsQuery(limit=100)
                requests = self._query_bus.execute(query)
                
                # Create response DTO
                response = RequestStatusResponse(
                    requests=[request.to_dict() for request in requests],
                    metadata={
                        'correlation_id': correlation_id,
                        'timestamp': context.get('timestamp'),
                        'request_count': len(requests),
                        'error_count': 0
                    }
                )
                
                # Convert to dict for API response
                return response.model_dump_camel()
            else:
                # Validate input using Pydantic model
                validated_data = self._validate_input(input_data)
                request_ids = validated_data.request_ids
                
                requests = []
                errors = []

                for request_id in request_ids:
                    try:
                        request = self._get_request_with_retry(request_id, long)
                        self.logger.info(
                            f"Retrieved status for request {request_id}",
                            extra={
                                'request_id': request_id,
                                'correlation_id': correlation_id,
                                'status': request.status.value if hasattr(request, 'status') and hasattr(request.status, 'value') and not isinstance(request.status, str) else request.status if hasattr(request, 'status') else request
                            }
                        )
                        requests.append(request.to_dict() if hasattr(request, 'to_dict') else 
                                       {"requestId": request_id, "status": request})
                    except Exception as e:
                        self.logger.error(
                            f"Failed to get status for request {request_id}",
                            extra={
                                'request_id': request_id,
                                'correlation_id': correlation_id,
                                'error': str(e)
                            }
                        )
                        errors.append({
                            "requestId": request_id,
                            "error": str(e)
                        })

                # Create response DTO
                response = RequestStatusResponse(
                    requests=requests,
                    errors=errors if errors else None,
                    metadata={
                        'correlation_id': correlation_id,
                        'timestamp': context.get('timestamp'),
                        'request_count': len(requests),
                        'error_count': len(errors)
                    }
                )
                
                # Convert to dict for API response
                result = response.model_dump_camel()

            # Record metrics
            if self.metrics:
                self.metrics.record_success(
                    'get_request_status',
                    start_time,
                    {
                        'request_count': len(requests),
                        'error_count': len(errors) if errors else 0,
                        'correlation_id': correlation_id
                    }
                )

            return result

        except ValueError as e:
            # Let the error handling middleware handle this
            raise e

        except Exception as e:
            # Let the error handling middleware handle this
            raise e

    @handle_interface_exceptions(context="request_status_validation", interface_type="api")
    def _validate_input(self, input_data: Union[Dict[str, Any], str, None]) -> RequestStatusModel:
        """
        Validate request input data using Pydantic model.
        
        Args:
            input_data: Request input data (dict or JSON string)
            
        Returns:
            Validated RequestStatusModel
            
        Raises:
            ValueError: If input data is invalid
        """
        if input_data is None:
            raise ValueError("Input data cannot be None")
            
        try:
            # Use RequestValidator to validate input against RequestStatusModel
            validated_data = self.validator.validate(RequestStatusModel, input_data)
            
            # Ensure we have at least one request ID
            if not validated_data.request_ids:
                raise ValueError("No request IDs provided")
                
            return validated_data
            
        except ValidationException as e:
            # Convert ValidationException to ValueError for backward compatibility
            raise ValueError(f"Validation error: {e.message}")

    @handle_interface_exceptions(context="request_status_retry", interface_type="api")
    def _get_request_with_retry(self, request_id: str, long: bool) -> Any:
        """
        Get request status with retry mechanism.
        
        Args:
            request_id: Request ID
            long: Whether to return detailed information
            
        Returns:
            Request object or status string
            
        Raises:
            Exception: If all retries fail
        """
        last_error = None
        for attempt in range(self._max_retries):
            try:
                if long:
                    # Get full request details with machines using CQRS query
                    query = GetRequestStatusQuery(request_id=request_id, include_machines=True)
                    return self._query_bus.execute(query)
                else:
                    # Get basic request status using CQRS query
                    query = GetRequestStatusQuery(request_id=request_id, include_machines=False)
                    return self._query_bus.execute(query)
            except RequestNotFoundError:
                # Don't retry if request not found
                raise
            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    self.logger.warning(
                        f"Retry {attempt + 1}/{self._max_retries} for request {request_id}"
                    )
                    continue
        
        # If we get here, all retries failed
        if last_error:
            raise last_error
        else:
            raise Exception(f"Failed to get request status after {self._max_retries} attempts")

if TYPE_CHECKING:
    from src.infrastructure.di.buses import QueryBus, CommandBus
