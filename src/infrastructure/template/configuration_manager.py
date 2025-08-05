"""Template Configuration Manager

Orchestrates template services while delegating to scheduler strategies.
Provides focused orchestration logic for template operations.

Architecture Principles:
- Delegates file operations to scheduler strategies
- Uses dedicated services for caching and persistence
- Maintains clean separation of concerns
- Preserves existing public interface
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.config.manager import ConfigurationManager
from src.domain.base.dependency_injection import injectable
from src.domain.base.exceptions import (
    DomainException,
    EntityNotFoundError,
    ValidationError,
)
from src.domain.base.ports.event_publisher_port import EventPublisherPort
from src.domain.base.ports.logging_port import LoggingPort
from src.domain.base.ports.scheduler_port import SchedulerPort

from .dtos import TemplateDTO
from .services.template_persistence_service import TemplatePersistenceService
from .template_cache_service import TemplateCacheService, create_template_cache_service


class TemplateConfigurationError(DomainException):
    """Base exception for template configuration errors."""


class TemplateNotFoundError(EntityNotFoundError):
    """Exception raised when a template is not found."""


class TemplateValidationError(ValidationError):
    """Exception raised when template validation fails."""


@injectable
class TemplateConfigurationManager:
    """
    Template Configuration Manager.

    This class orchestrates template operations by delegating to:
    - Scheduler strategies for file operations and field mapping
    - Cache service for performance optimization
    - Persistence service for CRUD operations
    - Template defaults service for hierarchical configuration

    Responsibilities:
    - Orchestrate template loading via scheduler strategy
    - Coordinate caching and persistence services
    - Provide unified template access interface
    - Handle template validation and events
    """

    def __init__(
        self,
        config_manager: ConfigurationManager,
        scheduler_strategy: SchedulerPort,
        logger: LoggingPort,
        cache_service: Optional[TemplateCacheService] = None,
        persistence_service: Optional[TemplatePersistenceService] = None,
        event_publisher: Optional[EventPublisherPort] = None,
        provider_capability_service: Optional["ProviderCapabilityService"] = None,
        template_defaults_service: Optional["TemplateDefaultsService"] = None,
    ):
        """
        Initialize the template configuration manager.

        Args:
            config_manager: Configuration manager for paths and settings
            scheduler_strategy: Strategy for file operations and field mapping
            logger: Logger for operations and debugging
            cache_service: Optional cache service (creates default if None)
            persistence_service: Optional persistence service (creates default if None)
            event_publisher: Optional event publisher for domain events
            provider_capability_service: Optional service for provider validation
            template_defaults_service: Optional service for template defaults
        """
        self.config_manager = config_manager
        self.scheduler_strategy = scheduler_strategy
        self.logger = logger
        self.event_publisher = event_publisher
        self.provider_capability_service = provider_capability_service
        self.template_defaults_service = template_defaults_service

        # Initialize services
        self.cache_service = cache_service or create_template_cache_service("ttl", logger)
        self.persistence_service = persistence_service or TemplatePersistenceService(
            scheduler_strategy, logger, event_publisher
        )

        self.logger.info("Template configuration manager initialized")

    async def load_templates(self, force_refresh: bool = False) -> List[TemplateDTO]:
        """
        Load all templates using cache service and scheduler strategy.

        Args:
            force_refresh: Force reload even if cached

        Returns:
            List of TemplateDTO objects
        """
        if force_refresh:
            self.cache_service.invalidate()

        def loader_func() -> List[TemplateDTO]:
            """Template loader function for cache service."""
            return self._load_templates_from_scheduler()

        templates = self.cache_service.get_or_load(loader_func)
        self.logger.info(f"Loaded {len(templates)} templates")
        return templates

    def _load_templates_from_scheduler(self) -> List[TemplateDTO]:
        """Load templates using scheduler strategy with batch AMI resolution."""
        try:
            # Get template file paths from scheduler strategy
            template_paths = self.scheduler_strategy.get_template_paths()
            if not template_paths:
                self.logger.warning("No template paths available from scheduler strategy")
                return []

            all_template_dicts = []

            # Load templates from each path
            for template_path in template_paths:
                try:
                    # Use scheduler strategy to load and parse templates
                    template_dicts = self.scheduler_strategy.load_templates_from_path(template_path)
                    all_template_dicts.extend(template_dicts)

                except Exception as e:
                    self.logger.error(f"Failed to load templates from {template_path}: {e}")
                    continue

            # Apply batch AMI resolution BEFORE converting to DTOs
            resolved_template_dicts = self._batch_resolve_amis(all_template_dicts)

            # Convert to DTOs with defaults applied
            all_templates = []
            for template_dict in resolved_template_dicts:
                try:
                    template_dto = self._convert_dict_to_template_dto(template_dict)
                    all_templates.append(template_dto)
                except Exception as e:
                    self.logger.warning(f"Failed to convert template dict to DTO: {e}")
                    continue

            self.logger.debug(f"Loaded {len(all_templates)} templates from scheduler strategy")
            return all_templates

        except Exception as e:
            self.logger.error(f"Failed to load templates from scheduler: {e}")
            return []

    def _convert_dict_to_template_dto(self, template_dict: Dict[str, Any]) -> TemplateDTO:
        """Convert template dictionary to TemplateDTO with defaults applied."""
        # Extract template ID (scheduler strategy should have normalized this)
        template_id = template_dict.get("template_id", template_dict.get("templateId", ""))

        if not template_id:
            raise ValueError("Template missing required template_id field")

        # Apply hierarchical defaults if service is available
        template_with_defaults = template_dict
        if self.template_defaults_service:
            # Determine provider instance for defaults
            provider_instance = self._determine_provider_instance(template_dict)
            template_with_defaults = self.template_defaults_service.resolve_template_defaults(
                template_dict, provider_instance
            )
            self.logger.debug(f"Applied defaults to template {template_id}")

        # AMI resolution is already done in _batch_resolve_amis, no need to do it again

        # Create TemplateDTO with defaults applied (AMI already resolved)
        return TemplateDTO(
            template_id=template_id,
            name=template_with_defaults.get("name", template_id),
            provider_api=template_with_defaults.get("provider_api", "EC2Fleet"),
            configuration=template_with_defaults,
            # Full configuration with defaults and AMI resolution
            created_at=template_with_defaults.get("created_at"),
            updated_at=template_with_defaults.get("updated_at"),
            version=template_with_defaults.get("version"),
            tags=template_with_defaults.get("tags", {}),
        )

    def _determine_provider_instance(self, template_dict: Dict[str, Any]) -> Optional[str]:
        """Determine which provider instance this template belongs to."""
        # 1. Check if template specifies provider instance
        if "provider_name" in template_dict:
            return template_dict["provider_name"]

        # 2. Use active provider from configuration
        try:
            provider_config = self.config_manager.get_provider_config()
            if hasattr(provider_config, "active_provider") and provider_config.active_provider:
                return provider_config.active_provider
        except Exception as e:
            self.logger.debug(f"Could not determine provider instance: {e}")

        # 3. Fallback to default
        return "aws"

    def _resolve_ami_if_enabled(self, template_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve AMI IDs from SSM parameters if AMI resolution is enabled."""
        try:
            # Check if AMI resolution is enabled
            if not self._is_ami_resolution_enabled():
                return template_dict

            # Get AMI resolver from DI container
            ami_resolver = self._get_ami_resolver()
            if not ami_resolver:
                return template_dict

            # Create a copy to avoid modifying original
            resolved_template = template_dict.copy()

            # Resolve image_id if it's an SSM parameter
            image_id = resolved_template.get("image_id") or resolved_template.get("imageId")
            if image_id and image_id.startswith("/aws/service/"):
                try:
                    resolved_ami = ami_resolver.resolve_with_fallback(image_id)
                    if resolved_ami != image_id:  # Only update if resolution succeeded
                        resolved_template["image_id"] = resolved_ami
                        if "imageId" in resolved_template:
                            resolved_template["imageId"] = resolved_ami
                        self.logger.info(f"Resolved SSM parameter {image_id} to AMI {resolved_ami}")
                except Exception as e:
                    self.logger.warning(f"Failed to resolve AMI parameter {image_id}: {e}")

            return resolved_template

        except Exception as e:
            self.logger.error(f"AMI resolution failed: {e}")
            return template_dict  # Return original on error

    def _is_ami_resolution_enabled(self) -> bool:
        """Check if AMI resolution is enabled."""
        try:
            provider_config = self.config_manager.get_provider_config()

            # Check AWS provider defaults
            if (
                hasattr(provider_config, "provider_defaults")
                and "aws" in provider_config.provider_defaults
            ):
                aws_defaults = provider_config.provider_defaults["aws"]
                if hasattr(aws_defaults, "extensions") and aws_defaults.extensions:
                    ami_resolution = aws_defaults.extensions.get("ami_resolution", {})
                    if isinstance(ami_resolution, dict) and ami_resolution.get("enabled"):
                        return True

            return False

        except Exception as e:
            self.logger.debug(f"Could not determine AMI resolution status: {e}")
            return False

    def _get_ami_resolver(self):
        """Get AMI resolver from DI container using port interface."""
        try:
            from src.infrastructure.di.container import get_container

            container = get_container()

            # Use port interface instead of concrete implementation
            from src.domain.base.ports.template_resolver_port import (
                TemplateResolverPort,
            )

            return container.get(TemplateResolverPort)

        except Exception as e:
            self.logger.debug(f"Could not get template resolver: {e}")
            return None

    def _batch_resolve_amis(self, template_dicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Batch resolve AMI IDs from SSM parameters to avoid duplicate calls."""
        try:
            # Check if AMI resolution is enabled
            if not self._is_ami_resolution_enabled():
                return template_dicts

            # Get AMI resolver
            ami_resolver = self._get_ami_resolver()
            if not ami_resolver:
                return template_dicts

            # Collect unique SSM parameters
            ssm_parameters = set()
            for template_dict in template_dicts:
                image_id = template_dict.get("image_id") or template_dict.get("imageId")
                if image_id and image_id.startswith("/aws/service/"):
                    ssm_parameters.add(image_id)

            if not ssm_parameters:
                return template_dicts  # No SSM parameters to resolve

            # Batch resolve all unique SSM parameters
            resolved_amis = {}
            for ssm_param in ssm_parameters:
                try:
                    resolved_ami = ami_resolver.resolve_with_fallback(ssm_param)
                    if resolved_ami != ssm_param:  # Only cache if resolution succeeded
                        resolved_amis[ssm_param] = resolved_ami
                except Exception as e:
                    self.logger.warning(f"Failed to resolve AMI parameter {ssm_param}: {e}")

            # Apply resolved AMIs to templates
            resolved_templates = []
            for template_dict in template_dicts:
                resolved_template = template_dict.copy()

                image_id = resolved_template.get("image_id") or resolved_template.get("imageId")
                if image_id and image_id in resolved_amis:
                    resolved_ami = resolved_amis[image_id]
                    resolved_template["image_id"] = resolved_ami
                    if "imageId" in resolved_template:
                        resolved_template["imageId"] = resolved_ami

                resolved_templates.append(resolved_template)

            self.logger.info(
                f"Batch resolved {
                    len(resolved_amis)} unique SSM parameters for {
                    len(template_dicts)} templates"
            )
            return resolved_templates

        except Exception as e:
            self.logger.error(f"Batch AMI resolution failed: {e}")
            return template_dicts  # Return original on error

    async def get_template_by_id(self, template_id: str) -> Optional[TemplateDTO]:
        """
        Get a specific template by ID.

        Args:
            template_id: Template identifier

        Returns:
            TemplateDTO if found, None otherwise

        Raises:
            TemplateConfigurationError: If template loading fails
            ValidationError: If template_id is invalid
        """
        try:
            # Validate input
            if not template_id or not isinstance(template_id, str):
                raise TemplateValidationError("Template ID must be a non-empty string")

            # Load templates (uses cache)
            templates = await self.load_templates()

            # Find template by ID
            for template in templates:
                if template.template_id == template_id:
                    self.logger.debug(f"Retrieved template {template_id}")
                    return template

            self.logger.debug(f"Template {template_id} not found")
            return None

        except TemplateValidationError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to get template {template_id}: {e}")
            raise TemplateConfigurationError(
                f"Failed to retrieve template {template_id}: {str(e)}"
            ) from e

    async def get_templates_by_provider(self, provider_api: str) -> List[TemplateDTO]:
        """
        Get templates filtered by provider API.

        Args:
            provider_api: Provider API identifier

        Returns:
            List of templates for the specified provider
        """
        templates = await self.load_templates()
        filtered_templates = [
            t for t in templates if getattr(t, "provider_api", None) == provider_api
        ]

        self.logger.debug(f"Found {len(filtered_templates)} templates for provider {provider_api}")
        return filtered_templates

    async def get_all_templates(self) -> List[TemplateDTO]:
        """Get all templates (alias for load_templates for compatibility)."""
        return await self.load_templates()

    def get_all_templates_sync(self) -> List[TemplateDTO]:
        """Get all templates synchronously for adapter compatibility."""
        import asyncio

        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we can't use run_until_complete
                # Fall back to direct template loading via scheduler strategy
                return self._load_templates_from_scheduler()
            else:
                return loop.run_until_complete(self.get_all_templates())
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(self.get_all_templates())

    async def save_template(self, template: TemplateDTO) -> None:
        """
        Save template using persistence service.

        Args:
            template: Template to save
        """
        try:
            await self.persistence_service.save_template(template)

            # Invalidate cache to ensure fresh data on next load
            self.cache_service.invalidate()

            self.logger.info(f"Saved template {template.template_id}")

        except Exception as e:
            self.logger.error(f"Failed to save template {template.template_id}: {e}")
            raise

    async def delete_template(self, template_id: str) -> None:
        """
        Delete template using persistence service.

        Args:
            template_id: Template identifier to delete
        """
        try:
            await self.persistence_service.delete_template(template_id)

            # Invalidate cache to ensure fresh data on next load
            self.cache_service.invalidate()

            self.logger.info(f"Deleted template {template_id}")

        except Exception as e:
            self.logger.error(f"Failed to delete template {template_id}: {e}")
            raise

    def get_template(self, template_id: str) -> Optional[TemplateDTO]:
        """Get template by ID synchronously for compatibility."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.get_template_by_id(template_id))
        except RuntimeError:
            # No event loop running, create new one
            return asyncio.run(self.get_template_by_id(template_id))

    async def validate_template(
        self, template: TemplateDTO, provider_instance: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate template configuration.

        Args:
            template: Template to validate
            provider_instance: Optional provider instance for capability validation

        Returns:
            Dictionary with validation results
        """
        validation_result = {
            "template_id": template.template_id,
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "supported_features": [],
            "validation_time": datetime.now(),
        }

        try:
            # Basic validation
            self._validate_basic_template_structure(template, validation_result)

            # Provider capability validation (if service available)
            if self.provider_capability_service and provider_instance:
                await self._validate_with_provider_capabilities(
                    template, provider_instance, validation_result
                )

            self.logger.info(
                f"Template validation completed for {template.template_id}: "
                f"{'valid' if validation_result['is_valid'] else 'invalid'}"
            )

            return validation_result

        except Exception as e:
            self.logger.error(f"Template validation failed for {template.template_id}: {e}")
            validation_result["is_valid"] = False
            validation_result["errors"].append(f"Validation error: {str(e)}")
            return validation_result

    def _validate_basic_template_structure(
        self, template: TemplateDTO, result: Dict[str, Any]
    ) -> None:
        """Validate basic template structure and required fields."""
        # Check required fields
        if not template.template_id:
            result["is_valid"] = False
            result["errors"].append("Template ID is required")

        if not template.provider_api:
            result["is_valid"] = False
            result["errors"].append("Provider API is required")

        # Check configuration structure
        if not template.configuration:
            result["warnings"].append("Template has no configuration data")
        else:
            # Validate essential configuration fields
            config = template.configuration

            if not config.get("image_id") and not config.get("imageId"):
                result["errors"].append("Image ID is required in configuration")
                result["is_valid"] = False

            max_instances = config.get("max_instances") or config.get("maxNumber", 0)
            if max_instances <= 0:
                result["warnings"].append("Max instances should be greater than 0")
            elif max_instances > 1000:
                result["warnings"].append(
                    "Max instances is very high (>1000), consider if this is intentional"
                )

        self.logger.debug(f"Basic validation completed for template {template.template_id}")

    async def _validate_with_provider_capabilities(
        self, template: TemplateDTO, provider_instance: str, result: Dict[str, Any]
    ) -> None:
        """Validate template against provider capabilities."""
        try:
            # Convert TemplateDTO to Template domain object for capability service
            from src.domain.template.aggregate import Template

            # Create minimal Template object for validation
            domain_template = Template(
                template_id=template.template_id,
                name=template.name,
                provider_api=template.provider_api,
                configuration=template.configuration,
            )

            # Use provider capability service for validation
            from src.application.services.provider_capability_service import (
                ValidationLevel,
            )

            capability_result = self.provider_capability_service.validate_template_requirements(
                domain_template, provider_instance, ValidationLevel.STRICT
            )

            # Merge capability validation results
            if not capability_result.is_valid:
                result["is_valid"] = False
                result["errors"].extend(capability_result.errors)

            result["warnings"].extend(capability_result.warnings)
            result["supported_features"].extend(capability_result.supported_features)

            self.logger.debug(
                f"Provider capability validation completed for template {
                    template.template_id}"
            )

        except Exception as e:
            self.logger.warning(
                f"Provider capability validation failed for template {
                    template.template_id}: {e}"
            )
            result["warnings"].append(f"Could not validate provider capabilities: {str(e)}")

    def clear_cache(self) -> None:
        """Clear template cache."""
        self.cache_service.invalidate()
        self.logger.info("Cleared template cache")


# Factory function for dependency injection
def create_template_configuration_manager(
    config_manager: ConfigurationManager,
    scheduler_strategy: SchedulerPort,
    logger: LoggingPort,
) -> TemplateConfigurationManager:
    """
    Create TemplateConfigurationManager.

    This function provides a clean way to create the manager with
    proper dependency injection.
    """
    return TemplateConfigurationManager(
        config_manager=config_manager,
        scheduler_strategy=scheduler_strategy,
        logger=logger,
    )
