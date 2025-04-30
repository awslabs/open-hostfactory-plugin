# src/api/request_machines.py
from typing import Dict, Any, Optional
import logging
import uuid
from src.application.request.service import RequestApplicationService
from src.domain.template.exceptions import TemplateNotFoundError
from src.domain.request.exceptions import RequestValidationError
from src.infrastructure.exceptions import InfrastructureError
from src.infrastructure.aws.exceptions import ResourceNotFoundError
from infrastructure.monitoring.metrics import MetricsCollector
from infrastructure.protection.rate_limiter import RateLimiter

class RequestMachines:
    """Enhanced API endpoint for requesting machines."""

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
        Request machines using specified template.

        Args:
            input_data: Request input data
            all_flag: Not used for this endpoint but included for interface consistency
            long: Not used for this endpoint but included for interface consistency
            context: Request context information

        Returns:
            Dict containing request status and details
        """
        context = context or {}
        correlation_id = context.get('correlation_id', str(uuid.uuid4()))
        start_time = self._metrics.start_timer() if self._metrics else None

        try:
            if all_flag:
                # Get all templates
                templates = self._service.get_template_service().get_available_templates()
                results = []
                
                for template in templates['templates']:
                    try:
                        # Create request for each template with its maxNumber
                        request = self._service.create_request(
                            template_id=template['templateId'],
                            num_machines=template['maxNumber'],
                            timeout=input_data.get('timeout', 3600) if input_data else 3600,
                            tags=input_data.get('tags') if input_data else None,
                            metadata=context
                        )
                        results.append({
                            "templateId": template['templateId'],
                            "requestId": str(request.request_id),
                            "numRequested": template['maxNumber']
                        })
                        self._logger.info(
                            f"Created request for template {template['templateId']}",
                            extra={
                                'request_id': str(request.request_id),
                                'correlation_id': correlation_id,
                                'template_id': template['templateId']
                            }
                        )
                    except Exception as e:
                        self._logger.error(
                            f"Failed to create request for template {template['templateId']}",
                            exc_info=True,
                            extra={
                                'correlation_id': correlation_id,
                                'template_id': template['templateId'],
                                'error': str(e)
                            }
                        )
                        results.append({
                            "templateId": template['templateId'],
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

            # Validate input
            self._validate_input(input_data)

            # Check rate limit
            if self._rate_limiter:
                self._rate_limiter.check_rate_limit(
                    key=context.get('client_ip', 'default')
                )

            # Extract request parameters
            template_data = input_data['template']
            template_id = template_data['templateId']
            num_machines = int(template_data['machineCount'])

            # Log request initiation
            self._logger.info(
                "Requesting machines",
                extra={
                    'correlation_id': correlation_id,
                    'template_id': template_id,
                    'machine_count': num_machines,
                    'client_ip': context.get('client_ip'),
                    'user_agent': context.get('user_agent')
                }
            )

            # Create request with metadata
            request = self._service.create_request(
                template_id=template_id,
                num_machines=num_machines,
                timeout=input_data.get('timeout', 3600),
                tags=input_data.get('tags'),
                metadata={
                    'source_ip': context.get('client_ip'),
                    'user_agent': context.get('user_agent'),
                    'created_by': context.get('user_id'),
                    'correlation_id': correlation_id
                }
            )

            # Log request ID immediately after creation
            request_id = str(request.request_id)
            self._logger.info(
                f"Created request with ID: {request_id}",
                extra={
                    'request_id': request_id,
                    'correlation_id': correlation_id,
                    'template_id': template_id,
                    'machine_count': num_machines
                }
            )

            # Create launch template
            try:
                launch_template = self._service.create_launch_template(request)
                self._logger.info(
                    f"Created launch template for request {request_id}",
                    extra={
                        'request_id': request_id,
                        'correlation_id': correlation_id,
                        'launch_template_id': launch_template['LaunchTemplateId'],
                        'launch_template_version': launch_template['Version']
                    }
                )
            except Exception as e:
                self._logger.error(
                    f"Failed to create launch template for request {request_id}",
                    exc_info=True,
                    extra={
                        'request_id': request_id,
                        'correlation_id': correlation_id,
                        'error': str(e)
                    }
                )
                raise

            # Create AWS resources
            try:
                aws_resource_id = self._service.create_aws_resources(request)
                self._logger.info(
                    f"Created AWS resources for request {request_id}",
                    extra={
                        'request_id': request_id,
                        'correlation_id': correlation_id,
                        'resource_id': aws_resource_id
                    }
                )
            except Exception as e:
                self._logger.error(
                    f"Failed to create AWS resources for request {request_id}",
                    exc_info=True,
                    extra={
                        'request_id': request_id,
                        'correlation_id': correlation_id,
                        'error': str(e)
                    }
                )
                raise

            # Record metrics
            if self._metrics:
                self._metrics.record_success(
                    'request_machines',
                    start_time,
                    {
                        'template_id': template_id,
                        'machine_count': num_machines,
                        'correlation_id': correlation_id,
                        'request_id': request_id
                    }
                )

            # Return response in HostFactory format
            return {
                "requestId": request_id,
                "message": "Request VM success from AWS.",
                "metadata": {
                    "correlation_id": correlation_id,
                    "template_id": template_id,
                    "machine_count": num_machines,
                    "timestamp": context.get('timestamp'),
                    "request_id": request_id
                }
            }

        except (ValueError, KeyError) as e:
            self._handle_error(
                "Invalid input data",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": "Invalid input format",
                "message": str(e),
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "ValidationError"
                }
            }

        except TemplateNotFoundError as e:
            self._handle_error(
                "Template not found",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": str(e),
                "message": "Template not found",
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "TemplateNotFoundError"
                }
            }

        except RequestValidationError as e:
            self._handle_error(
                "Request validation failed",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": str(e),
                "message": "Failed to validate request",
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "RequestValidationError"
                }
            }

        except ResourceNotFoundError as e:
            self._handle_error(
                "Resource not found",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": "Resource not found",
                "message": str(e),
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "ResourceNotFoundError",
                    "resource_type": "subnet" if "subnet" in str(e) else "other"
                }
            }

        except InfrastructureError as e:
            self._handle_error(
                "Infrastructure error",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": "Infrastructure error",
                "message": str(e),
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "InfrastructureError"
                }
            }

        except Exception as e:
            self._handle_error(
                "Unexpected error requesting machines",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": "Internal server error",
                "message": "Failed to request machines",
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "InternalError"
                }
            }

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate request input data."""
        if not isinstance(input_data, dict):
            raise ValueError("Input must be a dictionary")

        if 'template' not in input_data:
            raise ValueError("Input must include 'template' key")

        template_data = input_data['template']
        if not isinstance(template_data, dict):
            raise ValueError("Template data must be a dictionary")

        required_fields = ['templateId', 'machineCount']
        for field in required_fields:
            if field not in template_data:
                raise ValueError(f"Missing required field: {field}")

        try:
            machine_count = int(template_data['machineCount'])
            if machine_count <= 0:
                raise ValueError("Machine count must be positive")
        except ValueError:
            raise ValueError("Invalid machine count")

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
                'request_machines',
                start_time,
                {
                    'error_type': error.__class__.__name__,
                    'correlation_id': correlation_id
                }
            )