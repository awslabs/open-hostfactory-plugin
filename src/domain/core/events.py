from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import uuid

@dataclass(frozen=True)
class ResourceStateChangedEvent:
    """Event raised when a resource's state changes."""
    old_state: str
    new_state: str
    resource_id: str
    resource_type: str
    details: Optional[Dict[str, Any]] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass(frozen=True)
class ResourceCreatedEvent:
    """Event raised when a new resource is created."""
    resource_id: str
    resource_type: str
    details: Optional[Dict[str, Any]] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass(frozen=True)
class ResourceDeletedEvent:
    """Event raised when a resource is deleted."""
    resource_id: str
    resource_type: str
    details: Optional[Dict[str, Any]] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass(frozen=True)
class OperationFailedEvent:
    """Event raised when an operation fails."""
    operation: str
    error_message: str
    resource_id: str
    resource_type: str
    details: Optional[Dict[str, Any]] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

# Type alias for all event types
DomainEvent = ResourceStateChangedEvent | ResourceCreatedEvent | ResourceDeletedEvent | OperationFailedEvent

class EventHandler(ABC):
    """Base class for event handlers."""
    @abstractmethod
    def handle(self, event: DomainEvent) -> None:
        pass

class EventPublisher:
    """Publishes domain events to registered handlers."""
    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = {}

    def register(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Publish an event to all registered handlers."""
        event_type = event.__class__.__name__
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            handler.handle(event)

    def publish_all(self, events: List[DomainEvent]) -> None:
        """Publish multiple events."""
        for event in events:
            self.publish(event)
