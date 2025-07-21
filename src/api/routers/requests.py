"""Request management API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.api.dependencies import get_request_status_handler, get_return_requests_handler
from src.infrastructure.error.decorators import handle_rest_exceptions

router = APIRouter(prefix="/requests", tags=["Requests"])


@router.get(
    "/{request_id}/status",
    summary="Get Request Status",
    description="Get status of a specific request",
)
@handle_rest_exceptions(endpoint="/api/v1/requests/{request_id}/status", method="GET")
async def get_request_status(
    request_id: str, handler=Depends(get_request_status_handler())
) -> JSONResponse:
    """
    Get the status of a specific request.

    - **request_id**: Request identifier
    """
    result = await handler.handle(
        request_id=request_id,
        context={"endpoint": f"/requests/{request_id}/status", "method": "GET"},
    )

    return JSONResponse(content=result)


@router.get("/", summary="List Requests", description="List requests with optional filtering")
@handle_rest_exceptions(endpoint="/api/v1/requests", method="GET")
async def list_requests(
    status: Optional[str] = Query(None, description="Filter by request status"),
    limit: Optional[int] = Query(None, description="Limit number of results"),
    handler=Depends(get_return_requests_handler()),
) -> JSONResponse:
    """
    List requests with optional filtering.

    - **status**: Filter by request status (pending, running, complete, failed)
    - **limit**: Limit number of results
    """
    result = await handler.handle(
        status=status, limit=limit, context={"endpoint": "/requests", "method": "GET"}
    )

    return JSONResponse(content=result)


@router.get(
    "/{request_id}",
    summary="Get Request Details",
    description="Get detailed information about a request",
)
@handle_rest_exceptions(endpoint="/api/v1/requests/{request_id}", method="GET")
async def get_request_details(
    request_id: str, handler=Depends(get_request_status_handler())
) -> JSONResponse:
    """
    Get detailed information about a specific request.

    - **request_id**: Request identifier
    """
    result = await handler.handle(
        request_id=request_id, context={"endpoint": f"/requests/{request_id}", "method": "GET"}
    )

    return JSONResponse(content=result)
