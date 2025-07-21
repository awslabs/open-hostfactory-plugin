"""Base models for API requests and responses."""

from typing import Dict, Any, Optional, List, Type, TypeVar, Generic
from pydantic import BaseModel, Field, ConfigDict, create_model

T = TypeVar("T")


class APIBaseModel(BaseModel):
    """Base model for all API models with automatic validation."""

    model_config = ConfigDict(
        frozen=True,
        populate_by_name=True,  # Allow populating by field name (snake_case)
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,  # Validate assignments
    )


class APIRequest(APIBaseModel):
    """Base model for all API requests."""


class APIResponse(APIBaseModel):
    """Base model for all API responses."""

    message: Optional[str] = None


class PaginatedResponse(APIResponse, Generic[T]):
    """Base model for paginated responses."""

    items: List[T]
    total_count: int
    page: int = 1
    page_size: int
    has_more: bool = False


class ErrorDetail(APIBaseModel):
    """Error detail model."""

    code: str
    message: str
    category: str
    details: Dict[str, Any] = Field(default_factory=dict)


def format_api_error_response(error_detail: ErrorDetail, status: int) -> Dict[str, Any]:
    """
    Format API error response.

    Replaces the duplicate ErrorResponse class with a function-based approach
    that uses the infrastructure error response as the source of truth.
    """
    return {
        "error": {
            "code": error_detail.code,
            "message": error_detail.message,
            "category": error_detail.category,
            "details": error_detail.details,
        },
        "status": status,
    }


def create_request_model(
    name: str,
    fields: Dict[str, Any],
    description: Optional[str] = None,
    base_class: Type = APIRequest,
) -> Type[APIRequest]:
    """
    Create a request model dynamically.

    Args:
        name: Name of the model
        fields: Fields to include in the model
        description: Optional description of the model
        base_class: Optional base class for the model

    Returns:
        Created model class
    """
    model = create_model(name, __base__=base_class, **fields)

    # Add description if provided
    if description:
        model.__doc__ = description

    return model


def create_response_model(
    name: str,
    fields: Dict[str, Any],
    description: Optional[str] = None,
    base_class: Type = APIResponse,
) -> Type[APIResponse]:
    """
    Create a response model dynamically.

    Args:
        name: Name of the model
        fields: Fields to include in the model
        description: Optional description of the model
        base_class: Optional base class for the model

    Returns:
        Created model class
    """
    model = create_model(name, __base__=base_class, **fields)

    # Add description if provided
    if description:
        model.__doc__ = description

    return model
