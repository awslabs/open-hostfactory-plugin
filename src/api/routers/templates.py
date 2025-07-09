"""Template management API routes."""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.api.dependencies import get_template_handler
from src.infrastructure.error.decorators import handle_rest_exceptions

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("/", summary="List Templates", description="Get all available templates")
@handle_rest_exceptions(endpoint="/api/v1/templates", method="GET")
async def list_templates(
    all_flag: bool = Query(False, alias="all", description="Include all templates (including inactive)"),
    long: bool = Query(False, description="Include detailed template information"),
    clean: bool = Query(False, description="Return clean output format"),
    handler = Depends(get_template_handler())
) -> JSONResponse:
    """
    List all available templates.
    
    - **all**: Include inactive templates
    - **long**: Include detailed configuration
    - **clean**: Clean output format
    """
    result = await handler.handle(
        all_flag=all_flag,
        long=long,
        clean=clean,
        context={"endpoint": "/templates", "method": "GET"}
    )
    
    return JSONResponse(content=result)


@router.get("/{template_id}", summary="Get Template", description="Get specific template by ID")
@handle_rest_exceptions(endpoint="/api/v1/templates/{template_id}", method="GET")
async def get_template(
    template_id: str,
    long: bool = Query(False, description="Include detailed template information"),
    handler = Depends(get_template_handler())
) -> JSONResponse:
    """
    Get a specific template by ID.
    
    - **template_id**: Template identifier
    - **long**: Include detailed configuration
    """
    # Use the existing handler with template filtering
    result = await handler.handle(
        all_flag=True,  # Get all templates first
        long=long,
        clean=False,
        context={"endpoint": f"/templates/{template_id}", "method": "GET", "template_id": template_id}
    )
    
    # Filter for specific template
    if "data" in result and "templates" in result["data"]:
        templates = result["data"]["templates"]
        filtered_templates = [t for t in templates if t.get("id") == template_id or t.get("name") == template_id]
        
        if not filtered_templates:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "TEMPLATE_NOT_FOUND",
                    "message": f"Template '{template_id}' not found",
                    "category": "template_not_found"
                }
            )
        
        result["data"]["templates"] = filtered_templates
        result["data"]["count"] = len(filtered_templates)
    
    return JSONResponse(content=result)
