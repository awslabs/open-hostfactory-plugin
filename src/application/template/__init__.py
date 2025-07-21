"""Template application context - template use cases."""

# Import queries from the unified dto.queries module
from src.application.dto.queries import (
    GetTemplateQuery,
    ListTemplatesQuery,
    ValidateTemplateQuery,
)

from .commands import (
    CreateTemplateCommand,
    DeleteTemplateCommand,
    TemplateCommandResponse,
    UpdateTemplateCommand,
    ValidateTemplateCommand,
)

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
