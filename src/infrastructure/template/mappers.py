"""Template mappers for converting between domain aggregates and infrastructure DTOs."""
from typing import TYPE_CHECKING, List
from .dtos import TemplateDTO, TemplateValidationResultDTO

# Use TYPE_CHECKING to avoid direct domain imports
if TYPE_CHECKING:
    from src.domain.template.aggregate import Template


class TemplateMapper:
    """
    Mapper for converting between Template domain aggregate and TemplateDTO.
    
    Follows DIP by isolating domain dependencies through TYPE_CHECKING
    and providing clean conversion interface.
    """
    
    @staticmethod
    def to_dto(template: 'Template') -> TemplateDTO:
        """
        Convert Template domain aggregate to TemplateDTO.
        
        Args:
            template: Domain template aggregate
            
        Returns:
            TemplateDTO for infrastructure use
        """
        return TemplateDTO(
            template_id=template.template_id,
            name=template.name,
            provider_api=template.provider_api,
            configuration=template.configuration,
            created_at=getattr(template, 'created_at', None),
            updated_at=getattr(template, 'updated_at', None),
            version=getattr(template, 'version', None),
            tags=getattr(template, 'tags', None)
        )
    
    @staticmethod
    def from_dto(dto: TemplateDTO) -> 'Template':
        """
        Convert TemplateDTO to Template domain aggregate.
        
        Args:
            dto: Infrastructure TemplateDTO
            
        Returns:
            Template domain aggregate
        """
        # Import here to avoid circular dependencies
        from src.domain.template.aggregate import Template
        
        return Template(
            template_id=dto.template_id,
            name=dto.name,
            provider_api=dto.provider_api,
            configuration=dto.configuration
        )
    
    @staticmethod
    def to_dto_list(templates: List['Template']) -> List[TemplateDTO]:
        """Convert list of Template aggregates to DTOs."""
        return [TemplateMapper.to_dto(template) for template in templates]
    
    @staticmethod
    def from_dto_list(dtos: List[TemplateDTO]) -> List['Template']:
        """Convert list of TemplateDTO to Template aggregates."""
        return [TemplateMapper.from_dto(dto) for dto in dtos]


class TemplateValidationMapper:
    """Mapper for template validation results."""
    
    @staticmethod
    def create_validation_result(template_id: str, is_valid: bool, 
                               errors: List[str] = None, 
                               warnings: List[str] = None) -> TemplateValidationResultDTO:
        """Create validation result DTO."""
        return TemplateValidationResultDTO(
            template_id=template_id,
            is_valid=is_valid,
            errors=errors or [],
            warnings=warnings or []
        )
