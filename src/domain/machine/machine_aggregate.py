from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from src.domain.machine.value_objects import MachineId, MachineStatus, PriceType
from src.domain.machine.exceptions import InvalidMachineStateError
from src.domain.request.value_objects import RequestId
from src.domain.core.common_types import IPAddress, Tags
from src.domain.core.events import ResourceStateChangedEvent

@dataclass
class Machine:
    """Machine aggregate root."""
    machine_id: MachineId
    request_id: RequestId
    name: str
    status: MachineStatus
    instance_type: str
    private_ip: IPAddress
    aws_handler: str
    resource_id: str
    public_ip: Optional[IPAddress] = None
    price_type: PriceType = PriceType.ON_DEMAND
    cloud_host_id: Optional[str] = None
    launch_time: datetime = field(default_factory=datetime.utcnow)
    running_time: Optional[datetime] = None
    stopped_time: Optional[datetime] = None
    stopped_reason: Optional[str] = None
    terminated_time: Optional[datetime] = None
    terminated_reason: Optional[str] = None
    failed_time: Optional[datetime] = None
    failed_reason: Optional[str] = None
    returned_time: Optional[datetime] = None
    return_id: Optional[str] = None
    tags: Tags = field(default_factory=Tags)
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    _events: List[ResourceStateChangedEvent] = field(default_factory=list)
    health_checks: Dict[str, Any] = field(default_factory=dict)
    lifecycle_events: List[Dict[str, Any]] = field(default_factory=list)

    def update_status(self, new_status: MachineStatus, reason: Optional[str] = None) -> None:
        """Update machine status with enhanced validation and tracking."""
        if self.status == new_status:
            return

        # Define valid transitions with specific error messages
        valid_transitions = {
            MachineStatus.PENDING: {
                MachineStatus.RUNNING: "Machine started successfully",
                MachineStatus.FAILED: "Machine failed during startup"
            },
            MachineStatus.RUNNING: {
                MachineStatus.STOPPING: "Machine is being stopped",
                MachineStatus.TERMINATED: "Machine is being terminated"
            },
            MachineStatus.STOPPING: {
                MachineStatus.STOPPED: "Machine stopped successfully",
                MachineStatus.FAILED: "Machine failed during stop"
            },
            MachineStatus.STOPPED: {
                MachineStatus.RUNNING: "Machine restarted",
                MachineStatus.TERMINATED: "Machine is being terminated"
            },
            MachineStatus.TERMINATED: {
                MachineStatus.RETURNED: "Machine returned to provider"
            },
            MachineStatus.FAILED: {},  # Terminal state
            MachineStatus.RETURNED: {}  # Terminal state
        }

        if new_status not in valid_transitions.get(self.status, {}):
            raise InvalidMachineStateError(
                str(self.machine_id),
                self.status.value,
                new_status.value
            )

        old_status = self.status
        self.status = new_status
        self.message = reason if reason else valid_transitions[old_status][new_status]

        # Update timestamps and reasons based on status
        now = datetime.utcnow()
        if new_status == MachineStatus.RUNNING:
            self.running_time = now
        elif new_status == MachineStatus.STOPPED:
            self.stopped_time = now
            self.stopped_reason = reason
        elif new_status == MachineStatus.TERMINATED:
            self.terminated_time = now
            self.terminated_reason = reason
        elif new_status == MachineStatus.FAILED:
            self.failed_time = now
            self.failed_reason = reason

        # Record lifecycle event
        self.lifecycle_events.append({
            "timestamp": now.isoformat(),
            "event": f"Status changed from {old_status.value} to {new_status.value}",
            "reason": reason if reason else "Status transition",
            "details": {
                "old_status": old_status.value,
                "new_status": new_status.value,
                "message": self.message
            }
        })

        # Record the state change event
        self._events.append(
            ResourceStateChangedEvent(
                resource_id=str(self.machine_id),
                resource_type="Machine",
                old_state=old_status.value,
                new_state=new_status.value,
                details={
                    "reason": reason,
                    "timestamp": now.isoformat(),
                    "request_id": str(self.request_id)
                } if reason else None
            )
        )

    def mark_as_returned(self, return_id: str) -> None:
        """Mark machine as returned with enhanced tracking."""
        self.return_id = return_id
        self.returned_time = datetime.utcnow()
        self.update_status(MachineStatus.RETURNED, "Machine returned to provider")

    def update_health_check(self, check_type: str, status: bool, details: Optional[Dict[str, Any]] = None) -> None:
        """Update machine health check status."""
        now = datetime.utcnow()
        self.health_checks[check_type] = {
            "status": status,
            "last_check": now.isoformat(),
            "details": details or {},
            "history": self.health_checks.get(check_type, {}).get("history", []) + [{
                "timestamp": now.isoformat(),
                "status": status,
                "details": details or {}
            }]
        }

    @property
    def is_running(self) -> bool:
        return self.status == MachineStatus.RUNNING

    @property
    def is_failed(self) -> bool:
        return self.status in [MachineStatus.FAILED, MachineStatus.TERMINATED]

    @property
    def is_returned(self) -> bool:
        return self.status == MachineStatus.RETURNED

    @property
    def is_healthy(self) -> bool:
        """Check if all health checks are passing."""
        return all(
            check.get("status", False)
            for check in self.health_checks.values()
        )

    @property
    def events(self) -> List[ResourceStateChangedEvent]:
        return self._events.copy()

    def clear_events(self) -> None:
        self._events.clear()

    def to_dict(self, long: bool = False) -> Dict[str, Any]:
        """
        Convert machine to dictionary.
        
        Args:
            long: If True, include all details. If False, follow HostFactory format.
        """
        if not long:
            # HostFactory format as per input-output.md
            result = {
                "machineId": str(self.machine_id),
                "name": self.name,
                "status": self.status.value,
                "instanceType": self.instance_type,
                "privateIpAddress": str(self.private_ip),
                "result": self._get_result_status(),  # 'executing', 'fail', or 'succeed'
                "launchtime": int(self.launch_time.timestamp())
            }
            
            # Optional fields - only include if they have values
            if self.public_ip:
                result["publicIpAddress"] = str(self.public_ip)
            if self.message:
                result["message"] = self.message
            
            return result
        
        # Detailed format with all information
        result = {
            "machineId": str(self.machine_id),
            "requestId": str(self.request_id),
            "name": self.name,
            "status": self.status.value,
            "instanceType": self.instance_type,
            "privateIpAddress": str(self.private_ip),
            "publicIpAddress": str(self.public_ip) if self.public_ip else None,
            "awsHandler": self.aws_handler,
            "resourceId": self.resource_id,
            "priceType": self.price_type.value,
            "cloudHostId": self.cloud_host_id,
            "launchtime": int(self.launch_time.timestamp()),
            "runningTime": self.running_time.isoformat() if self.running_time else None,
            "stoppedTime": self.stopped_time.isoformat() if self.stopped_time else None,
            "stoppedReason": self.stopped_reason,
            "terminatedTime": self.terminated_time.isoformat() if self.terminated_time else None,
            "terminatedReason": self.terminated_reason,
            "failedTime": self.failed_time.isoformat() if self.failed_time else None,
            "failedReason": self.failed_reason,
            "returnedTime": self.returned_time.isoformat() if self.returned_time else None,
            "returnId": self.return_id,
            "tags": self.tags.to_dict(),
            "message": self.message,
            "metadata": self.metadata,
            "healthChecks": self.health_checks,
            "lifecycleEvents": self.lifecycle_events,
            "isHealthy": self.is_healthy
        }
        return result

    def _get_result_status(self) -> str:
        """Get result status as per HostFactory requirements."""
        if self.status == MachineStatus.RUNNING:
            return "succeed"
        elif self.status in [MachineStatus.FAILED, MachineStatus.TERMINATED]:
            return "fail"
        return "executing"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Machine':
        """Create machine from dictionary."""
        return cls(
            machine_id=MachineId(data["machineId"]),
            request_id=RequestId(data["requestId"]),
            name=data["name"],
            status=MachineStatus(data["status"]),
            instance_type=data["instanceType"],
            private_ip=IPAddress(data["privateIpAddress"]),
            public_ip=IPAddress(data["publicIpAddress"]) if data.get("publicIpAddress") else None,
            aws_handler=data["awsHandler"],
            resource_id=data["resourceId"],
            price_type=PriceType(data.get("priceType", "on-demand")),
            cloud_host_id=data.get("cloudHostId"),
            launch_time=datetime.fromisoformat(data["launchTime"]),
            running_time=datetime.fromisoformat(data["runningTime"]) if data.get("runningTime") else None,
            stopped_time=datetime.fromisoformat(data["stoppedTime"]) if data.get("stoppedTime") else None,
            stopped_reason=data.get("stoppedReason"),
            terminated_time=datetime.fromisoformat(data["terminatedTime"]) if data.get("terminatedTime") else None,
            terminated_reason=data.get("terminatedReason"),
            failed_time=datetime.fromisoformat(data["failedTime"]) if data.get("failedTime") else None,
            failed_reason=data.get("failedReason"),
            returned_time=datetime.fromisoformat(data["returnedTime"]) if data.get("returnedTime") else None,
            return_id=data.get("returnId"),
            tags=Tags.from_dict(data.get("tags", {})),
            message=data.get("message", ""),
            metadata=data.get("metadata", {}),
            health_checks=data.get("healthChecks", {}),
            lifecycle_events=data.get("lifecycleEvents", [])
        )