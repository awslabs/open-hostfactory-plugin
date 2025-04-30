# src/infrastructure/event/event_publisher.py
from typing import List
import logging
from src.domain.core.events import DomainEvent

class EventPublisher:
    """
    Concrete implementation of event publishing system.
    Handles publishing domain events to registered handlers.
    """

    def __init__(self):
        self._handlers = {}
        self._logger = logging.getLogger(__name__)

    def register(self, event_type: str, handler: callable) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        self._logger.debug(f"Registered handler for event type: {event_type}")

    def publish(self, event: DomainEvent) -> None:
        """Publish a single event to all registered handlers."""
        event_type = event.__class__.__name__
        handlers = self._handlers.get(event_type, [])
        
        self._logger.debug(f"Publishing event {event_type} to {len(handlers)} handlers")
        
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self._logger.error(f"Error handling event {event_type}: {str(e)}")

    def publish_all(self, events: List[DomainEvent]) -> None:
        """Publish multiple events."""
        for event in events:
            self.publish(event)