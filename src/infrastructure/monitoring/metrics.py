# src/helpers/metrics.py
from typing import Dict, Any, Optional, List
import time
import logging
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MetricData:
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str]

class MetricsCollector:
    """Collector for application metrics."""

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._metrics = []

    def start_timer(self) -> float:
        """Start a timer for performance measurement."""
        return time.time()

    def record_success(self, 
                      operation: str, 
                      start_time: Optional[float],
                      tags: Optional[Dict[str, str]] = None) -> None:
        """Record successful operation metrics."""
        if start_time:
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            self._record_metric(f"{operation}_duration", duration, tags)
        
        self._record_metric(f"{operation}_success", 1, tags)

    def record_error(self, 
                    operation: str, 
                    start_time: Optional[float],
                    tags: Optional[Dict[str, str]] = None) -> None:
        """Record error metrics."""
        if start_time:
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            self._record_metric(f"{operation}_error_duration", duration, tags)
        
        self._record_metric(f"{operation}_error", 1, tags)

    def _record_metric(self, 
                      name: str, 
                      value: float, 
                      tags: Optional[Dict[str, str]] = None) -> None:
        """Record a metric."""
        metric = MetricData(
            name=name,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags or {}
        )
        self._metrics.append(metric)
        self._logger.debug(f"Recorded metric: {metric}")

    def get_metrics(self) -> List[MetricData]:
        """Get all recorded metrics."""
        return self._metrics.copy()

    def clear_metrics(self) -> None:
        """Clear all recorded metrics."""
        self._metrics.clear()