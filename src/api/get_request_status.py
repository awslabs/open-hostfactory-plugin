# src/api/get_request_status.py
from typing import Dict, Any, Optional
import logging
from src.application.request.service import RequestApplicationService
from src.domain.request.exceptions import RequestNotFoundError
from infrastructure.monitoring.metrics import MetricsCollector
from infrastructure.protection.rate_limiter import RateLimiter

class GetRequestStatus:
    """Enhanced API endpoint for checking request status."""

    def __init__(self, 
                 request_service: RequestApplicationService,
                 rate_limiter: Optional[RateLimiter] = None,
                 metrics: Optional[MetricsCollector] = None,
                 max_retries: int = 3):
        self._service = request_service
        self._rate_limiter = rate_limiter
        self._metrics = metrics
        self._max_retries = max_retries
        self._logger = logging.getLogger(__name__)

    def execute(self,
                input_data: Optional[Dict[str, Any]] = None,
                all_flag: bool = False,
                long: bool = False,
                clean: bool = False,
                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get status of requests with enhanced functionality.

        Args:
            input_data: Optional input data containing request IDs
            all_flag: Whether to return all active requests
            long: Whether to return detailed information
            context: Request context information

        Returns:
            Dict containing request status information
        """
        context = context or {}
        correlation_id = context.get('correlation_id')
        start_time = self._metrics.start_timer() if self._metrics else None

        try:
            # Check rate limit
            if self._rate_limiter:
                self._rate_limiter.check_rate_limit(
                    key=context.get('client_ip', 'default')
                )

            # Log request
            self._logger.info(
                "Getting request status",
                extra={
                    'correlation_id': correlation_id,
                    'all_flag': all_flag,
                    'long_format': long,
                    'client_ip': context.get('client_ip')
                }
            )

            if all_flag:
                requests = self._service.get_active_requests()
                return {
                    "requests": [
                        RequestDTO.from_domain(req, long=long).to_dict()
                        for req in requests
                    ],
                    "status": "complete",
                    "message": "Status retrieved successfully."
                }
            else:
                if not input_data or 'requests' not in input_data:
                    raise ValueError("Input must include 'requests' key")

                # Ensure requests is a list
                if not isinstance(input_data['requests'], list):
                    # Handle the case where a single request is passed as a dict
                    if isinstance(input_data['requests'], dict):
                        input_data['requests'] = [input_data['requests']]
                    else:
                        raise ValueError("'requests' must be a list or a single request object")

                requests = []
                errors = []

                for req_data in input_data['requests']:
                    if 'requestId' not in req_data:
                        errors.append({
                            "requestId": None,
                            "error": "Missing requestId"
                        })
                        continue

                    request_id = req_data['requestId']
                    try:
                        request = self._get_request_with_retry(request_id, long)
                        self._logger.info(
                            f"Retrieved status for request {request_id}",
                            extra={
                                'request_id': request_id,
                                'correlation_id': correlation_id,
                                'status': request.status.value
                            }
                        )
                        requests.append(request.to_dict(long=long))
                    except Exception as e:
                        self._logger.error(
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

                result = {
                    "requests": requests,
                    "status": "complete",
                    "message": "Status retrieved successfully.",
                    "errors": errors if errors else None
                }

            # Add metadata
            result['metadata'] = {
                'correlation_id': correlation_id,
                'timestamp': context.get('timestamp'),
                'request_count': len(requests),
                'error_count': len(errors) if 'errors' in locals() else 0
            }

            # Record metrics
            if self._metrics:
                self._metrics.record_success(
                    'get_request_status',
                    start_time,
                    {
                        'request_count': len(requests),
                        'error_count': len(errors) if 'errors' in locals() else 0,
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
                "Unexpected error getting request status",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": "Internal server error",
                "message": "Failed to retrieve request status",
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "InternalError"
                }
            }

    def _get_request_with_retry(self, request_id: str, long: bool) -> Any:
        """Get request status with retry mechanism."""
        last_error = None
        for attempt in range(self._max_retries):
            try:
                return self._service.get_request_status(request_id, long)
            except RequestNotFoundError as e:
                raise  # Don't retry if request not found
            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    self._logger.warning(
                        f"Retry {attempt + 1}/{self._max_retries} for request {request_id}"
                    )
                    continue
        raise last_error

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
                'get_request_status',
                start_time,
                {
                    'error_type': error.__class__.__name__,
                    'correlation_id': correlation_id
                }
            )