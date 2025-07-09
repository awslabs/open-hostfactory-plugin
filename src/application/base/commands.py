"""Base command infrastructure - foundation for command processing."""
from typing import Protocol

from src.application.dto.base import BaseCommand, BaseResponse
from src.application.interfaces.command_handler import CommandHandler

__all__ = ['CommandHandler', 'CommandBus']


class CommandBus(Protocol):
    """Protocol for command bus."""
    
    async def send(self, command: BaseCommand) -> BaseResponse:
        """Send a command for processing."""
        ...
    
    def register_handler(self, command_type: type, handler: CommandHandler) -> None:
        """Register a command handler for a specific command type."""
        ...
        """Register a command handler."""
        ...
