# src/api/get_available_templates.py
from typing import Dict, Any, Optional
import logging
from src.application.template.service import TemplateApplicationService
from src.domain.template.exceptions import TemplateNotFoundError
from infrastructure.monitoring.metrics import MetricsCollector
from infrastructure.protection.rate_limiter import RateLimiter

class GetAvailableTemplates:
    """Enhanced API endpoint for retrieving available templates."""

    def __init__(self, 
                 template_service: TemplateApplicationService,
                 rate_limiter: Optional[RateLimiter] = None,
                 metrics: Optional[MetricsCollector] = None):
        self._service = template_service
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
        Get all available templates with enhanced functionality.

        Args:
            input_data: Optional input data
            all_flag: Whether to return all templates
            long: Whether to return detailed information
            context: Request context information

        Returns:
            Dict containing templates and status information
        """
        correlation_id = context.get('correlation_id') if context else None
        start_time = self._metrics.start_timer() if self._metrics else None

        try:
            # Check rate limit
            if self._rate_limiter:
                self._rate_limiter.check_rate_limit(
                    key=context.get('client_ip') if context else 'default'
                )

            # Log request
            self._logger.info(
                "Getting available templates",
                extra={
                    'correlation_id': correlation_id,
                    'client_ip': context.get('client_ip') if context else None,
                    'user_agent': context.get('user_agent') if context else None
                }
            )

            # Get templates
            result = self._service.get_available_templates(long)

            # Add request metadata
            result['metadata'] = {
                'correlation_id': correlation_id,
                'timestamp': context.get('timestamp') if context else None,
                'request_id': context.get('request_id') if context else None
            }

            # Record metrics
            if self._metrics:
                self._metrics.record_success(
                    'get_available_templates',
                    start_time,
                    {
                        'template_count': len(result.get('templates', [])),
                        'correlation_id': correlation_id
                    }
                )

            return result

        except TemplateNotFoundError as e:
            self._handle_error(
                "Template not found error",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": str(e),
                "message": "Failed to retrieve available templates",
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "TemplateNotFoundError"
                }
            }

        except Exception as e:
            self._handle_error(
                "Unexpected error getting templates",
                e,
                correlation_id,
                start_time
            )
            return {
                "error": "Internal server error",
                "message": "Failed to retrieve available templates",
                "metadata": {
                    "correlation_id": correlation_id,
                    "error_type": "InternalError"
                }
            }

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
                'get_available_templates',
                start_time,
                {
                    'error_type': error.__class__.__name__,
                    'correlation_id': correlation_id
                }
            )