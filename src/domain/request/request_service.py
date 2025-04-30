# src/domain/request/request_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from src.domain.request.request_aggregate import Request
from src.domain.request.value_objects import (
    RequestId, RequestType, RequestStatus,
    RequestConfiguration, RequestEvent, LaunchTemplateInfo
)
from src.domain.request.exceptions import (
    RequestNotFoundError, InvalidRequestStateError,
    RequestValidationError, MachineAllocationError
)
from src.domain.template.template_service import TemplateService
from src.domain.machine.machine_service import MachineService
from src.domain.core.events import EventPublisher

class RequestService:
    """Domain service for request operations."""

    def __init__(self,
                 request_repository,
                 template_service: TemplateService,
                 machine_service: MachineService,
                 event_publisher: Optional[EventPublisher] = None):
        self._repository = request_repository
        self._template_service = template_service
        self._machine_service = machine_service
        self._event_publisher = event_publisher
        self._logger = logging.getLogger(__name__)

    def create_request(self,
                      template_id: str,
                      num_machines: int,
                      timeout: int = 3600,
                      tags: Optional[Dict[str, str]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Request:
        """Create a new acquire request with validation."""
        try:
            # Validate template
            template = self._template_service.get_template(template_id)
            self._template_service.validate_template_request(template, num_machines)

            # Validate request configuration
            config = RequestConfiguration(
                num_machines=num_machines,
                timeout=timeout,
                tags=tags,
                metadata=metadata
            )

            # Create request
            request = Request.create_acquire_request(
                template_id=template_id,
                num_machines=num_machines,
                aws_handler=template.aws_handler,
                configuration=config
            )

            # Save request
            self._repository.save(request)

            # Publish event if available
            if self._event_publisher:
                self._event_publisher.publish_request_created(request)

            return request

        except Exception as e:
            self._logger.error(f"Failed to create request: {str(e)}")
            raise RequestValidationError(
                "new_request",
                {"creation": str(e)}
            )

    def create_return_request(self, machine_ids: List[str]) -> Request:
        """Create a new return request with validation."""
        try:
            # Get and validate machines
            machines = []
            for machine_id in machine_ids:
                machine = self._machine_service.get_machine(machine_id)
                if not machine.is_running:
                    raise RequestValidationError(
                        "return_request",
                        {machine_id: "Machine is not in running state"}
                    )
                machines.append(machine)

            # Create request
            request = Request.create_return_request(machines)

            # Save request
            self._repository.save(request)

            # Publish event if available
            if self._event_publisher:
                self._event_publisher.publish_return_request_created(request)

            return request

        except Exception as e:
            self._logger.error(f"Failed to create return request: {str(e)}")
            raise

    def get_request_status(self, request_id: str, long: bool = False) -> Request:
        """Get request status with validation."""
        request = self._repository.find_by_id(RequestId(request_id))
        if not request:
            raise RequestNotFoundError(request_id)

        # Check for timeout
        if request.is_active and request.has_timed_out:
            request.update_status(
                RequestStatus.FAILED,
                f"Request timed out after {request.timeout} seconds"
            )
            self._repository.save(request)

            if self._event_publisher:
                self._event_publisher.publish_request_timed_out(request)

        return request

    def update_request_status(self,
                            request_id: str,
                            new_status: RequestStatus,
                            message: Optional[str] = None) -> Request:
        """Update request status with validation."""
        request = self.get_request_status(request_id)

        # Validate state transition
        if not request.status.can_transition_to(new_status):
            raise InvalidRequestStateError(
                request_id,
                request.status.value,
                new_status.value
            )

        # Update status
        request.update_status(new_status, message)
        self._repository.save(request)

        # Publish event if available
        if self._event_publisher:
            self._event_publisher.publish_request_status_changed(
                request_id=request_id,
                old_status=request.status,
                new_status=new_status,
                message=message
            )

        return request

    def get_active_requests(self) -> List[Request]:
        """Get all active requests with status updates."""
        requests = self._repository.find_active_requests()

        # Check for timeouts
        for request in requests:
            if request.has_timed_out:
                request.update_status(
                    RequestStatus.FAILED,
                    f"Request timed out after {request.timeout} seconds"
                )
                self._repository.save(request)

                if self._event_publisher:
                    self._event_publisher.publish_request_timed_out(request)

        return requests

    def get_return_requests(self) -> List[Request]:
        """Get all return requests."""
        return self._repository.find_return_requests()

    def set_launch_template_info(self,
                               request_id: str,
                               template_id: str,
                               version: str) -> Request:
        """Set launch template information for request."""
        request = self.get_request_status(request_id)
        
        launch_template_info = LaunchTemplateInfo(
            template_id=template_id,
            version=version
        )
        
        request.set_launch_template_info(launch_template_info)
        self._repository.save(request)
        
        return request

    def cleanup_old_requests(self, age_hours: int = 24) -> None:
        """Clean up old completed requests."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=age_hours)
            old_requests = [
                request for request in self._repository.find_all()
                if not request.is_active and request.created_at < cutoff_time
            ]

            for request in old_requests:
                self._repository.delete(request.request_id)
                self._logger.info(f"Cleaned up old request: {request.request_id}")

        except Exception as e:
            self._logger.error(f"Failed to cleanup old requests: {str(e)}")
            raise

    def validate_request_state_transition(self,
                                       request: Request,
                                       new_status: RequestStatus) -> None:
        """Validate request state transition."""
        if not request.status.can_transition_to(new_status):
            raise InvalidRequestStateError(
                str(request.request_id),
                request.status.value,
                new_status.value
            )

    def create_return_request_all(self) -> Request:
        """Create a return request for all active machines."""
        machines = self._machine_service.get_active_machines()
        if not machines:
            raise RequestValidationError(
                "return_all",
                {"machines": "No active machines found"}
            )

        request = Request.create_return_request(machines)
        self._repository.save(request)

        if self._event_publisher:
            self._event_publisher.publish_return_request_created(request)

        return request