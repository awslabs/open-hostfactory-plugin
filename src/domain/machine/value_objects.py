from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime
import re
from src.domain.core.exceptions import ValidationError
from src.domain.core.common_types import IPAddress

class MachineStatus(str, Enum):
    """
    Machine status with mapping to HostFactory states.
    HostFactory expects machine states:
    - running
    - stopped
    - terminated
    - shutting-down
    - stopping
    """
    # External states (HostFactory-facing)
    PENDING = "pending"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    SHUTTING_DOWN = "shutting-down"
    TERMINATED = "terminated"
    
    # Internal states (for tracking)
    RETURNED = "returned"  # Used for return requests
    FAILED = "failed"     # Used for failed provisioning
    UNKNOWN = "unknown"   # Used for unrecognized states

    @classmethod
    def from_aws_state(cls, aws_state: str) -> MachineStatus:
        """Convert AWS instance state to MachineStatus."""
        state_map = {
            "pending": cls.PENDING,
            "running": cls.RUNNING,
            "stopping": cls.STOPPING,
            "stopped": cls.STOPPED,
            "shutting-down": cls.SHUTTING_DOWN,
            "terminated": cls.TERMINATED
        }
        return state_map.get(aws_state.lower(), cls.UNKNOWN)

    def can_transition_to(self, new_status: MachineStatus) -> bool:
        """Validate state transition."""
        valid_transitions = {
            self.PENDING: {self.RUNNING, self.FAILED},
            self.RUNNING: {self.STOPPING, self.SHUTTING_DOWN},
            self.STOPPING: {self.STOPPED, self.FAILED},
            self.STOPPED: {self.RUNNING, self.TERMINATED},
            self.SHUTTING_DOWN: {self.TERMINATED},
            self.TERMINATED: {self.RETURNED},
            self.FAILED: set(),  # Terminal state
            self.RETURNED: set(), # Terminal state
            self.UNKNOWN: {self.PENDING, self.RUNNING, self.STOPPED, self.TERMINATED}
        }
        return new_status in valid_transitions.get(self, set())

    @property
    def is_terminal(self) -> bool:
        """Check if status is terminal."""
        return self in {self.TERMINATED, self.FAILED, self.RETURNED}

    @property
    def is_active(self) -> bool:
        """Check if status is active."""
        return self in {self.PENDING, self.RUNNING}

class PriceType(str, Enum):
    """Machine price type."""
    ON_DEMAND = "on-demand"
    SPOT = "spot"

@dataclass(frozen=True)
class MachineId:
    """Machine identifier with validation."""
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise ValidationError("Machine ID must be a string")
        if not re.match(r'^[i|j]-[a-f0-9]+$', self.value):
            raise ValidationError(f"Invalid machine ID format: {self.value}")

    def __str__(self) -> str:
        return self.value

@dataclass(frozen=True)
class MachineConfiguration:
    """Machine configuration with validation."""
    instance_type: str
    private_ip: IPAddress
    aws_handler: str
    resource_id: str
    public_ip: Optional[IPAddress] = None
    price_type: PriceType = PriceType.ON_DEMAND
    cloud_host_id: Optional[str] = None

    def __post_init__(self):
        if not self.instance_type:
            raise ValidationError("Instance type is required")
        if not self.aws_handler:
            raise ValidationError("AWS handler is required")
        if not self.resource_id:
            raise ValidationError("Resource ID is required")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        result = {
            "instanceType": self.instance_type,
            "privateIpAddress": str(self.private_ip),
            "awsHandler": self.aws_handler,
            "resourceId": self.resource_id,
            "priceType": self.price_type.value
        }
        
        if self.public_ip:
            result["publicIpAddress"] = str(self.public_ip)
        if self.cloud_host_id:
            result["cloudHostId"] = self.cloud_host_id
            
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MachineConfiguration:
        """Create configuration from dictionary."""
        return cls(
            instance_type=data["instanceType"],
            private_ip=IPAddress(data["privateIpAddress"]),
            public_ip=IPAddress(data["publicIpAddress"]) if "publicIpAddress" in data else None,
            aws_handler=data["awsHandler"],
            resource_id=data["resourceId"],
            price_type=PriceType(data.get("priceType", "on-demand")),
            cloud_host_id=data.get("cloudHostId")
        )

@dataclass(frozen=True)
class MachineEvent:
    """Machine lifecycle event."""
    timestamp: datetime
    event_type: str
    old_state: Optional[str]
    new_state: Optional[str]
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.event_type:
            raise ValidationError("Event type is required")

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "eventType": self.event_type,
            "oldState": self.old_state,
            "newState": self.new_state,
            "details": self.details
        }

@dataclass(frozen=True)
class HealthCheck:
    """Machine health check result."""
    check_type: str
    status: bool
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.check_type:
            raise ValidationError("Health check type is required")

    def to_dict(self) -> Dict[str, Any]:
        """Convert health check to dictionary."""
        return {
            "checkType": self.check_type,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details
        }