"""
Machine Event Handlers - DRY-compliant handlers using new architecture.

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


@event_handler("MachineCreatedEvent")
class MachineCreatedHandler(LoggingEventHandler):
    """Handle machine creation events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format machine created message."""
        fields = self.extract_fields(event, {
            'template_id': 'unknown',
            'instance_type': 'unknown',
            'availability_zone': None
        })
        
        message = (
            f"Machine created: {event.aggregate_id} | "
            f"Template: {fields['template_id']} | "
            f"Type: {fields['instance_type']}"
        )
        
        if fields['availability_zone']:
            message += f" | AZ: {fields['availability_zone']}"
        
        return message


@event_handler("MachineStatusUpdatedEvent")
class MachineStatusUpdatedHandler(LoggingEventHandler):
    """Handle machine status update events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format machine status update message."""
        fields = self.extract_fields(event, {
            'old_status': 'unknown',
            'new_status': 'unknown',
            'reason': None
        })
        
        message = (
            f"Machine status updated: {event.aggregate_id} | "
            f"{fields['old_status']} → {fields['new_status']}"
        )
        
        if fields['reason']:
            message += f" | Reason: {fields['reason']}"
        
        return message


@event_handler("MachineTerminatedEvent")
class MachineTerminatedHandler(LoggingEventHandler):
    """Handle machine termination events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format machine terminated message."""
        fields = self.extract_fields(event, {
            'reason': 'unknown',
            'final_status': 'terminated'
        })
        
        return (
            f"Machine terminated: {event.aggregate_id} | "
            f"Reason: {fields['reason']} | "
            f"Final Status: {fields['final_status']}"
        )


@event_handler("MachineHealthCheckEvent")
class MachineHealthCheckHandler(LoggingEventHandler):
    """Handle machine health check events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format machine health check message."""
        fields = self.extract_fields(event, {
            'health_status': 'unknown',
            'check_type': 'periodic',
            'details': {}
        })
        
        message = (
            f"Machine health check: {event.aggregate_id} | "
            f"Status: {fields['health_status']} | "
            f"Type: {fields['check_type']}"
        )
        
        # Add details if available
        if fields['details'] and isinstance(fields['details'], dict):
            detail_items = []
            for key, value in fields['details'].items():
                detail_items.append(f"{key}: {value}")
            if detail_items:
                message += f" | Details: {', '.join(detail_items)}"
        
        return message


@event_handler("MachineErrorEvent")
class MachineErrorHandler(LoggingEventHandler):
    """Handle machine error events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format machine error message."""
        fields = self.extract_fields(event, {
            'error_message': 'Unknown error',
            'error_code': None,
            'recovery_action': None
        })
        
        message = self.format_error_message(event, fields['error_message'])
        
        if fields['error_code']:
            message += f" | Code: {fields['error_code']}"
        
        if fields['recovery_action']:
            message += f" | Recovery: {fields['recovery_action']}"
        
        return message
