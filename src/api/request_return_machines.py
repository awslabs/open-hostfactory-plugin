# src/api/request_return_machines.py
from typing import Dict, Any, Optional, List
import logging
from src.application.request.service import RequestApplicationService
from src.domain.machine.exceptions import MachineNotFoundError
from infrastructure.monitoring.metrics import MetricsCollector
from infrastructure.protection.rate_limiter import RateLimiter

class RequestReturnMachines:
    """Enhanced API endpoint for returning machines."""

    def __init__(self, 
                 request_service: RequestApplicationService,
                 rate_limiter: Optional[RateLimiter] = None,
                 metrics: Optional[MetricsCollector] = None):
        self._service = request_service
        self._rate_limiter = rate_limiter
        self._metrics = metrics
        self._logger = logging.getLogger(__name__)

    def execute(self,
                input_data: Optional[Dict[str, Any]] = None,
                all_flag: bool = False,
                long: bool = False,
                clean: bool = False,
                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Request machines to be returned.

        Args:
            input_data: Optional input data containing machine IDs
            all_flag: Whether to return all machines
            context: Request context information

        Returns:
            Dict containing return request status
        """
        correlation_id = context.get('correlation_id') if context else None
        start_time = self._metrics.start_timer() if self._metrics else None

        try:
            # Clean up all resources
            if clean:
                self._service.cleanup_all_resources()
                return {
                    "message": "All resources cleaned up successfully",
                    "metadata": {
                        "correlation_id": context.get('correlation_id') if context else None
                    }
                }

            # Check rate limit
            if self._rate_limiter:
                self._rate_limiter.check_rate_limit(
                    key=context.get('client_ip') if context else 'default'
                )

            if all_flag:
                # Return all machines
                request = self._service.create_return_request_all()
                machine_count = len(request.machines)
                self._logger.info(
                    f"Returning all machines ({machine_count} total)",
                    extra={'correlation_id': correlation_id}
                )
            elif all_flag:
                # Get all active machines
                request = self._service.create_return_request_all()
                return {
                    "requestId": str(request.request_id),
                    "message": "Return request created for all machines",
                    "metadata": {
                        "correlation_id": context.get('correlation_id') if context else None,
                        "machine_count": len(request.machines)
                    }
                }
            else:
                # Validate input
                if not input_data or 'machines' not in input_data:
                    raise ValueError("Input must include 'machines' key")

                machine_ids = self._extract_machine_ids(input_data['machines'])
                if not machine_ids:
                    return {
                        "message": "No machines to return",
                        "requestId": None,
                        "metadata": {
                            "correlation_id": correlation_id,
                            "machine_count": 0
                        }
                    }

                # Log request
                self._logger.info(
                    "Returning machines",
                    extra={
                        'correlation_id': correlation_id,
                        'machine_count': len(machine_ids),
                        'machine_ids': machine_ids,
                        'client_ip': context.get('client_ip') if context else None
                    }
                )

                # Create return request
                request = self._service.create_return_request(machine_ids)

            # Record metrics
            if self._metrics:
                self._metrics.record_success(
                    'request_return_machines',
                    start_time,
                    {
                        'machine_count': len(request.machines),
                        'correlation_id': correlation_id
                    }
                )

            return {
                "requestId": str(request.request_id),
                "message": "Delete VM success.",
                "metadata": {
                    "correlation_id": correlation_id,
                    "machine_count": len(request.machines),
                    "timestamp": context.get('timestamp') if context else None
                }
            }

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

        except MachineNotFoundError as e:
            self._handle_error(
                "Machine not found",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": str(e),
                "message": "Machine not found",
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "MachineNotFoundError"
                }
            }

        except Exception as e:
            self._handle_error(
                "Unexpected error returning machines",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": "Internal server error",
                "message": "Failed to return machines",
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "InternalError"
                }
            }

    def _extract_machine_ids(self, machines_data: List[Dict[str, Any]]) -> List[str]:
        """Extract and validate machine IDs from input data."""
        machine_ids = []
        for machine in machines_data:
            if not isinstance(machine, dict):
                raise ValueError("Each machine entry must be a dictionary")
            
            machine_id = machine.get('machineId')
            if not machine_id:
                continue
                
            if not isinstance(machine_id, str):
                raise ValueError(f"Invalid machine ID format: {machine_id}")
                
            machine_ids.append(machine_id)
            
        return machine_ids

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
                'request_return_machines',
                start_time,
                {
                    'error_type': error.__class__.__name__,
                    'correlation_id': correlation_id
                }
            )