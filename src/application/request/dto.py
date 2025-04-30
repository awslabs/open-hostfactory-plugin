from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.domain.request.request_aggregate import Request
from src.domain.request.value_objects import RequestType, RequestStatus
from src.application.machine.dto import MachineDTO

@dataclass
class RequestDTO:
    """DTO for request responses."""
    request_id: str
    status: str
    message: str
    machines: List[Dict[str, Any]]
    request_type: Optional[str] = None
    template_id: Optional[str] = None
    aws_handler: Optional[str] = None
    num_requested: Optional[int] = None
    resource_id: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_domain(cls, request: Request, long: bool = False) -> 'RequestDTO':
        """Create DTO from domain object."""
        if not long:
            # Basic HostFactory format
            return cls(
                request_id=str(request.request_id),
                status=request.status.value,
                message=request.message,
                machines=[
                    MachineDTO.from_domain(machine, long=False).to_dict()
                    for machine in request.machines
                ]
            )

        # Detailed format
        return cls(
            request_id=str(request.request_id),
            status=request.status.value,
            message=request.message,
            machines=[
                MachineDTO.from_domain(machine, long=True).to_dict()
                for machine in request.machines
            ],
            request_type=request.request_type.value,
            template_id=str(request.template_id) if request.template_id else None,
            aws_handler=request.aws_handler,
            num_requested=request.num_requested,
            resource_id=request.resource_id,
            created_at=request.created_at,
            metadata=request.metadata
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to HostFactory API format."""
        result = {
            "requestId": self.request_id,
            "status": self.status,
            "message": self.message,
            "machines": self.machines
        }

        if self.request_type:
            result.update({
                "requestType": self.request_type,
                "templateId": self.template_id,
                "awsHandler": self.aws_handler,
                "numRequested": self.num_requested,
                "resourceId": self.resource_id,
                "createdAt": self.created_at.isoformat() if self.created_at else None,
                "metadata": self.metadata
            })

        return result