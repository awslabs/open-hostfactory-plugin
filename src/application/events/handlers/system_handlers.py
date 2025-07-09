"""
System Event Handlers - DRY-compliant handlers using new architecture.

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


@event_handler("SystemStartedEvent")
class SystemStartedHandler(LoggingEventHandler):
    """Handle system startup events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format system started message."""
        fields = self.extract_fields(event, {
            'version': 'unknown',
            'environment': 'unknown',
            'startup_time': None,
            'configuration_loaded': True
        })
        
        message = (
            f"System started: {fields['version']} | "
            f"Environment: {fields['environment']}"
        )
        
        if fields['startup_time']:
            message += f" | Startup time: {self.format_duration(fields['startup_time'])}"
        
        if not fields['configuration_loaded']:
            message += " | Warning: Configuration not fully loaded"
        
        return message


@event_handler("SystemShutdownEvent")
class SystemShutdownHandler(LoggingEventHandler):
    """Handle system shutdown events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format system shutdown message."""
        fields = self.extract_fields(event, {
            'shutdown_reason': 'Normal shutdown',
            'graceful': True,
            'uptime': None,
            'pending_requests': 0
        })
        
        message = (
            f"System shutdown: {fields['shutdown_reason']} | "
            f"Graceful: {fields['graceful']}"
        )
        
        if fields['uptime']:
            message += f" | Uptime: {self.format_duration(fields['uptime'])}"
        
        if fields['pending_requests'] > 0:
            message += f" | Pending requests: {fields['pending_requests']}"
        
        return message


@event_handler("ConfigurationUpdatedEvent")
class ConfigurationUpdatedHandler(LoggingEventHandler):
    """Handle configuration update events - DRY compliant."""
    
    def format_message(self, event: DomainEvent) -> str:
        """Format configuration updated message."""
        fields = self.extract_fields(event, {
            'config_section': 'unknown',
            'changes_count': 0,
            'reload_required': False,
            'updated_by': 'system'
        })
        
        message = (
            f"Configuration updated: {fields['config_section']} | "
            f"Changes: {fields['changes_count']} | "
            f"By: {fields['updated_by']}"
        )
        
        if fields['reload_required']:
            message += " | Reload required"
        
        return message
