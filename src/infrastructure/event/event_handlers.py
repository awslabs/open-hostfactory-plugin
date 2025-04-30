# src/infrastructure/event/event_handlers.py
import logging
from src.domain.core.events import (
    ResourceStateChangedEvent,
    ResourceCreatedEvent,
    ResourceDeletedEvent,
    OperationFailedEvent
)

class EventHandlers:
    """
    Collection of event handlers for domain events.
    """

    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def handle_resource_state_changed(self, event: ResourceStateChangedEvent) -> None:
        """Handle resource state change events."""
        self._logger.info(
            f"Resource {event.resource_type} ({event.resource_id}) "
            f"state changed from {event.old_state} to {event.new_state}"
        )

    def handle_resource_created(self, event: ResourceCreatedEvent) -> None:
        """Handle resource creation events."""
        self._logger.info(
            f"Resource {event.resource_type} ({event.resource_id}) created"
        )

    def handle_resource_deleted(self, event: ResourceDeletedEvent) -> None:
        """Handle resource deletion events."""
        self._logger.info(
            f"Resource {event.resource_type} ({event.resource_id}) deleted"
        )

    def handle_operation_failed(self, event: OperationFailedEvent) -> None:
        """Handle operation failure events."""
        self._logger.error(
            f"Operation {event.operation} failed for resource {event.resource_id}: "
            f"{event.error_message}"
        )