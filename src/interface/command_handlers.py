"""Command handlers orchestrator for the interface layer.

This module provides a unified interface to all command handlers organized by responsibility:
- Template operations (handle_list_templates, handle_get_template, etc.)
- Request operations (handle_get_request_status, handle_request_machines, etc.)
- Storage operations (handle_list_storage_strategies, etc.)
- Scheduler operations (handle_list_scheduler_strategies, etc.)
- System operations (handle_provider_health, etc.)
"""

# Import base handler
from src.application.base.command_handler import CLICommandHandler

# Import specialized handlers by category
from src.interface.template_command_handlers import (
    handle_list_templates,
    handle_get_template,
    handle_validate_template,
)

from src.interface.request_command_handlers import (
    handle_get_request_status,
    handle_request_machines,
    handle_get_return_requests,
    handle_request_return_machines,
)

from src.interface.system_command_handlers import (
    handle_provider_health,
    handle_list_providers,
    handle_provider_config,
    handle_validate_provider_config,
    handle_reload_provider_config,
    handle_select_provider_strategy,
    handle_execute_provider_operation,
    handle_provider_metrics,
)

from src.interface.storage_command_handlers import (
    handle_list_storage_strategies,
    handle_show_storage_config,
    handle_validate_storage_config,
    handle_test_storage,
    handle_storage_health,
    handle_storage_metrics,
)

from src.interface.scheduler_command_handlers import (
    handle_list_scheduler_strategies,
    handle_show_scheduler_config,
    handle_validate_scheduler_config,
)

__all__ = [
    # Base handler
    "CLICommandHandler",
    # Template handlers (function-based)
    "handle_list_templates",
    "handle_get_template",
    "handle_validate_template",
    # Request handlers (function-based)
    "handle_get_request_status",
    "handle_request_machines",
    "handle_get_return_requests",
    "handle_request_return_machines",
    # System handlers (function-based)
    "handle_provider_health",
    "handle_list_providers",
    "handle_provider_config",
    "handle_validate_provider_config",
    "handle_reload_provider_config",
    "handle_select_provider_strategy",
    "handle_execute_provider_operation",
    "handle_provider_metrics",
    # Storage handlers (function-based)
    "handle_list_storage_strategies",
    "handle_show_storage_config",
    "handle_validate_storage_config",
    "handle_test_storage",
    "handle_storage_health",
    "handle_storage_metrics",
    # Scheduler handlers (function-based)
    "handle_list_scheduler_strategies",
    "handle_show_scheduler_config",
    "handle_validate_scheduler_config",
]
