"""API models package."""

from src.api.models.base import (
    APIBaseModel,
    APIRequest,
    APIResponse,
    PaginatedResponse,
    ErrorDetail,
    format_api_error_response,
    create_request_model,
    create_response_model,
)
from src.api.models.responses import (
    SuccessResponse,
    format_error_for_api,
    format_success_for_api,
    create_error_response,
)
from src.api.models.requests import (
    BaseRequestModel,
    MachineReferenceModel,
    RequestMachinesModel,
    RequestStatusModel,
    RequestReturnMachinesModel,
    GetReturnRequestsModel,
)

__all__ = [
    # Base models
    "APIBaseModel",
    "APIRequest",
    "APIResponse",
    "PaginatedResponse",
    "ErrorDetail",
    "format_api_error_response",
    "create_request_model",
    "create_response_model",
    # Request models
    "BaseRequestModel",
    "MachineReferenceModel",
    "RequestMachinesModel",
    "RequestStatusModel",
    "RequestReturnMachinesModel",
    "GetReturnRequestsModel",
    # Response models
    "SuccessResponse",
    "format_error_for_api",
    "format_success_for_api",
    "create_error_response",
]
