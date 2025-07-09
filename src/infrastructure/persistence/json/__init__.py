"""JSON persistence package."""
from src.infrastructure.persistence.json.template import JSONTemplateRepositoryImpl
from src.infrastructure.persistence.json.unit_of_work import JSONUnitOfWork

__all__ = [
    'JSONTemplateRepositoryImpl',
    'JSONUnitOfWork'
]

# Backward compatibility alias
JSONTemplateRepository = JSONTemplateRepositoryImpl
