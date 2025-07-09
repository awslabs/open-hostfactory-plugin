"""Base DTO class with automatic camelCase conversion."""
from typing import Dict, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, ConfigDict

def to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

class BaseDTO(BaseModel):
    """Base class for all DTOs with automatic camelCase conversion."""
    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True,  # Allow populating by field name (snake_case)
    )
    
    def model_dump_camel(self, exclude_none: bool = True) -> Dict[str, Any]:
        """Convert to dictionary with camelCase keys using Pydantic's built-in alias system."""
        return self.model_dump(by_alias=True, exclude_none=exclude_none)
    
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Legacy method for compatibility."""
        return self.model_dump_camel()
    
    # Keep the old methods for compatibility with code that might use them directly
    def _to_camel_case(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert dictionary keys from snake_case to camelCase."""
        result = {}
        for key, value in data.items():
            # Convert key to camelCase
            camel_key = self._snake_to_camel(key)
            
            # Handle nested dictionaries
            if isinstance(value, dict):
                result[camel_key] = self._to_camel_case(value)
            # Handle lists of dictionaries
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                result[camel_key] = [self._to_camel_case(item) if isinstance(item, dict) else item for item in value]
            else:
                result[camel_key] = value
                
        return result
    
    @staticmethod
    def _snake_to_camel(snake_str: str) -> str:
        """Convert snake_case string to camelCase."""
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])


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
