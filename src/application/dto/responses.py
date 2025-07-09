"""
Response DTOs for application layer.

This module re-exports the domain-specific DTOs to provide a unified interface
for the application layer. This follows the DRY principle by avoiding duplication
of DTO definitions.

IMPORTANT: Always import DTOs from this module rather than directly from domain-specific
modules to ensure consistent usage across the application. This allows us to:
1. Change the implementation details without affecting consumers
2. Add cross-cutting concerns like validation or serialization in one place
3. Maintain backward compatibility when refactoring
"""
from __future__ import annotations

# Import base DTO class
from src.application.dto.base import BaseDTO

# Import domain-specific DTOs
from src.application.machine.dto import MachineDTO, MachineHealthDTO
from src.application.request.dto import (
    RequestDTO, 
    RequestStatusResponse, 
    ReturnRequestResponse,
    RequestMachinesResponse,
    RequestReturnMachinesResponse,
    CleanupResourcesResponse,
    RequestSummaryDTO
)
from src.application.template.dto import TemplateDTO, TemplateListResponse

__all__ = [
    'BaseDTO',
    'MachineDTO',
    'RequestDTO',
    'TemplateDTO',
    'TemplateListResponse',
    'RequestSummaryDTO',
    'MachineHealthDTO',
    'RequestStatusResponse',
    'ReturnRequestResponse',
    'RequestMachinesResponse',
    'RequestReturnMachinesResponse',
    'CleanupResourcesResponse'
]
