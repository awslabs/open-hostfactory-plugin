"""Base DTO class with stable API and clean snake_case format."""
from typing import Dict, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, ConfigDict


class BaseDTO(BaseModel):
    """
    Base class for all DTOs with stable API and clean snake_case format.
    
    This class provides a future-proof abstraction layer that:
    - Uses pure snake_case internally (Pythonic)
    - Provides stable to_dict()/from_dict() API
    - Abstracts away Pydantic implementation details
    - Allows easy framework switching if needed
    
    External format conversion (camelCase) is handled at scheduler strategy level.
    """
    model_config = ConfigDict(
        frozen=True
        # Removed: alias_generator=to_camel (camelCase pollution)
        # Removed: populate_by_name=True (not needed without aliases)
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Stable public API - returns clean snake_case dictionary.
        
        This method provides a stable interface that abstracts away the underlying
        serialization framework. External format conversion (camelCase) should be
        handled at the scheduler strategy level, not here.
        
        Returns:
            Dict with snake_case keys (Pythonic format)
        """
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseDTO':
        """
        Stable public API - creates instance from snake_case dictionary.
        
        This method provides a stable interface that abstracts away the underlying
        serialization framework.
        
        Args:
            data: Dictionary with snake_case keys
            
        Returns:
            New instance of the DTO
        """
        return cls.model_validate(data)
    
    @staticmethod
    def serialize_enum(value: Union[Enum, str, None]) -> Optional[str]:
        """
        Serialize enum to string value.
        
        Args:
            value: Enum, string, or None value
            
        Returns:
            String representation or None
        """
        if value is None:
            return None
        if isinstance(value, Enum):
            return value.value
        return str(value)


# CQRS Base Classes

class BaseCommand(BaseDTO):
    """Base class for command DTOs."""
    command_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    dry_run: bool = False  # Enable dry-run mode for testing without real resource creation


class BaseQuery(BaseDTO):
    """Base class for query DTOs."""
    query_id: Optional[str] = None
    correlation_id: Optional[str] = None
    filters: Dict[str, Any] = {}
    pagination: Optional[Dict[str, Any]] = None


class BaseResponse(BaseDTO):
    """Base class for response DTOs."""
    success: bool = True
    message: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = {}


class PaginatedResponse(BaseResponse):
    """Base class for paginated responses."""
    total_count: int = 0
    page: int = 1
    page_size: int = 50
    has_next: bool = False
    has_previous: bool = False
