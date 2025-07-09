"""Template-related command handlers for the interface layer - Updated for new CQRS system."""
from __future__ import annotations
from typing import Dict, Any, TYPE_CHECKING

from src.application.base.command_handler import CLICommandHandler
from src.infrastructure.di.buses import QueryBus, CommandBus
from src.application.template.format_service import TemplateFormatService
from src.application.dto.responses import TemplateListResponse
from src.application.dto.queries import ListTemplatesQuery
from src.infrastructure.di.container import get_container


class GetAvailableTemplatesCLIHandler(CLICommandHandler):
    """Handler for getAvailableTemplates command."""
    
    def __init__(self, query_bus: QueryBus, command_bus: CommandBus, 
                 format_service: TemplateFormatService, logger=None):
        """Initialize handler with injected dependencies.
        
        Args:
            query_bus: Query bus for executing queries (injected)
            command_bus: Command bus for executing commands (injected)
            format_service: Template format service for conversions (injected)
            logger: Logger instance for logging operations
            
        Note:
            Now uses constructor injection instead of service locator pattern.
            All dependencies are explicitly provided via constructor.
        """
        super().__init__(query_bus=query_bus, command_bus=command_bus, logger=logger)
        self.format_service = format_service
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle getAvailableTemplates command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Available templates information
        """
        # Execute via new CQRS system
        self.logger.debug("Getting available templates")
        
        # Create query using new CQRS system
        query = ListTemplatesQuery(
            active_only=not (hasattr(command, 'all') and command.all),
            include_configuration=hasattr(command, 'long') and command.long
        )
        
        # Execute through injected CQRS QueryBus
        templates = self._query_bus.execute(query)
        
        # Apply field filtering based on --long flag
        include_full_config = hasattr(command, 'long') and command.long
        use_camel_case = False  # CLI uses snake_case by default
        
        if self.format_service:
            result = self.format_service.convert_templates(
                templates, 
                include_full_config=include_full_config,
                use_camel_case=use_camel_case
            )
        else:
            # Fallback if format service not available
            response = TemplateListResponse(templates=templates)
            result = response.to_dict()
        
        return result
    
    def handle_with_legacy_format(self, command) -> Dict[str, Any]:
        """
        Handle getAvailableTemplates command with legacy camelCase format.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Available templates information in camelCase format
        """
        # Execute via new CQRS system
        self.logger.debug("Getting available templates (legacy format)")
        
        # Create query using new CQRS system
        query = ListTemplatesQuery(
            active_only=not (hasattr(command, 'all') and command.all),
            include_configuration=hasattr(command, 'long') and command.long
        )
        
        # Execute through injected CQRS QueryBus
        templates = self._query_bus.execute(query)
        
        # Apply field filtering and legacy format conversion
        include_full_config = hasattr(command, 'long') and command.long
        use_camel_case = True  # Legacy format uses camelCase
        
        if self.format_service:
            result = self.format_service.convert_templates(
                templates,
                include_full_config=include_full_config,
                use_camel_case=use_camel_case
            )
        else:
            # Fallback to direct response (shouldn't happen)
            response = TemplateListResponse(templates=templates)
            result = response.to_dict()
        
        return result
