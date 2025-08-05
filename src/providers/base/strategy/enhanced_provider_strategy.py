"""Enhanced Provider Strategy with API-specific capabilities."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import Field

from .provider_strategy import ProviderCapabilities as BaseProviderCapabilities
from .provider_strategy import ProviderStrategy


class EnhancedProviderCapabilities(BaseProviderCapabilities):
    """Enhanced provider capabilities with API-specific support."""

    # Supported Provider APIs (e.g., EC2Fleet, SpotFleet, RunInstances, ASG)
    supported_apis: List[str] = Field(default_factory=list)

    # API-specific capabilities and limitations
    api_capabilities: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    def supports_api(self, api_type: str) -> bool:
        """Check if provider supports a specific API type."""
        return api_type in self.supported_apis

    def get_api_capabilities(self, api_type: str) -> Dict[str, Any]:
        """Get capabilities for a specific API type."""
        return self.api_capabilities.get(api_type, {})

    def get_api_limitation(self, api_type: str, limitation_key: str, default: Any = None) -> Any:
        """Get a specific limitation for an API type."""
        api_caps = self.get_api_capabilities(api_type)
        return api_caps.get(limitation_key, default)

    def validate_template_compatibility(
        self, template_provider_api: str, max_instances: int = 1
    ) -> Dict[str, Any]:
        """
        Validate if a template is compatible with this provider.

        Args:
            template_provider_api: The provider API specified in the template
            max_instances: Maximum instances requested in template

        Returns:
            Dictionary with validation results
        """
        result = {
            "compatible": False,
            "errors": [],
            "warnings": [],
            "api_supported": False,
            "limitations": {},
        }

        # Check if API is supported
        if not self.supports_api(template_provider_api):
            result["errors"].append(
                f"Provider {
                    self.provider_type} does not support API {template_provider_api}. "
                f"Supported APIs: {
                    ', '.join(
                        self.supported_apis)}"
            )
            return result

        result["api_supported"] = True
        api_caps = self.get_api_capabilities(template_provider_api)

        # Check instance limits
        max_allowed = api_caps.get("max_instances", float("inf"))
        if max_instances > max_allowed:
            result["errors"].append(
                f"Template requests {max_instances} instances but {template_provider_api} "
                f"supports maximum {max_allowed} instances"
            )

        # Check for warnings
        if max_instances > api_caps.get("recommended_max_instances", float("inf")):
            result["warnings"].append(
                f"Template requests {max_instances} instances. "
                f"Recommended maximum for {template_provider_api} is {api_caps.get('recommended_max_instances')}"
            )

        # Add limitations info
        result["limitations"] = {
            key: value
            for key, value in api_caps.items()
            if key.endswith("_required") or key.startswith("supports_") or key.endswith("_limit")
        }

        # Mark as compatible if no errors
        result["compatible"] = len(result["errors"]) == 0

        return result


class EnhancedProviderStrategy(ProviderStrategy, ABC):
    """Enhanced provider strategy with API-specific capabilities."""

    @abstractmethod
    def get_enhanced_capabilities(self) -> EnhancedProviderCapabilities:
        """Get enhanced provider capabilities with API support."""

    def get_capabilities(self) -> BaseProviderCapabilities:
        """Get base capabilities (for backward compatibility)."""
        enhanced = self.get_enhanced_capabilities()
        return BaseProviderCapabilities(
            provider_type=enhanced.provider_type,
            supported_operations=enhanced.supported_operations,
            features=enhanced.features,
            limitations=enhanced.limitations,
            performance_metrics=enhanced.performance_metrics,
        )

    def validate_template(
        self, template_provider_api: str, max_instances: int = 1
    ) -> Dict[str, Any]:
        """Validate template compatibility with this provider."""
        capabilities = self.get_enhanced_capabilities()
        return capabilities.validate_template_compatibility(template_provider_api, max_instances)

    def get_supported_apis(self) -> List[str]:
        """Get list of supported API types."""
        return self.get_enhanced_capabilities().supported_apis

    def supports_template_api(self, api_type: str) -> bool:
        """Check if provider supports the template's API type."""
        return self.get_enhanced_capabilities().supports_api(api_type)


class ProviderTemplateValidator:
    """Utility class for validating templates against provider capabilities."""

    def __init__(self, providers: Dict[str, EnhancedProviderStrategy]):
        self.providers = providers

    def find_compatible_providers(
        self, template_provider_api: str, max_instances: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Find all providers compatible with a template.

        Returns:
            List of provider compatibility results
        """
        results = []

        for provider_name, provider in self.providers.items():
            validation = provider.validate_template(template_provider_api, max_instances)
            results.append(
                {
                    "provider": provider_name,
                    "provider_type": provider.provider_type,
                    **validation,
                }
            )

        return results

    def get_best_provider(
        self, template_provider_api: str, max_instances: int = 1
    ) -> Optional[str]:
        """
        Get the best provider for a template based on compatibility and capabilities.

        Returns:
            Provider name or None if no compatible provider found
        """
        compatible = self.find_compatible_providers(template_provider_api, max_instances)

        # Filter to only compatible providers
        compatible_providers = [p for p in compatible if p["compatible"]]

        if not compatible_providers:
            return None

        # Sort by number of warnings (fewer is better)
        compatible_providers.sort(key=lambda p: len(p.get("warnings", [])))

        return compatible_providers[0]["provider"]

    def validate_all_templates(
        self, templates: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Validate multiple templates against all providers.

        Args:
            templates: List of template dictionaries with 'provider_api' and 'max_instances'

        Returns:
            Dictionary mapping template IDs to compatibility results
        """
        results = {}

        for template in templates:
            template_id = template.get("template_id", "unknown")
            provider_api = template.get("provider_api")
            max_instances = template.get("max_instances", 1)

            if provider_api:
                results[template_id] = self.find_compatible_providers(provider_api, max_instances)
            else:
                results[template_id] = [
                    {
                        "provider": "none",
                        "compatible": False,
                        "errors": ["Template missing provider_api field"],
                        "warnings": [],
                        "api_supported": False,
                    }
                ]

        return results
