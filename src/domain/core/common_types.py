# src/domain/core/common_types.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
import uuid

@dataclass(frozen=True)
class Timestamp:
    value: datetime

    @classmethod
    def now(cls) -> Timestamp:
        return cls(datetime.utcnow())

    def __str__(self) -> str:
        return self.value.isoformat()

@dataclass(frozen=True)
class ResourceId:
    """Base class for all resource identifiers."""
    value: str

    def __str__(self) -> str:
        return self.value

@dataclass(frozen=True)
class Tag:
    key: str
    value: str

    def __str__(self) -> str:
        return f"{self.key}={self.value}"

    @classmethod
    def from_dict(cls, data: dict) -> Tag:
        return cls(key=data["Key"], value=data["Value"])

    def to_dict(self) -> dict:
        return {"Key": self.key, "Value": self.value}

@dataclass(frozen=True)
class Tags:
    """Collection of tags with helper methods."""
    items: Dict[str, str] = field(default_factory=dict)

    def add(self, key: str, value: str) -> Tags:
        new_items = self.items.copy()
        new_items[key] = value
        return Tags(new_items)

    def remove(self, key: str) -> Tags:
        new_items = self.items.copy()
        new_items.pop(key, None)
        return Tags(new_items)

    def get(self, key: str) -> Optional[str]:
        return self.items.get(key)

    def to_dict(self) -> Dict[str, str]:
        return self.items.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> Tags:
        return cls(items=data.copy())

    def to_aws_format(self) -> List[Dict[str, str]]:
        """Convert tags to AWS API format."""
        return [{"Key": k, "Value": v} for k, v in self.items.items()]

    @classmethod
    def from_aws_format(cls, tags: List[Dict[str, str]]) -> Tags:
        """Create Tags from AWS API format."""
        return cls(items={t["Key"]: t["Value"] for t in tags})

    def __str__(self) -> str:
        return ";".join(f"{k}={v}" for k, v in self.items.items())

@dataclass(frozen=True)
class IPAddress:
    """Represents an IP address with validation."""
    value: str

    def __post_init__(self):
        self._validate()

    def _validate(self) -> None:
        parts = self.value.split('.')
        if len(parts) != 4:
            raise ValueError(f"Invalid IP address format: {self.value}")
        for part in parts:
            if not part.isdigit() or not 0 <= int(part) <= 255:
                raise ValueError(f"Invalid IP address value: {self.value}")

    def __str__(self) -> str:
        return self.value

class AWSResourceState(str, Enum):
    """Common AWS resource states."""
    PENDING = "pending"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    SHUTTING_DOWN = "shutting-down"
    TERMINATED = "terminated"
    UNKNOWN = "unknown"

    @classmethod
    def from_aws_state(cls, state: str) -> AWSResourceState:
        """Convert AWS API state to our domain state."""
        state_map = {
            "pending": cls.PENDING,
            "running": cls.RUNNING,
            "stopping": cls.STOPPING,
            "stopped": cls.STOPPED,
            "shutting-down": cls.SHUTTING_DOWN,
            "terminated": cls.TERMINATED
        }
        return state_map.get(state.lower(), cls.UNKNOWN)