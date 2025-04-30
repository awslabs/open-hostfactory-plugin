import pytest
from dataclasses import dataclass
from src.domain.core.events import (
    EventPublisher,
    ResourceStateChangedEvent,
    EventHandler
)

class TestEventHandler(EventHandler):
    def __init__(self):
        self.received_events = []

    def handle(self, event):
        self.received_events.append(event)

def test_event_publisher_single_event():
    # Arrange
    publisher = EventPublisher()
    handler = TestEventHandler()
    
    publisher.register("ResourceStateChangedEvent", handler)
    event = ResourceStateChangedEvent(
        old_state="pending",
        new_state="running",
        resource_id="test-123",
        resource_type="TestResource"
    )

    # Act
    publisher.publish(event)

    # Assert
    assert len(handler.received_events) == 1
    assert handler.received_events[0].old_state == "pending"
    assert handler.received_events[0].new_state == "running"

def test_event_publisher_multiple_handlers():
    # Arrange
    publisher = EventPublisher()
    handler1 = TestEventHandler()
    handler2 = TestEventHandler()
    
    publisher.register("ResourceStateChangedEvent", handler1)
    publisher.register("ResourceStateChangedEvent", handler2)
    
    event = ResourceStateChangedEvent(
        old_state="pending",
        new_state="running",
        resource_id="test-123",
        resource_type="TestResource"
    )

    # Act
    publisher.publish(event)

    # Assert
    assert len(handler1.received_events) == 1
    assert len(handler2.received_events) == 1

def test_event_publisher_multiple_events():
    # Arrange
    publisher = EventPublisher()
    handler = TestEventHandler()
    
    publisher.register("ResourceStateChangedEvent", handler)
    
    events = [
        ResourceStateChangedEvent(
            old_state="pending",
            new_state="running",
            resource_id="test-123",
            resource_type="TestResource"
        ),
        ResourceStateChangedEvent(
            old_state="running",
            new_state="stopped",
            resource_id="test-123",
            resource_type="TestResource"
        )
    ]

    # Act
    publisher.publish_all(events)

    # Assert
    assert len(handler.received_events) == 2

def test_event_publisher_handler_error():
    # Arrange
    publisher = EventPublisher()
    
    class ErrorHandler(EventHandler):
        def handle(self, event):
            raise Exception("Handler error")
    
    handler = ErrorHandler()
    publisher.register("ResourceStateChangedEvent", handler)
    
    event = ResourceStateChangedEvent(
        old_state="pending",
        new_state="running",
        resource_id="test-123",
        resource_type="TestResource"
    )

    # Act & Assert
    # Should not raise exception
    publisher.publish(event)
