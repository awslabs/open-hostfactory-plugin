# src/domain/request/value_objects.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import re
import uuid
from typing import Optional, Dict, Any
from src.domain.core.exceptions import ValidationError

class RequestType(str, Enum):
    """Request type enumeration."""
    ACQUIRE = "acquire"
    RETURN = "return"

class RequestStatus(str, Enum):
    """
    Request status enumeration.
    
    HostFactory External States:
    - running: Request is being processed
    - complete: All machines are running successfully
    - complete_with_error: Some machines failed
    
    Internal States (for tracking):
    - pending: Initial state when request is created
    - creating: AWS resources are being created
    """
    # HostFactory-facing states (as per input-output.md)
    RUNNING = "running"
    COMPLETE = "complete"
    COMPLETE_WITH_ERROR = "complete_with_error"
    
    # Internal tracking states
    PENDING = "pending"
    CREATING = "creating"
    
    def can_transition_to(self, new_status: 'RequestStatus') -> bool:
        """
        Validate state transition.
        
        State Flow:
        PENDING -> CREATING -> RUNNING -> COMPLETE/COMPLETE_WITH_ERROR
        """
        valid_transitions = {
            # Internal transitions
            self.PENDING: {self.CREATING, self.RUNNING},  # Can skip CREATING if no launch template needed
            self.CREATING: {self.RUNNING},
            # External transitions (HostFactory-facing)
            self.RUNNING: {self.COMPLETE, self.COMPLETE_WITH_ERROR},
            self.COMPLETE: set(),  # Terminal state
            self.COMPLETE_WITH_ERROR: set()  # Terminal state
        }
        return new_status in valid_transitions.get(self, set())

    @property
    def is_terminal(self) -> bool:
        """Check if status is terminal."""
        return self in {self.COMPLETE, self.COMPLETE_WITH_ERROR}

    @property
    def is_internal(self) -> bool:
        """Check if status is internal tracking status."""
        return self in {self.PENDING, self.CREATING}

    @property
    def external_status(self) -> str:
        """
        Get the external status to report to HostFactory.
        Internal states are mapped to 'running' for HostFactory compatibility.
        """
        if self.is_internal:
            return self.RUNNING.value
        return self.value

    @property
    def result_status(self) -> str:
        """
        Get result status as per HostFactory requirements.
        Maps to: 'executing', 'succeed', or 'fail'
        """
        if self == self.COMPLETE:
            return "succeed"
        elif self == self.COMPLETE_WITH_ERROR:
            return "fail"
        return "executing"

class RequestResult(str, Enum):
    """
    Request result status as per HostFactory requirements.
    Used in machine status responses.
    """
    EXECUTING = "executing"
    SUCCEED = "succeed"
    FAIL = "fail"

@dataclass(frozen=True)
class RequestId:
    """
    Request identifier with validation.
    Format: 
    - Acquire requests: 'req-<uuid>'
    - Return requests: 'ret-<uuid>'
    """
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise ValidationError("Request ID must be a string")
        if not re.match(r'^(req|ret)-[a-f0-9-]+$', self.value):
            raise ValidationError(f"Invalid request ID format: {self.value}")

    @classmethod
    def generate(cls, request_type: RequestType) -> RequestId:
        """Generate a new request ID with appropriate prefix."""
        prefix = "req" if request_type == RequestType.ACQUIRE else "ret"
        return cls(f"{prefix}-{uuid.uuid4()}")

    @property
    def is_return_request(self) -> bool:
        """Check if this is a return request ID."""
        return self.value.startswith("ret-")

    @property
    def is_acquire_request(self) -> bool:
        """Check if this is an acquire request ID."""
        return self.value.startswith("req-")

    def __str__(self) -> str:
        return self.value

@dataclass(frozen=True)
class RequestConfiguration:
    """Request configuration with validation."""
    num_machines: int
    timeout: int = 3600  # Default 1 hour
    tags: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not isinstance(self.num_machines, int):
            raise ValidationError("Number of machines must be an integer")
        if self.num_machines <= 0:
            raise ValidationError("Number of machines must be positive")
        if self.timeout <= 0:
            raise ValidationError("Timeout must be positive")
        if self.timeout > 86400:  # 24 hours
            raise ValidationError("Timeout cannot exceed 24 hours")
        if self.tags is not None and not isinstance(self.tags, dict):
            raise ValidationError("Tags must be a dictionary")
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise ValidationError("Metadata must be a dictionary")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        result = {
            "numMachines": self.num_machines,
            "timeout": self.timeout
        }
        if self.tags:
            result["tags"] = self.tags
        if self.metadata:
            result["metadata"] = self.metadata
        return result

@dataclass(frozen=True)
class RequestEvent:
    """Request lifecycle event for tracking state changes."""
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
class LaunchTemplateInfo:
    """Launch template information for AWS resource creation."""
    template_id: str
    version: str

    def __post_init__(self):
        if not self.template_id:
            raise ValidationError("Launch template ID is required")
        if not self.version:
            raise ValidationError("Launch template version is required")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "launchTemplateId": self.template_id,
            "version": self.version
        }