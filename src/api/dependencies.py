"""FastAPI dependency injection integration."""
from typing import Any, Type, TypeVar
from fastapi import Depends

from src.infrastructure.di.container import get_container
from src.infrastructure.di.buses import QueryBus, CommandBus
from src.config.manager import ConfigurationManager
from src.config.schemas.server_schema import ServerConfig

T = TypeVar('T')


def get_di_container():
    """Get the DI container instance."""
    return get_container()


def get_service(service_type: Type[T]) -> T:
    """
    Generic dependency for getting services from DI container.
    
    Args:
        service_type: Type of service to retrieve
        
    Returns:
        Service instance from DI container
    """
    def _get_service(container = Depends(get_di_container)) -> T:
        return container.get(service_type)
    
    return _get_service


def get_query_bus(container = Depends(get_di_container)) -> QueryBus:
    """Get QueryBus from DI container."""
    return container.get(QueryBus)


def get_command_bus(container = Depends(get_di_container)) -> CommandBus:
    """Get CommandBus from DI container."""
    return container.get(CommandBus)


def get_config_manager(container = Depends(get_di_container)) -> ConfigurationManager:
    """Get ConfigurationManager from DI container."""
    return container.get(ConfigurationManager)


def get_server_config(config_manager: ConfigurationManager = Depends(get_config_manager)) -> ServerConfig:
    """Get ServerConfig from configuration manager."""
    return config_manager.get_typed(ServerConfig)


# API Handler Dependencies
def get_template_handler():
    """Get template API handler from DI container."""
    def _get_handler(container = Depends(get_di_container)):
        from src.api.handlers.get_available_templates_handler import GetAvailableTemplatesRESTHandler
        return container.get(GetAvailableTemplatesRESTHandler)
    return _get_handler


def get_request_machines_handler():
    """Get request machines API handler from DI container."""
    def _get_handler(container = Depends(get_di_container)):
        from src.api.handlers.request_machines_handler import RequestMachinesRESTHandler
        return container.get(RequestMachinesRESTHandler)
    return _get_handler


def get_request_status_handler():
    """Get request status API handler from DI container."""
    def _get_handler(container = Depends(get_di_container)):
        from src.api.handlers.get_request_status_handler import GetRequestStatusRESTHandler
        return container.get(GetRequestStatusRESTHandler)
    return _get_handler


def get_return_requests_handler():
    """Get return requests API handler from DI container."""
    def _get_handler(container = Depends(get_di_container)):
        from src.api.handlers.get_return_requests_handler import GetReturnRequestsRESTHandler
        return container.get(GetReturnRequestsRESTHandler)
    return _get_handler


def get_return_machines_handler():
    """Get return machines API handler from DI container."""
    def _get_handler(container = Depends(get_di_container)):
        from src.api.handlers.request_return_machines_handler import RequestReturnMachinesRESTHandler
        return container.get(RequestReturnMachinesRESTHandler)
    return _get_handler
