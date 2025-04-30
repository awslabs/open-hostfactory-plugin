from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class MachineDTO:
    """DTO for machine responses."""
    machine_id: str
    name: str
    status: str
    instance_type: str
    private_ip: str
    public_ip: Optional[str]
    result: str  # 'executing', 'fail', or 'succeed'
    launch_time: int
    message: str = ""
    aws_handler: Optional[str] = None
    resource_id: Optional[str] = None
    price_type: Optional[str] = None
    cloud_host_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    health_checks: Optional[Dict[str, Any]] = None

    @classmethod
    def from_domain(cls, machine: Machine, long: bool = False) -> 'MachineDTO':
        """Create DTO from domain object."""
        if not long:
            return cls(
                machine_id=str(machine.machine_id),
                name=machine.name,
                status=machine.status.value,
                instance_type=machine.instance_type,
                private_ip=str(machine.private_ip),
                public_ip=str(machine.public_ip) if machine.public_ip else None,
                result=machine._get_result_status(),
                launch_time=int(machine.launch_time.timestamp()),
                message=machine.message
            )

        return cls(
            machine_id=str(machine.machine_id),
            name=machine.name,
            status=machine.status.value,
            instance_type=machine.instance_type,
            private_ip=str(machine.private_ip),
            public_ip=str(machine.public_ip) if machine.public_ip else None,
            result=machine._get_result_status(),
            launch_time=int(machine.launch_time.timestamp()),
            message=machine.message,
            aws_handler=machine.aws_handler,
            resource_id=machine.resource_id,
            price_type=machine.price_type.value,
            cloud_host_id=machine.cloud_host_id,
            metadata=machine.metadata,
            health_checks=machine.health_checks
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to HostFactory API format."""
        result = {
            "machineId": self.machine_id,
            "name": self.name,
            "status": self.status,
            "instanceType": self.instance_type,
            "privateIpAddress": self.private_ip,
            "result": self.result,
            "launchtime": self.launch_time
        }

        if self.public_ip:
            result["publicIpAddress"] = self.public_ip
        if self.message:
            result["message"] = self.message

        # Add extended information for long format
        if self.aws_handler:
            result.update({
                "awsHandler": self.aws_handler,
                "resourceId": self.resource_id,
                "priceType": self.price_type,
                "cloudHostId": self.cloud_host_id,
                "metadata": self.metadata,
                "healthChecks": self.health_checks
            })

        return result