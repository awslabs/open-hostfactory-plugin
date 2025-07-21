"""Exception context management."""

import threading
from typing import Dict, Any
from datetime import datetime


class ExceptionContext:
    """Rich context information for exception handling."""

    def __init__(self, operation: str, layer: str = "application", **additional_context):
        self.operation = operation
        self.layer = layer
        self.timestamp = datetime.utcnow()
        self.thread_id = threading.get_ident()
        self.additional_context = additional_context

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging."""
        return {
            "operation": self.operation,
            "layer": self.layer,
            "timestamp": self.timestamp.isoformat(),
            "thread_id": self.thread_id,
            **self.additional_context,
        }
