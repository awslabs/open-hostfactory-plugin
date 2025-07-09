"""Core instance manager interface - provider-agnostic instance management."""
from typing import Dict, Any, List, Optional, Protocol, runtime_checkable
from pydantic import BaseModel
from enum import Enum

from src.domain.base.value_objects import InstanceId, InstanceType, Tags


class InstanceState(str, Enum):
    """Instance state enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    SHUTTING_DOWN = "shutting-down"
    TERMINATED = "terminated"


class InstanceSpec(BaseModel):
    """Specification for creating instances."""
    instance_type: InstanceType
    image_id: str
    count: int = 1
    tags: Optional[Tags] = None
    subnet_id: Optional[str] = None
    security_group_ids: Optional[List[str]] = None
    key_name: Optional[str] = None
    user_data: Optional[str] = None
    
    class Config:
        extra = "allow"  # Allow provider-specific config fields


class Instance(BaseModel):
    """Instance information."""
    instance_id: InstanceId
    instance_type: InstanceType
    state: InstanceState
    image_id: str
    launch_time: Optional[str] = None
    tags: Optional[Tags] = None
    
    class Config:
        extra = "allow"  # Allow provider-specific fields


class InstanceStatusResponse(BaseModel):
    """Response for instance status queries."""
    instances: List[Instance]
    total_count: int
    
    class Config:
        extra = "allow"


class InstanceConfig(BaseModel):
    """Base configuration for cloud instances."""
    instance_type: InstanceType
    image_id: str
    count: int = 1
    tags: Optional[Tags] = None
    
    class Config:
        extra = "allow"  # Allow provider-specific config fields


@runtime_checkable
class InstanceManagerPort(Protocol):
    """Interface for managing cloud instances."""
    
    def launch_instances(self, config: InstanceConfig) -> List[InstanceId]:
        """Launch cloud instances."""
        ...
    
    def terminate_instances(self, instance_ids: List[InstanceId]) -> bool:
        """Terminate cloud instances."""
        ...
    
    def get_instance_status(self, instance_ids: List[InstanceId]) -> InstanceStatusResponse:
        """Get status of specific instances."""
        ...
    
    def create_instances(self, spec: InstanceSpec) -> List[Instance]:
        """Create instances based on specification."""
        ...
    
    def list_instances(self, filters: Optional[Dict[str, Any]] = None) -> List[Instance]:
        """List instances with optional filters."""
        ...
    
    def stop_instances(self, instance_ids: List[InstanceId]) -> bool:
        """Stop cloud instances (if supported by provider)."""
        ...
    
    def start_instances(self, instance_ids: List[InstanceId]) -> bool:
        """Start stopped cloud instances (if supported by provider)."""
        ...
    
    def get_instance_status(self, instance_ids: List[InstanceId]) -> Dict[InstanceId, str]:
        """Get the status of cloud instances."""
        ...
    
    def get_instance_details(self, instance_ids: List[InstanceId]) -> List[Dict[str, Any]]:
        """Get detailed information about cloud instances."""
        ...
    
    def update_instance_tags(self, instance_ids: List[InstanceId], tags: Tags) -> bool:
        """Update tags on cloud instances."""
        ...
