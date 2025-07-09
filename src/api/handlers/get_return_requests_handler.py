"""Enhanced API handler for getting return requests."""
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime
import uuid

from src.infrastructure.handlers.base.api_handler import BaseAPIHandler
from src.application.request.queries import ListRequestsQuery
from src.application.dto.responses import ReturnRequestResponse
from src.monitoring.metrics import MetricsCollector
from src.config.manager import get_config_manager
from src.config import RequestConfig

# Exception handling infrastructure
from src.infrastructure.error.decorators import handle_interface_exceptions

if TYPE_CHECKING:
    from src.infrastructure.di.buses import QueryBus, CommandBus

class GetReturnRequestsRESTHandler(BaseAPIHandler):
    """Enhanced API handler for getting return requests - Pure CQRS Implementation."""

    def __init__(self, 
                 query_bus: 'QueryBus',
                 command_bus: 'CommandBus',
                 metrics: Optional[MetricsCollector] = None,
                 cache_duration: int = 60):  # Cache duration in seconds
        """
        Initialize handler with pure CQRS dependencies.
        
        Args:
            query_bus: Query bus for CQRS queries
            command_bus: Command bus for CQRS commands
            metrics: Optional metrics collector
            cache_duration: Cache duration in seconds
        """
        # Initialize without service dependency
        super().__init__(None, metrics)
        self._query_bus = query_bus
        self._command_bus = command_bus
        self._cache_duration = cache_duration
        self._cache = {}
        
    def handle(self, request: Any, **kwargs) -> Dict[str, Any]:
        """
        Get return requests with enhanced functionality.

        Args:
            input_data: Optional input data for filtering
            all_flag: Not used for this endpoint but included for interface consistency
            long: Whether to return detailed information
            clean: Not used for this endpoint but included for interface consistency
            context: Request context information

        Returns:
            Dict containing return requests information
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
        
    @handle_interface_exceptions(context="get_return_requests_api", interface_type="api")
    def _handle(self,
                input_data: Optional[Dict[str, Any]] = None,
                all_flag: bool = False,
                long: bool = False,
                clean: bool = False,
                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Internal implementation of handle method.
        
        Args:
            input_data: Optional input data for filtering
            all_flag: Not used for this endpoint but included for interface consistency
            long: Whether to return detailed information
            clean: Not used for this endpoint but included for interface consistency
            context: Request context information
            
        Returns:
            Dict containing return requests information
        """
        context = context or {}
        correlation_id = context.get('correlation_id', str(uuid.uuid4()))
        start_time = self.metrics.start_timer() if self.metrics else None

        try:
            # Try to get from cache first
            cache_key = self._get_cache_key(input_data, long)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                self.logger.debug("Returning cached result", 
                                 extra={'correlation_id': correlation_id})
                return cached_result

            # Log request
            self.logger.info(
                "Getting return requests",
                extra={
                    'correlation_id': correlation_id,
                    'long_format': long,
                    'filters': input_data,
                    'client_ip': context.get('client_ip')
                }
            )

            # Get return requests using CQRS query
            query = ListRequestsQuery(
                status="return_requested",  # Filter for return requests
                limit=100
            )
            return_requests = self._query_bus.execute(query)

            # Apply filters if provided
            if input_data and 'filters' in input_data:
                return_requests = self._apply_filters(return_requests, input_data['filters'])

            # Format response
            formatted_requests = []
            for request in return_requests:
                request_data = {
                    "machine": request.machines[0].name if hasattr(request, 'machines') and request.machines else None,
                    "gracePeriod": self._calculate_grace_period(request),
                    "status": request.status.value if hasattr(request.status, 'value') else request.status,
                    "requestId": str(request.request_id),
                    "createdAt": request.created_at.isoformat() if hasattr(request.created_at, 'isoformat') else request.created_at
                }

                if long:
                    request_data.update({
                        "machines": [m.to_dict() if hasattr(m, 'to_dict') else m for m in request.machines] if hasattr(request, 'machines') else [],
                        "metadata": request.metadata if hasattr(request, 'metadata') else {},
                        "events": [e.to_dict() if hasattr(e, 'to_dict') else e for e in request.events] if hasattr(request, 'events') else []
                    })

                formatted_requests.append(request_data)

            # Create response DTO
            response = ReturnRequestResponse(
                requests=formatted_requests,
                metadata={
                    "correlation_id": correlation_id,
                    "timestamp": context.get('timestamp'),
                    "request_count": len(formatted_requests),
                    "filters_applied": bool(input_data and 'filters' in input_data)
                }
            )
            
            # Convert to dict for API response
            result = response.to_dict()

            # Cache the result
            self._add_to_cache(cache_key, result)

            # Record metrics
            if self.metrics:
                self.metrics.record_success(
                    'get_return_requests',
                    start_time,
                    {
                        'request_count': len(formatted_requests),
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

    def _get_cache_key(self, input_data: Optional[Dict[str, Any]], long: bool) -> str:
        """
        Generate cache key based on input parameters.
        
        Args:
            input_data: Input data for filtering
            long: Whether to return detailed information
            
        Returns:
            Cache key
        """
        return f"return_requests_{hash(str(input_data))}_{long}"

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get result from cache if valid.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached data if valid, None otherwise
        """
        if cache_key in self._cache:
            cached_data = self._cache[cache_key]
            if (datetime.utcnow() - cached_data['timestamp']).total_seconds() < self._cache_duration:
                return cached_data['data']
            else:
                del self._cache[cache_key]
        return None

    def _add_to_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """
        Add result to cache.
        
        Args:
            cache_key: Cache key
            data: Data to cache
        """
        self._cache[cache_key] = {
            'data': data,
            'timestamp': datetime.utcnow()
        }
        self._cleanup_cache()

    def _cleanup_cache(self) -> None:
        """Clean up expired cache entries."""
        now = datetime.utcnow()
        expired_keys = [
            key for key, value in self._cache.items()
            if (now - value['timestamp']).total_seconds() >= self._cache_duration
        ]
        for key in expired_keys:
            del self._cache[key]

    def _apply_filters(self, requests: List[Any], filters: Dict[str, Any]) -> List[Any]:
        """
        Apply filters to return requests.
        
        Args:
            requests: List of return requests
            filters: Filters to apply
            
        Returns:
            Filtered list of return requests
        """
        filtered_requests = requests

        if 'status' in filters:
            filtered_requests = [
                r for r in filtered_requests
                if (r.status.value if hasattr(r.status, 'value') and not isinstance(r.status, str) else r.status) == filters['status']
            ]

        if 'machine_name' in filters:
            filtered_requests = [
                r for r in filtered_requests
                if hasattr(r, 'machines') and any(m.name == filters['machine_name'] for m in r.machines)
            ]

        if 'time_range' in filters:
            start_time = datetime.fromisoformat(filters['time_range']['start'])
            end_time = datetime.fromisoformat(filters['time_range']['end'])
            filtered_requests = [
                r for r in filtered_requests
                if start_time <= r.created_at <= end_time
            ]

        return filtered_requests

    def _calculate_grace_period(self, request: Any) -> int:
        """
        Calculate grace period for return request.
        
        Args:
            request: Return request
            
        Returns:
            Grace period in seconds
        """
        if not hasattr(request, 'machines') or not request.machines:
            return 0

        # Get default grace period from configuration
        config = get_config_manager().get_typed(RequestConfig)
        default_grace_period = config.default_grace_period

        # Check if machine is spot instance
        if hasattr(request, 'machines') and any(hasattr(m, 'price_type') and m.price_type == 'spot' for m in request.machines):
            # Spot instances get 2 minutes grace period
            return 120

        return default_grace_period
