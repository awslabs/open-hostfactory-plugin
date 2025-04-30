# src/application/request/service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import uuid
from src.domain.request.request_repository import RequestRepository
from src.domain.request.request_aggregate import Request
from src.domain.request.value_objects import RequestId, RequestType, RequestStatus
from src.domain.request.exceptions import RequestNotFoundError, InvalidRequestStateError
from src.domain.template.template_service import TemplateService
from src.domain.template.template_aggregate import Template
from src.domain.machine.machine_service import MachineService
from src.domain.core.events import EventPublisher, ResourceStateChangedEvent
from src.infrastructure.aws.aws_client import AWSClient
from src.infrastructure.exceptions import InfrastructureError
from src.domain.core.exceptions import RequestValidationError

class RequestApplicationService:
    """Domain service for request operations."""

    def __init__(self,
                 request_repository,
                 template_service: TemplateService,
                 machine_service: MachineService,
                 aws_handlers: Dict[str, Any],
                 aws_client: AWSClient,
                 event_publisher: Optional[EventPublisher] = None):
        self._repository = request_repository
        self._template_service = template_service
        self._machine_service = machine_service
        self._aws_handlers = aws_handlers
        self._aws_client = aws_client
        self._event_publisher = event_publisher
        self._logger = logging.getLogger(__name__)

    def _get_aws_handler(self, handler_type: str) -> Optional[Any]:
        """Get the appropriate AWS handler for the given type."""
        return self._aws_handlers.get(handler_type)

    def create_request(self,
                    template_id: str, 
                    num_machines: int,
                    timeout: int = 3600,
                    tags: Optional[Dict[str, str]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> Request:
        """Create a new acquire request and initiate AWS resource creation."""
        try:
            correlation_id = metadata.get('correlation_id', str(uuid.uuid4()))
            self._logger.info(f"Creating request with correlation ID: {correlation_id}, template: {template_id}, machines: {num_machines}")

            # Get and validate template
            template = self._template_service.get_template(template_id)
            
            # Check AWS quotas before proceeding
            self._check_aws_quotas(template, num_machines)
            
            # Create initial request
            request = Request.create_acquire_request(
                template_id=template_id,
                num_machines=num_machines,
                aws_handler=template.aws_handler,
                timeout=timeout,
                tags=tags
            )

            # Add metadata
            request.metadata.update({
                'correlation_id': correlation_id,
                'source_ip': metadata.get('source_ip'),
                'user_agent': metadata.get('user_agent'),
                'created_by': metadata.get('created_by'),
                'template_info': {
                    'handler': template.aws_handler,
                    'instance_type': template.vm_type or list(template.vm_types.keys() if template.vm_types else []),
                    'subnet': template.subnet_id or template.subnet_ids
                }
            })

            # Save initial request
            self._repository.save(request)
            self._logger.info(f"Created request {request.request_id}")

            try:
                # Get AWS handler
                handler = self._get_aws_handler(template.aws_handler)
                if not handler:
                    raise ValueError(f"No handler found for AWS handler type: {template.aws_handler}")

                # Create launch template
                launch_template = handler.create_launch_template(template, request)
                request.set_launch_template_info(
                    launch_template['LaunchTemplateId'],
                    launch_template['Version']
                )
                self._repository.save(request)
                self._logger.info(f"Created launch template for request {request.request_id}")

                # Create AWS resources
                resource_id = handler.acquire_hosts(request, template)
                request.set_resource_id(resource_id)
                request.update_status(RequestStatus.RUNNING, "AWS resource creation initiated")
                self._repository.save(request)
                self._logger.info(f"Created AWS resources for request {request.request_id}")

            except Exception as aws_error:
                error_msg = f"AWS resource creation failed: {str(aws_error)}"
                self._logger.error(f"Error for request {request.request_id}: {error_msg}")
                request.update_status(RequestStatus.FAILED, error_msg)
                self._repository.save(request)
                raise

            return request

        except Exception as e:
            self._logger.error(f"Failed to create request: {str(e)}", exc_info=True)
            raise

    def get_request_status(self, request_id: str, long: bool = False) -> Request:
        """Get request status and update from AWS."""
        request = self._repository.find_by_id(RequestId(request_id))
        if not request:
            raise RequestNotFoundError(request_id)

        self._logger.debug(f"Checking status for request {request_id}")

        if request.is_active and request.resource_id:
            handler = self._get_aws_handler(request.aws_handler)
            if handler:
                try:
                    instance_status = handler.check_hosts_status(request)
                    
                    for instance in instance_status:
                        existing_machine = next(
                            (m for m in request.machines if m.machine_id == instance['InstanceId']), 
                            None
                        )
                        
                        if not existing_machine:
                            machine = self._machine_service.register_machine(
                                instance,
                                str(request.request_id),
                                request.aws_handler,
                                request.resource_id
                            )
                            request.add_machine(machine)
                            self._logger.info(f"Added new machine {machine.machine_id} to request {request_id}")
                    
                    if len(request.machines) == request.num_requested:
                        if all(m.is_running for m in request.machines):
                            request.update_status(RequestStatus.COMPLETE, "All machines are running")
                            self._logger.info(f"Request {request_id} completed successfully")
                        elif any(m.is_failed for m in request.machines):
                            request.update_status(RequestStatus.COMPLETE_WITH_ERROR, "Some machines failed to start")
                            self._logger.warning(f"Request {request_id} completed with errors")
                    
                    self._repository.save(request)
                    
                except Exception as e:
                    self._logger.error(f"Error checking AWS status for request {request_id}: {str(e)}")

        # Check for timeout
        if request.is_active and request.has_timed_out:
            request.update_status(
                RequestStatus.FAILED,
                f"Request timed out after {request.timeout} seconds"
            )
            self._repository.save(request)
            self._logger.warning(f"Request {request_id} timed out")

        return request

    def create_return_request(self, machine_ids: List[str]) -> Request:
        """Create a new return request with validation."""
        try:
            # Get machines and validate their state
            machines = []
            for machine_id in machine_ids:
                machine = self._machine_service.get_machine(machine_id)
                if not machine.is_running:
                    raise ValueError(f"Machine {machine_id} is not in running state")
                machines.append(machine)

            # Create return request
            request = Request.create_return_request(machines)
            
            # Add metadata
            request.metadata['machines_info'] = [
                {
                    'id': str(m.machine_id),
                    'instance_type': m.instance_type,
                    'launch_time': m.launch_time.isoformat()
                }
                for m in machines
            ]

            # Save request
            self._repository.save(request)

            # Publish event
            self._event_publisher.publish(
                ResourceStateChangedEvent(
                    resource_id=str(request.request_id),
                    resource_type="Request",
                    old_state="none",
                    new_state=request.status.value,
                    details={'machine_ids': machine_ids}
                )
            )

            return request

        except Exception as e:
            self._logger.error(f"Failed to create return request: {str(e)}")
            raise

    def create_return_request_all(self) -> Request:
        """Create a return request for all active machines."""
        try:
            machines = self._machine_service.get_active_machines()
            if not machines:
                raise ValueError("No active machines found")

            request = Request.create_return_request(machines)
            self._repository.save(request)

            # Publish event
            self._event_publisher.publish(
                ResourceStateChangedEvent(
                    resource_id=str(request.request_id),
                    resource_type="Request",
                    old_state="none",
                    new_state=request.status.value,
                    details={'machine_count': len(machines)}
                )
            )

            return request

        except Exception as e:
            self._logger.error(f"Failed to create return all request: {str(e)}")
            raise

    def get_active_requests(self) -> List[Request]:
        """Get all active requests with status updates."""
        try:
            requests = self._repository.find_active_requests()
            
            # Check for timeouts and update statuses
            for request in requests:
                if request.has_timed_out:
                    request.update_status(
                        RequestStatus.FAILED,
                        f"Request timed out after {request.timeout} seconds"
                    )
                    self._repository.save(request)

            return requests

        except Exception as e:
            self._logger.error(f"Failed to get active requests: {str(e)}")
            raise

    def get_return_requests(self) -> List[Request]:
        """Get all return requests."""
        try:
            return self._repository.find_return_requests()
        except Exception as e:
            self._logger.error(f"Failed to get return requests: {str(e)}")
            raise

    def update_request_status(self, 
                            request_id: str, 
                            new_status: RequestStatus,
                            message: Optional[str] = None) -> Request:
        """Update request status with validation."""
        try:
            request = self.get_request_status(request_id)
            request.update_status(new_status, message)
            self._repository.save(request)

            # Publish event
            self._event_publisher.publish(
                ResourceStateChangedEvent(
                    resource_id=str(request_id),
                    resource_type="Request",
                    old_state=request.status.value,
                    new_state=new_status.value,
                    details={'message': message} if message else None
                )
            )

            return request

        except Exception as e:
            self._logger.error(f"Failed to update request status: {str(e)}")
            raise

    def _check_aws_quotas(self, template: Template, num_machines: int) -> None:
        """Check AWS service quotas before creating request."""
        try:
            if not self._aws_client:
                return

            service_quotas = self._aws_client.service_quotas_client.get_service_quota(
                ServiceCode='ec2',
                QuotaCode='L-1216C47A'  # Running On-Demand instances
            )

            current_usage = len(self._machine_service.get_active_machines())
            quota_limit = service_quotas['Quota']['Value']

            if current_usage + num_machines > quota_limit:
                raise InfrastructureError(
                    f"Request would exceed AWS quota limit. "
                    f"Current: {current_usage}, Requested: {num_machines}, Limit: {quota_limit}"
                )

        except Exception as e:
            self._logger.warning(f"Failed to check AWS quotas: {str(e)}")

    def _enrich_request_metadata(self, request: Request) -> None:
        """Add additional metadata to request for detailed view."""
        try:
            if request.template_id:
                template = self._template_service.get_template(str(request.template_id))
                request.metadata['template_details'] = template.to_dict()

            if request.machines:
                request.metadata['machines_details'] = [
                    self._machine_service.get_machine(str(m.machine_id)).to_dict()
                    for m in request.machines
                ]

            if self._aws_client and request.resource_id:
                if request.aws_handler == 'EC2Fleet':
                    fleet_info = self._aws_client.ec2_client.describe_fleets(
                        FleetIds=[request.resource_id]
                    )
                    request.metadata['aws_details'] = fleet_info['Fleets'][0]
                elif request.aws_handler == 'SpotFleet':
                    fleet_info = self._aws_client.ec2_client.describe_spot_fleet_requests(
                        SpotFleetRequestIds=[request.resource_id]
                    )
                    request.metadata['aws_details'] = fleet_info['SpotFleetRequestConfigs'][0]

        except Exception as e:
            self._logger.warning(f"Failed to enrich request metadata: {str(e)}")

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

    def cleanup_all_resources(self) -> None:
        """Clean up all AWS resources and clear the database."""
        try:
            # Get all requests
            all_requests = self._repository.find_all()
            
            # First, cancel/delete all AWS resources
            for request in all_requests:
                try:
                    # Get the appropriate AWS handler
                    handler = self._aws_handlers.get(request.aws_handler)
                    if not handler:
                        self._logger.warning(f"No handler found for {request.aws_handler}")
                        continue

                    # Collect instance IDs for termination
                    instance_ids = []
                    if request.machines:
                        instance_ids.extend([str(m.machine_id) for m in request.machines])

                    if request.resource_id:
                        # Cancel/delete parent resources (fleets, ASGs)
                        if request.aws_handler == 'SpotFleet':
                            self._aws_client.ec2_client.cancel_spot_fleet_requests(
                                SpotFleetRequestIds=[request.resource_id],
                                TerminateInstances=True
                            )
                        elif request.aws_handler == 'EC2Fleet':
                            self._aws_client.ec2_client.delete_fleets(
                                FleetIds=[request.resource_id],
                                TerminateInstances=True
                            )
                        elif request.aws_handler == 'ASG':
                            self._aws_client.autoscaling_client.delete_auto_scaling_group(
                                AutoScalingGroupName=request.resource_id,
                                ForceDelete=True
                            )
                        elif request.aws_handler == 'RunInstances' and instance_ids:
                            # For RunInstances, terminate instances directly
                            self._aws_client.ec2_client.terminate_instances(
                                InstanceIds=instance_ids
                            )

                    # Delete launch template if it exists
                    if request.launch_template_id:
                        try:
                            self._aws_client.ec2_client.delete_launch_template(
                                LaunchTemplateId=request.launch_template_id
                            )
                        except Exception as e:
                            self._logger.warning(f"Failed to delete launch template: {str(e)}")

                except Exception as e:
                    self._logger.warning(f"Error cleaning up AWS resources for request {request.request_id}: {str(e)}")

            # Double-check for any remaining instances
            try:
                # Get all instances with our tags
                instances = self._aws_client.ec2_client.describe_instances(
                    Filters=[
                        {'Name': 'tag:CreatedBy', 'Values': ['HostFactory']}
                    ]
                )
                
                remaining_instance_ids = []
                for reservation in instances.get('Reservations', []):
                    for instance in reservation['Instances']:
                        if instance['State']['Name'] not in ['terminated', 'shutting-down']:
                            remaining_instance_ids.append(instance['InstanceId'])

                if remaining_instance_ids:
                    self._logger.info(f"Terminating remaining instances: {remaining_instance_ids}")
                    self._aws_client.ec2_client.terminate_instances(
                        InstanceIds=remaining_instance_ids
                    )

            except Exception as e:
                self._logger.warning(f"Error cleaning up remaining instances: {str(e)}")

            # Handle database cleanup
            try:
                # Get all requests again to ensure we have latest state
                all_requests = self._repository.find_all()
                
                # Update all requests to terminated/failed state
                for request in all_requests:
                    if request.is_active:
                        request.update_status(
                            RequestStatus.FAILED,
                            "Request terminated during cleanup"
                        )
                        self._repository.save(request)

                # Update all machines to terminated state
                for request in all_requests:
                    for machine in request.machines:
                        if machine.is_running:
                            machine.update_status(
                                MachineStatus.TERMINATED,
                                "Machine terminated during cleanup"
                            )
                            self._machine_service.update_machine_status(
                                str(machine.machine_id),
                                MachineStatus.TERMINATED,
                                "Machine terminated during cleanup"
                            )

                self._logger.info("Database cleanup completed successfully")

            except Exception as e:
                self._logger.error(f"Error during database cleanup: {str(e)}")
                raise InfrastructureError(f"Failed to cleanup database: {str(e)}")

    def get_template_service(self) -> TemplateService:
        """Get template service for --all operations."""
        return self._template_service

    def create_return_request_all(self) -> Request:
        """Create a return request for all active machines."""
        try:
            # Get all active machines
            machines = self._machine_service.get_active_machines()
            if not machines:
                raise RequestValidationError(
                    "return_all",
                    {"machines": "No active machines found"}
                )

            # Group machines by their original request
            machines_by_request = {}
            for machine in machines:
                if machine.request_id not in machines_by_request:
                    machines_by_request[machine.request_id] = {
                        'handler': machine.aws_handler,
                        'resource_id': machine.resource_id,
                        'machines': []
                    }
                machines_by_request[machine.request_id]['machines'].append(machine)

            # Release machines through their respective handlers
            for req_id, req_data in machines_by_request.items():
                handler = self._aws_handlers.get(req_data['handler'])
                if handler:
                    # Create a temporary request object with all required fields
                    temp_request = Request(
                        request_id=req_id,
                        request_type=RequestType.RETURN,
                        template_id=None,  # Not needed for return
                        num_requested=len(req_data['machines']),
                        aws_handler=req_data['handler'],
                        resource_id=req_data['resource_id'],
                        machines=req_data['machines']
                    )
                    handler.release_hosts(temp_request)

            # Create the final return request
            request = Request.create_return_request(machines)
            self._repository.save(request)

            if self._event_publisher:
                self._event_publisher.publish(
                    ResourceStateChangedEvent(
                        resource_id=str(request.request_id),
                        resource_type="Request",
                        old_state="none",
                        new_state=request.status.value,
                        details={'machine_count': len(machines)}
                    )
                )

            return request

        except Exception as e:
            self._logger.error(f"Failed to create return request for all machines: {str(e)}")
            raise