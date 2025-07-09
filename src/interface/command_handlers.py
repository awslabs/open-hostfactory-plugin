"""Command handlers orchestrator for the interface layer.

This module provides a unified interface to all command handlers organized by responsibility:
- Template operations (GetAvailableTemplatesCLIHandler)
- Request operations (GetRequestStatusCLIHandler, RequestMachinesCLIHandler, etc.)
- System operations (MigrateRepositoryCLIHandler, GetProviderHealthCLIHandler, etc.)
"""

# Import base handler
from src.application.base.command_handler import CLICommandHandler

# Import specialized handlers by category
from src.interface.template_command_handlers import (
    GetAvailableTemplatesCLIHandler
)

from src.interface.request_command_handlers import (
    GetRequestStatusCLIHandler,
    RequestMachinesCLIHandler,
    GetReturnRequestsCLIHandler,
    RequestReturnMachinesCLIHandler
)

from src.interface.system_command_handlers import (
    MigrateRepositoryCLIHandler,
    GetProviderHealthCLIHandler,
    ListAvailableProvidersCLIHandler,
    GetProviderConfigCLIHandler,
    ValidateProviderConfigCLIHandler,
    ReloadProviderConfigCLIHandler,
    MigrateProviderConfigCLIHandler,
    SelectProviderStrategyCLIHandler,
    ExecuteProviderOperationCLIHandler,
    GetProviderMetricsCLIHandler
)

__all__ = [
    # Base handler
    'CLICommandHandler',
    
    # Template handlers
    'GetAvailableTemplatesCLIHandler',
    
    # Request handlers
    'GetRequestStatusCLIHandler',
    'RequestMachinesCLIHandler',
    'GetReturnRequestsCLIHandler',
    'RequestReturnMachinesCLIHandler',
    
    # System handlers
    'MigrateRepositoryCLIHandler',
    'GetProviderHealthCLIHandler',
    'ListAvailableProvidersCLIHandler',
    'GetProviderConfigCLIHandler',
    'ValidateProviderConfigCLIHandler',
    'ReloadProviderConfigCLIHandler',
    'MigrateProviderConfigCLIHandler',
    'SelectProviderStrategyCLIHandler',
    'ExecuteProviderOperationCLIHandler',
    'GetProviderMetricsCLIHandler'
]
