from src.domain.core.exceptions import DomainException, ResourceNotFoundError
from typing import Dict

class TemplateNotFoundError(ResourceNotFoundError):
    """Raised when a template cannot be found."""
    def __init__(self, template_id: str):
        super().__init__("Template", template_id)

class TemplateValidationError(DomainException):
    """Raised when template validation fails."""
    def __init__(self, template_id: str, errors: Dict[str, str]):
        message = f"Template validation failed for {template_id}: {', '.join(f'{k}: {v}' for k, v in errors.items())}"
        super().__init__(message)
        self.template_id = template_id
        self.errors = errors
