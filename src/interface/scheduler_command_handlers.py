"""Scheduler-related command handlers for the interface layer."""

from __future__ import annotations

from typing import Any, Dict

from src.domain.base.ports.scheduler_port import SchedulerPort
from src.infrastructure.di.buses import QueryBus
from src.infrastructure.di.container import get_container
from src.infrastructure.error.decorators import handle_interface_exceptions


@handle_interface_exceptions(context="list_scheduler_strategies", interface_type="cli")
async def handle_list_scheduler_strategies(args) -> Dict[str, Any]:
    """
    Handle list scheduler strategies operations.

    Args:
        args: Modern argument namespace with resource/action structure

    Returns:
        Scheduler strategies list
    """
    container = get_container()
    query_bus = container.get(QueryBus)
    scheduler_strategy = container.get(SchedulerPort)

    from src.application.queries.system import ListSchedulerStrategiesQuery

    query = ListSchedulerStrategiesQuery()
    strategies = await query_bus.execute(query)

    return {
        "strategies": strategies,
        "count": len(strategies),
        "message": "Scheduler strategies retrieved successfully",
    }


@handle_interface_exceptions(context="show_scheduler_config", interface_type="cli")
async def handle_show_scheduler_config(args) -> Dict[str, Any]:
    """
    Handle show scheduler configuration operations.

    Args:
        args: Modern argument namespace with resource/action structure

    Returns:
        Scheduler configuration
    """
    container = get_container()
    query_bus = container.get(QueryBus)

    from src.application.queries.system import GetSchedulerConfigurationQuery

    query = GetSchedulerConfigurationQuery()
    config = await query_bus.execute(query)

    return {
        "config": config,
        "message": "Scheduler configuration retrieved successfully",
    }


@handle_interface_exceptions(context="validate_scheduler_config", interface_type="cli")
async def handle_validate_scheduler_config(args) -> Dict[str, Any]:
    """
    Handle validate scheduler configuration operations.

    Args:
        args: Modern argument namespace with resource/action structure

    Returns:
        Validation results
    """
    container = get_container()
    query_bus = container.get(QueryBus)

    from src.application.queries.system import ValidateSchedulerConfigurationQuery

    query = ValidateSchedulerConfigurationQuery()
    validation = await query_bus.execute(query)

    return {
        "validation": validation,
        "message": "Scheduler configuration validated successfully",
    }
