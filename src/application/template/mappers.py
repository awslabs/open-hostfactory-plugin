"""Template DTO mappers for converting between layers."""
from typing import List
from src.infrastructure.template.dtos import TemplateDTO as InfraTemplateDTO
from src.application.template.dto import TemplateDTO as AppTemplateDTO


class TemplateDTOMapper:
    """Maps between infrastructure and application TemplateDTO objects."""
    
    @staticmethod
    def infrastructure_to_application(infra_dto: InfraTemplateDTO) -> AppTemplateDTO:
        """Convert infrastructure TemplateDTO to application TemplateDTO.
        
        Args:
            infra_dto: Infrastructure layer TemplateDTO
            
        Returns:
            Application layer TemplateDTO (Pydantic)
        """
        return AppTemplateDTO(
            template_id=infra_dto.template_id,
            name=infra_dto.name,
            description=None,  # Not available in infrastructure DTO
            
            # Instance configuration - extract from configuration dict
            instance_type=infra_dto.configuration.get('instance_type'),
            image_id=infra_dto.configuration.get('image_id'),
            max_instances=infra_dto.configuration.get('max_instances', 1),
            
            # Network configuration - extract from configuration dict
            subnet_ids=infra_dto.configuration.get('subnet_ids', []),
            security_group_ids=infra_dto.configuration.get('security_group_ids', []),
            
            # Provider configuration
            provider_api=infra_dto.provider_api,
            provider_config=infra_dto.configuration,
            
            # Metadata
            version=infra_dto.version,
            tags=infra_dto.tags or {},  # Convert None to empty dict
            
            # Status and timestamps
            is_active=True,  # Assume active if in infrastructure
            created_at=infra_dto.created_at,
            updated_at=infra_dto.updated_at,
        )
    
    @staticmethod
    def infrastructure_list_to_application(infra_dtos: List[InfraTemplateDTO]) -> List[AppTemplateDTO]:
        """Convert list of infrastructure TemplateDTOs to application TemplateDTOs.
        
        Args:
            infra_dtos: List of infrastructure layer TemplateDTOs
            
        Returns:
            List of application layer TemplateDTOs (Pydantic)
        """
        return [
            TemplateDTOMapper.infrastructure_to_application(infra_dto)
            for infra_dto in infra_dtos
        ]
    
    @staticmethod
    def application_to_infrastructure(app_dto: AppTemplateDTO) -> InfraTemplateDTO:
        """Convert application TemplateDTO to infrastructure TemplateDTO.
        
        Args:
            app_dto: Application layer TemplateDTO
            
        Returns:
            Infrastructure layer TemplateDTO (dataclass)
        """
        # Build configuration dict from application DTO fields
        configuration = app_dto.provider_config.copy() if app_dto.provider_config else {}
        
        # Add instance configuration to config dict
        if app_dto.instance_type:
            configuration['instance_type'] = app_dto.instance_type
        if app_dto.image_id:
            configuration['image_id'] = app_dto.image_id
        if app_dto.max_instances:
            configuration['max_instances'] = app_dto.max_instances
        if app_dto.subnet_ids:
            configuration['subnet_ids'] = app_dto.subnet_ids
        if app_dto.security_group_ids:
            configuration['security_group_ids'] = app_dto.security_group_ids
        
        return InfraTemplateDTO(
            template_id=app_dto.template_id,
            name=app_dto.name or app_dto.template_id,  # Fallback to template_id if name is None
            provider_api=app_dto.provider_api or 'aws',  # Default provider
            configuration=configuration,
            created_at=app_dto.created_at,
            updated_at=app_dto.updated_at,
            version=app_dto.version,
            tags=app_dto.tags,
        )
