"""Main application configuration schema."""

import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .common_schema import (
    DatabaseConfig,
    EventsConfig,
    NamingConfig,
    RequestConfig,
    ResourceConfig,
)
from .logging_schema import LoggingConfig
from .performance_schema import CircuitBreakerConfig, PerformanceConfig
from .provider_strategy_schema import ProviderConfig
from .scheduler_schema import SchedulerConfig
from .server_schema import ServerConfig
from .storage_schema import StorageConfig
from .template_schema import TemplateConfig


class AppConfig(BaseModel):
    """Application configuration."""

    version: str = Field("2.0.0", description="Configuration version")
    provider: ProviderConfig
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    naming: NamingConfig = Field(default_factory=lambda: NamingConfig())
    logging: LoggingConfig = Field(default_factory=lambda: LoggingConfig())
    template: Optional[TemplateConfig] = None
    events: EventsConfig = Field(default_factory=lambda: EventsConfig())
    storage: StorageConfig = Field(default_factory=lambda: StorageConfig())
    resource: ResourceConfig = Field(default_factory=lambda: ResourceConfig())
    request: RequestConfig = Field(default_factory=lambda: RequestConfig())
    database: DatabaseConfig = Field(default_factory=lambda: DatabaseConfig())
    circuit_breaker: CircuitBreakerConfig = Field(
        default_factory=lambda: CircuitBreakerConfig()
    )
    performance: PerformanceConfig = Field(default_factory=lambda: PerformanceConfig())
    server: ServerConfig = Field(default_factory=lambda: ServerConfig())
    environment: str = Field("development", description="Environment")
    debug: bool = Field(False, description="Debug mode")
    request_timeout: int = Field(300, description="Request timeout in seconds")
    max_machines_per_request: int = Field(
        100, description="Maximum number of machines per request"
    )

    @model_validator(mode="after")
    def ensure_template_config(self) -> "AppConfig":
        """Ensure template configuration is present."""
        if self.template is None:
            object.__setattr__(
                self,
                "template",
                TemplateConfig(
                    default_image_id="ami-12345678",
                    default_instance_type="t2.micro",
                    subnet_ids=["subnet-12345678"],
                    security_group_ids=["sg-12345678"],
                ),
            )
        return self

    def get_config_file_path(self) -> str:
        """Build full config file path using scheduler + provider type."""
        config_root = self.scheduler.get_config_root()
        # Extract provider type from active_provider (e.g., "aws-default" -> "aws")
        provider_type = self.provider.active_provider.split("-")[0]
        # Generate provider-specific config file name
        config_file = f"{provider_type}prov_config.json"
        return os.path.join(config_root, config_file)

    def get_templates_file_path(self) -> str:
        """Build full templates file path using scheduler + provider type."""
        config_root = self.scheduler.get_config_root()
        # Extract provider type from active_provider (e.g., "aws-default" -> "aws")
        provider_type = self.provider.active_provider.split("-")[0]
        # Generate provider-specific templates file name
        templates_file = f"{provider_type}prov_templates.json"
        return os.path.join(config_root, templates_file)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """
        Validate environment.

        Args:
            v: Value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If environment is invalid
        """
        valid_environments = ["development", "testing", "staging", "production"]
        if v not in valid_environments:
            raise ValueError(f"Environment must be one of {valid_environments}")
        return v

    @field_validator("request_timeout")
    @classmethod
    def validate_request_timeout(cls, v: int) -> int:
        """Validate request timeout."""
        if v < 0:
            raise ValueError("Request timeout must be positive")
        return v

    @field_validator("max_machines_per_request")
    @classmethod
    def validate_max_machines(cls, v: int) -> int:
        """Validate max machines per request."""
        if v < 1:
            raise ValueError("Maximum machines per request must be at least 1")
        return v


def validate_config(config: Dict[str, Any]) -> AppConfig:
    """
    Validate configuration.

    Args:
        config: Configuration to validate

    Returns:
        Validated configuration

    Raises:
        ValueError: If configuration is invalid
    """
    # Rebuild model to ensure all forward references are resolved
    AppConfig.model_rebuild()
    return AppConfig(**config)
