"""
Request Event Handlers - DRY-compliant handlers using new architecture.

These handlers replace the duplicated code in consolidated_event_handlers.py
with a clean, maintainable architecture following DDD/SOLID/DRY principles.
"""
from typing import Optional

# Import the new base classes and decorator
from src.application.events.base import LoggingEventHandler
from src.application.events.decorators import event_handler

# Import types - using string imports to avoid circular dependencies
try:
    from src.domain.base.events import DomainEvent
    from src.domain.base.ports import LoggingPort
except ImportError:
    # Fallback for testing or when dependencies aren't available
    DomainEvent = object
    LoggingPort = object


@event_handler("RequestCreatedEvent")
class RequestCreatedHandler(LoggingEventHandler):
    """Handle request creation events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format request created message."""
        fields = self.extract_fields(event, {
            'template_id': 'unknown',
            'machine_count': 0,
            'timeout': None,
            'request_type': 'unknown'
        })
        
        message = (
            f"Request created: {event.aggregate_id} | "
            f"Template: {fields['template_id']} | "
            f"Count: {fields['machine_count']} | "
            f"Type: {fields['request_type']}"
        )
        
        if fields['timeout']:
            message += f" | Timeout: {fields['timeout']}s"
        
        return message


@event_handler("RequestStatusUpdatedEvent")
class RequestStatusUpdatedHandler(LoggingEventHandler):
    """Handle request status update events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format request status update message."""
        fields = self.extract_fields(event, {
            'old_status': 'unknown',
            'new_status': 'unknown',
            'reason': None
        })
        
        return self.format_status_change_message(
            event, 
            fields['old_status'], 
            fields['new_status']
        )


@event_handler("RequestCompletedEvent")
class RequestCompletedHandler(LoggingEventHandler):
    """Handle request completion events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format request completed message."""
        fields = self.extract_fields(event, {
            'completion_status': 'completed',
            'machine_ids': [],
            'completion_time': None,
            'duration': None
        })
        
        machine_count = len(fields['machine_ids']) if fields['machine_ids'] else 0
        
        message = (
            f"Request completed: {event.aggregate_id} | "
            f"Status: {fields['completion_status']} | "
            f"Machines: {machine_count}"
        )
        
        if fields['duration']:
            message += f" | Duration: {self.format_duration(fields['duration'])}"
        
        return message


@event_handler("RequestFailedEvent")
class RequestFailedHandler(LoggingEventHandler):
    """Handle request failure events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format request failed message."""
        fields = self.extract_fields(event, {
            'error_message': 'Unknown error',
            'error_code': None,
            'failure_reason': 'Unknown'
        })
        
        message = (
            f"Request failed: {event.aggregate_id} | "
            f"Reason: {fields['failure_reason']} | "
            f"Error: {fields['error_message']}"
        )
        
        if fields['error_code']:
            message += f" | Code: {fields['error_code']}"
        
        return message


@event_handler("RequestCancelledEvent")
class RequestCancelledHandler(LoggingEventHandler):
    """Handle request cancellation events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format request cancelled message."""
        fields = self.extract_fields(event, {
            'cancellation_reason': 'User requested',
            'cancelled_by': 'unknown',
            'partial_completion': False
        })
        
        message = (
            f"Request cancelled: {event.aggregate_id} | "
            f"Reason: {fields['cancellation_reason']} | "
            f"By: {fields['cancelled_by']}"
        )
        
        if fields['partial_completion']:
            message += " | Partial completion"
        
        return message


@event_handler("RequestTimeoutEvent")
class RequestTimeoutHandler(LoggingEventHandler):
    """Handle request timeout events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format request timeout message."""
        fields = self.extract_fields(event, {
            'timeout_duration': 0,
            'partial_results': {},
            'retry_possible': False
        })
        
        message = (
            f"Request timeout: {event.aggregate_id} | "
            f"Duration: {fields['timeout_duration']}s"
        )
        
        if fields['partial_results']:
            partial_count = len(fields['partial_results'])
            message += f" | Partial results: {partial_count}"
        
        if fields['retry_possible']:
            message += " | Retry possible"
        
        return message
