"""Template application context - template use cases."""

from .commands import (
    CreateTemplateCommand,
    UpdateTemplateCommand,
    DeleteTemplateCommand,
    ValidateTemplateCommand,
    TemplateCommandResponse,
)

# Import queries from the unified dto.queries module
from src.application.dto.queries import GetTemplateQuery, ListTemplatesQuery, ValidateTemplateQuery

__all__ = [
    # Commands
    "CreateTemplateCommand",
    "UpdateTemplateCommand",
    "DeleteTemplateCommand",
    "ValidateTemplateCommand",
    "TemplateCommandResponse",
    # Queries
    "GetTemplateQuery",
    "ListTemplatesQuery",
    "ValidateTemplateQuery",
]
