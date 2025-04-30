# src/api/get_return_requests.py
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta
from src.application.request.service import RequestApplicationService
from src.domain.request.exceptions import RequestNotFoundError
from infrastructure.monitoring.metrics import MetricsCollector
from infrastructure.protection.rate_limiter import RateLimiter

class GetReturnRequests:
    """Enhanced API endpoint for getting return requests."""

    def __init__(self, 
                 request_service: RequestApplicationService,
                 rate_limiter: Optional[RateLimiter] = None,
                 metrics: Optional[MetricsCollector] = None,
                 cache_duration: int = 60):  # Cache duration in seconds
        self._service = request_service
        self._rate_limiter = rate_limiter
        self._metrics = metrics
        self._cache_duration = cache_duration
        self._cache = {}
        self._logger = logging.getLogger(__name__)

    def execute(self,
                input_data: Optional[Dict[str, Any]] = None,
                all_flag: bool = False,
                long: bool = False,
                clean: bool = False,
                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get return requests with enhanced functionality.

        Args:
            input_data: Optional input data for filtering
            long: Whether to return detailed information
            context: Request context information

        Returns:
            Dict containing return requests information
        """
        correlation_id = context.get('correlation_id') if context else None
        start_time = self._metrics.start_timer() if self._metrics else None

        try:
            # Check rate limit
            if self._rate_limiter:
                self._rate_limiter.check_rate_limit(
                    key=context.get('client_ip') if context else 'default'
                )

            # Try to get from cache first
            cache_key = self._get_cache_key(input_data, long)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                self._logger.debug("Returning cached result", 
                                 extra={'correlation_id': correlation_id})
                return cached_result

            # Log request
            self._logger.info(
                "Getting return requests",
                extra={
                    'correlation_id': correlation_id,
                    'long_format': long,
                    'filters': input_data,
                    'client_ip': context.get('client_ip') if context else None
                }
            )

            # Get return requests
            return_requests = self._service.get_return_requests()

            # Apply filters if provided
            if input_data and 'filters' in input_data:
                return_requests = self._apply_filters(return_requests, input_data['filters'])

            # Format response
            formatted_requests = []
            for request in return_requests:
                request_data = {
                    "machine": request.machines[0].name if request.machines else None,
                    "gracePeriod": self._calculate_grace_period(request),
                    "status": request.status.value,
                    "requestId": str(request.request_id),
                    "createdAt": request.created_at.isoformat()
                }

                if long:
                    request_data.update({
                        "machines": [m.to_dict() for m in request.machines],
                        "metadata": request.metadata,
                        "events": [e.to_dict() for e in request.events]
                    })

                formatted_requests.append(request_data)

            result = {
                "requests": formatted_requests,
                "status": "complete",
                "message": "Return requests retrieved successfully.",
                "metadata": {
                    "correlation_id": correlation_id,
                    "timestamp": context.get('timestamp') if context else None,
                    "request_count": len(formatted_requests),
                    "filters_applied": bool(input_data and 'filters' in input_data)
                }
            }

            # Cache the result
            self._add_to_cache(cache_key, result)

            # Record metrics
            if self._metrics:
                self._metrics.record_success(
                    'get_return_requests',
                    start_time,
                    {
                        'request_count': len(formatted_requests),
                        'correlation_id': correlation_id
                    }
                )

            return result

        except ValueError as e:
            self._handle_error(
                "Invalid input data",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": str(e),
                "message": "Invalid input format",
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "ValidationError"
                }
            }

        except Exception as e:
            self._handle_error(
                "Unexpected error getting return requests",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": "Internal server error",
                "message": "Failed to retrieve return requests",
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "InternalError"
                }
            }

    def _get_cache_key(self, input_data: Optional[Dict[str, Any]], long: bool) -> str:
        """Generate cache key based on input parameters."""
        return f"return_requests_{hash(str(input_data))}_{long}"

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get result from cache if valid."""
        if cache_key in self._cache:
            cached_data = self._cache[cache_key]
            if (datetime.utcnow() - cached_data['timestamp']).total_seconds() < self._cache_duration:
                return cached_data['data']
            else:
                del self._cache[cache_key]
        return None

    def _add_to_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """Add result to cache."""
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
        """Apply filters to return requests."""
        filtered_requests = requests

        if 'status' in filters:
            filtered_requests = [
                r for r in filtered_requests
                if r.status.value == filters['status']
            ]

        if 'machine_name' in filters:
            filtered_requests = [
                r for r in filtered_requests
                if any(m.name == filters['machine_name'] for m in r.machines)
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
        """Calculate grace period for return request."""
        if not request.machines:
            return 0

        # Default grace period is 5 minutes
        default_grace_period = 300

        # Check if machine is spot instance
        if any(m.price_type == 'spot' for m in request.machines):
            # Spot instances get 2 minutes grace period
            return 120

        return default_grace_period

    def _handle_error(self, 
                     message: str, 
                     error: Exception, 
                     correlation_id: Optional[str],
                     start_time: Optional[float]) -> None:
        """Handle and log errors with metrics."""
        self._logger.error(
            message,
            exc_info=error,
            extra={
                'correlation_id': correlation_id,
                'error_type': error.__class__.__name__
            }
        )

        if self._metrics:
            self._metrics.record_error(
                'get_return_requests',
                start_time,
                {
                    'error_type': error.__class__.__name__,
                    'correlation_id': correlation_id
                }
            )