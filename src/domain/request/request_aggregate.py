# src/domain/request/request_aggregate.py
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from src.domain.request.value_objects import RequestId, RequestType, RequestStatus
from src.domain.request.exceptions import InvalidRequestStateError, MachineAllocationError
from src.domain.machine.machine_aggregate import Machine
from src.domain.template.value_objects import TemplateId
from src.domain.core.common_types import Tags
from src.domain.core.events import ResourceStateChangedEvent, ResourceCreatedEvent

@dataclass
class Request:
    """Request aggregate root."""
    request_id: RequestId
    request_type: RequestType
    template_id: Optional[TemplateId]
    num_requested: int
    aws_handler: str
    status: RequestStatus = RequestStatus.PENDING
    resource_id: Optional[str] = None
    message: str = ""
    machines: List[Machine] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    first_status_check: Optional[datetime] = None
    last_status_check: Optional[datetime] = None
    launch_template_id: Optional[str] = None
    launch_template_version: Optional[str] = None
    tags: Tags = field(default_factory=Tags)
    _events: List[ResourceStateChangedEvent] = field(default_factory=list)
    timeout: int = field(default=3600)  # 1 hour default timeout
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Request':
        """Create a Request instance from a dictionary."""
        # Handle camelCase to snake_case key mapping
        key_mapping = {
            'requestId': 'request_id',
            'requestType': 'request_type',
            'templateId': 'template_id',
            'numRequested': 'num_requested',
            'awsHandler': 'aws_handler',
            'resourceId': 'resource_id',
            'createdAt': 'created_at',
            'firstStatusCheck': 'first_status_check',
            'lastStatusCheck': 'last_status_check',
            'launchTemplateId': 'launch_template_id',
            'launchTemplateVersion': 'launch_template_version'
        }

        # Convert keys to snake_case
        converted_data = {}
        for key, value in data.items():
            new_key = key_mapping.get(key, key.lower())
            converted_data[new_key] = value

        # Convert string dates to datetime objects
        created_at = (datetime.fromisoformat(converted_data['created_at']) 
                    if converted_data.get('created_at') else datetime.utcnow())
        first_status_check = (datetime.fromisoformat(converted_data['first_status_check'])
                            if converted_data.get('first_status_check') else None)
        last_status_check = (datetime.fromisoformat(converted_data['last_status_check'])
                            if converted_data.get('last_status_check') else None)

        # Convert string IDs to proper objects
        request_id = RequestId(converted_data['request_id']) if isinstance(converted_data.get('request_id'), str) else converted_data.get('request_id')
        template_id = TemplateId(converted_data['template_id']) if converted_data.get('template_id') else None
        request_type = RequestType(converted_data['request_type']) if isinstance(converted_data.get('request_type'), str) else converted_data.get('request_type', RequestType.ACQUIRE)
        status = RequestStatus(converted_data['status']) if isinstance(converted_data.get('status'), str) else converted_data.get('status', RequestStatus.PENDING)

        # Convert machines list
        machines = [
            Machine.from_dict(machine_data) if isinstance(machine_data, dict) else machine_data
            for machine_data in converted_data.get('machines', [])
        ]

        # Convert tags
        tags = Tags(converted_data.get('tags', {})) if isinstance(converted_data.get('tags'), dict) else converted_data.get('tags', Tags())

        return cls(
            request_id=request_id,
            request_type=request_type,
            template_id=template_id,
            num_requested=converted_data.get('num_requested', 0),
            aws_handler=converted_data.get('aws_handler', ''),
            status=status,
            resource_id=converted_data.get('resource_id'),
            message=converted_data.get('message', ''),
            machines=machines,
            created_at=created_at,
            first_status_check=first_status_check,
            last_status_check=last_status_check,
            launch_template_id=converted_data.get('launch_template_id'),
            launch_template_version=converted_data.get('launch_template_version'),
            tags=tags,
            timeout=converted_data.get('timeout', 3600),
            metadata=converted_data.get('metadata', {})
        )

    def to_dict(self, long: bool = False) -> Dict[str, Any]:
        """Convert request to dictionary."""
        if not long:
            # HostFactory format
            return {
                "requestId": str(self.request_id),
                "status": self.status.value,
                "message": self.message,
                "machines": [
                    machine.to_dict(long=False) 
                    for machine in self.machines
                ]
            }
        
        # Detailed format with all information
        result = {
            "requestId": str(self.request_id),
            "requestType": self.request_type.value,
            "templateId": str(self.template_id) if self.template_id else None,
            "status": self.status.value,
            "message": self.message,
            "numRequested": self.num_requested,
            "awsHandler": self.aws_handler,
            "resourceId": self.resource_id,
            "machines": [machine.to_dict(long=True) for machine in self.machines],
            "createdAt": self.created_at.isoformat(),
            "firstStatusCheck": self.first_status_check.isoformat() if self.first_status_check else None,
            "lastStatusCheck": self.last_status_check.isoformat() if self.last_status_check else None,
            "launchTemplateId": self.launch_template_id,
            "launchTemplateVersion": self.launch_template_version,
            "tags": self.tags.to_dict(),
            "metadata": self.metadata
        }
        return result

    def __post_init__(self):
        # Record creation event
        self._events.append(
            ResourceCreatedEvent(
                resource_id=str(self.request_id),
                resource_type="Request",
                details=self.to_dict()
            )
        )

    @classmethod
    def create_acquire_request(cls, template_id: str, num_machines: int, aws_handler: str, 
                             timeout: int = 3600, tags: Optional[Dict[str, str]] = None) -> 'Request':
        """Create a new acquire request."""
        return cls(
            request_id=RequestId.generate(RequestType.ACQUIRE),
            request_type=RequestType.ACQUIRE,
            template_id=TemplateId(template_id),
            num_requested=num_machines,
            aws_handler=aws_handler,
            timeout=timeout,
            tags=Tags(tags) if tags else Tags()
        )

    @classmethod
    def create_return_request(cls, machines: List[Machine]) -> 'Request':
        """Create a new return request."""
        return cls(
            request_id=RequestId.generate(RequestType.RETURN),
            request_type=RequestType.RETURN,
            template_id=None,
            num_requested=len(machines),
            aws_handler="return",
            machines=machines
        )

    def update_status(self, new_status: RequestStatus, message: Optional[str] = None) -> None:
        """Update request status with validation and tracking."""
        if self.status == new_status:
            return

        # Define valid transitions with specific error messages
        valid_transitions = {
            RequestStatus.PENDING: {
                RequestStatus.RUNNING: "Request started processing",
                RequestStatus.FAILED: "Request failed during initialization"
            },
            RequestStatus.RUNNING: {
                RequestStatus.COMPLETE: "Request completed successfully",
                RequestStatus.COMPLETE_WITH_ERROR: "Request completed with some errors",
                RequestStatus.FAILED: "Request failed during execution"
            },
            RequestStatus.COMPLETE: {},  # Terminal state
            RequestStatus.COMPLETE_WITH_ERROR: {},  # Terminal state
            RequestStatus.FAILED: {}  # Terminal state
        }

        if new_status not in valid_transitions.get(self.status, {}):
            raise InvalidRequestStateError(
                str(self.request_id),
                self.status.value,
                new_status.value
            )

        old_status = self.status
        self.status = new_status
        if message:
            self.message = message

        # Update status check timestamps
        now = datetime.utcnow()
        self.last_status_check = now
        if not self.first_status_check:
            self.first_status_check = now

        # Check for timeout
        if self.is_active and self.has_timed_out:
            self.status = RequestStatus.FAILED
            self.message = f"Request timed out after {self.timeout} seconds"

        # Record the event
        self._events.append(
            ResourceStateChangedEvent(
                resource_id=str(self.request_id),
                resource_type="Request",
                old_state=old_status.value,
                new_state=new_status.value,
                details={
                    "message": message,
                    "timestamp": now.isoformat(),
                    "machines": len(self.machines)
                } if message else None
            )
        )

    def add_machine(self, machine: Machine) -> None:
        """Add a machine to this request with validation."""
        if len(self.machines) >= self.num_requested:
            raise MachineAllocationError(
                str(self.request_id),
                f"Cannot exceed requested machine count ({self.num_requested})"
            )

        # Validate machine state
        if machine.is_failed:
            self.metadata["failed_machines"] = self.metadata.get("failed_machines", 0) + 1

        self.machines.append(machine)
        self._update_status_from_machines()

    def _update_status_from_machines(self) -> None:
        """Update request status based on machine states."""
        if not self.machines:
            return

        all_complete = len(self.machines) == self.num_requested
        failed_count = sum(1 for m in self.machines if m.is_failed)
        running_count = sum(1 for m in self.machines if m.is_running)

        if all_complete:
            if failed_count > 0:
                self.update_status(
                    RequestStatus.COMPLETE_WITH_ERROR,
                    f"{failed_count} machines failed to provision"
                )
            elif running_count == self.num_requested:
                self.update_status(
                    RequestStatus.COMPLETE,
                    "All machines provisioned successfully"
                )

        # Update metadata
        self.metadata.update({
            "total_machines": len(self.machines),
            "running_machines": running_count,
            "failed_machines": failed_count,
            "last_update": datetime.utcnow().isoformat()
        })

    @property
    def events(self) -> List[ResourceStateChangedEvent]:
        return self._events.copy()

    def clear_events(self) -> None:
        self._events.clear()

    @property
    def is_active(self) -> bool:
        """Check if request is still active."""
        return self.status in [RequestStatus.PENDING, RequestStatus.RUNNING]

    @property
    def has_timed_out(self) -> bool:
        """Check if request has timed out."""
        if not self.first_status_check:
            return False
        elapsed = datetime.utcnow() - self.first_status_check
        return elapsed.total_seconds() > self.timeout

    def set_launch_template_info(self, template_id: str, version: str) -> None:
        """Set launch template information."""
        self.launch_template_id = template_id
        self.launch_template_version = version
        self.metadata["launch_template"] = {
            "id": template_id,
            "version": version,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.update_status(RequestStatus.RUNNING, f"Created launch template {template_id}")

    def set_resource_id(self, resource_id: str) -> None:
        """Set AWS resource ID."""
        self.resource_id = resource_id
        self.metadata["resource"] = {
            "id": resource_id,
            "timestamp": datetime.utcnow().isoformat()
        }