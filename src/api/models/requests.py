"""Request models for API handlers."""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from src.application.dto.base import to_camel


class BaseRequestModel(BaseModel):
    """Base class for all request models with automatic camelCase conversion."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # Allow populating by field name (snake_case)
    )


class MachineReferenceModel(BaseRequestModel):
    """Model for machine reference in requests."""
    name: str
    machine_id: Optional[str] = None


class RequestMachinesModel(BaseRequestModel):
    """Model for request machines API."""
    template: Dict[str, Any]
    
    @property
    def template_id(self) -> str:
        """Get template ID from template dictionary."""
        return self.template.get("templateId", "")
    
    @property
    def machine_count(self) -> int:
        """Get machine count from template dictionary."""
        return int(self.template.get("machineCount", 0))


class RequestStatusModel(BaseRequestModel):
    """Model for request status API."""
    requests: List[Dict[str, Any]]
    
    @property
    def request_ids(self) -> List[str]:
        """Get request IDs from requests list."""
        return [r.get("requestId", "") for r in self.requests if "requestId" in r]


class RequestReturnMachinesModel(BaseRequestModel):
    """Model for request return machines API."""
    machines: List[Dict[str, Any]]
    
    @property
    def machine_names(self) -> List[str]:
        """Get machine names from machines list."""
        return [m.get("name", "") for m in self.machines if "name" in m]
    
    @property
    def machine_ids(self) -> List[str]:
        """Get machine IDs from machines list."""
        return [m.get("machineId", "") for m in self.machines if "machineId" in m]


class GetReturnRequestsModel(BaseRequestModel):
    """Model for get return requests API."""
    machines: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    
    @property
    def machine_names(self) -> List[str]:
        """Get machine names from machines list."""
        if not self.machines:
            return []
        return [m.get("name", "") for m in self.machines if "name" in m]
