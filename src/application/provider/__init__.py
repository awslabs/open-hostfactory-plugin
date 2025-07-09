"""Provider Strategy Application Layer - CQRS commands and queries for provider operations.

This package provides CQRS integration for the provider strategy pattern,
enabling runtime provider selection, health monitoring, and multi-cloud operations
through clean command/query interfaces.
"""

from .commands import (
    SelectProviderStrategyCommand,
    ExecuteProviderOperationCommand,
    RegisterProviderStrategyCommand,
    UpdateProviderHealthCommand,
    ConfigureProviderStrategyCommand
)

from .queries import (
    GetProviderHealthQuery,
    ListAvailableProvidersQuery,
    GetProviderCapabilitiesQuery,
    GetProviderMetricsQuery,
    GetProviderStrategyConfigQuery
)

__all__ = [
    # Commands
    "SelectProviderStrategyCommand",
    "ExecuteProviderOperationCommand", 
    "RegisterProviderStrategyCommand",
    "UpdateProviderHealthCommand",
    "ConfigureProviderStrategyCommand",
    
    # Queries
    "GetProviderHealthQuery",
    "ListAvailableProvidersQuery",
    "GetProviderCapabilitiesQuery",
    "GetProviderMetricsQuery",
    "GetProviderStrategyConfigQuery"
]
