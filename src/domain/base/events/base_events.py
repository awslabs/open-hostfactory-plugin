"""Base event classes and protocols - foundation for event-driven architecture."""
from typing import Any, Dict, Protocol, Optional, List
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


class DomainEvent(BaseModel):
    """Base class for all domain events."""
    model_config = ConfigDict(frozen=True)
    
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    event_type: str
    aggregate_id: str
    aggregate_type: str
    version: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def __init__(self, **data):
        # Set event_type based on class name if not provided
        if 'event_type' not in data or not data['event_type']:
            data['event_type'] = self.__class__.__name__
        super().__init__(**data)


class InfrastructureEvent(DomainEvent):
    """Base class for infrastructure-level events."""
    resource_type: str = ""
    resource_id: str = ""


# =============================================================================
# BASE EVENT CLASSES FOR COMMON PATTERNS (DRY IMPROVEMENTS)
# =============================================================================

class TimedEvent(DomainEvent):
    """Base class for events that track duration and timing."""
    duration_ms: float
    start_time: Optional[datetime] = None


class ErrorEvent(DomainEvent):
    """Base class for events that track errors and failures."""
    error_message: str
    error_code: Optional[str] = None
    retry_count: int = 0


class OperationEvent(TimedEvent):
    """Base class for operation events that track success/failure and timing."""
    operation_type: str
    success: bool = True


class PerformanceEvent(TimedEvent):
    """Base class for performance-related events with thresholds."""
    threshold_ms: Optional[float] = None
    threshold_exceeded: bool = False


class StatusChangeEvent(DomainEvent):
    """Base class for events that track status transitions."""
    old_status: str
    new_status: str
    reason: Optional[str] = None


# =============================================================================
# PROTOCOLS
# =============================================================================

class EventPublisher(Protocol):
    """Protocol for event publishing."""
    
    def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""
        ...
    
    def register_handler(self, event_type: str, handler) -> None:
        """Register an event handler."""
        ...



class EventHandler(Protocol):
    """Protocol for event handlers."""
    
    def handle(self, event: DomainEvent) -> None:
        """Handle a domain event."""
        ...
