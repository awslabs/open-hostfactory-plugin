"""Provider strategy configuration schemas."""
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator, model_validator

from .base_config import BaseCircuitBreakerConfig


class ProviderMode(str, Enum):
    """Provider operation modes."""
    SINGLE = "single"
    MULTI = "multi"
    NONE = "none"


class HealthCheckConfig(BaseModel):
    """Health check configuration for individual provider."""
    
    enabled: bool = Field(True, description="Enable health checks for this provider")
    interval: int = Field(300, description="Health check interval in seconds")
    timeout: int = Field(30, description="Health check timeout in seconds")
    retry_count: int = Field(3, description="Number of retries for failed health checks")
    
    @validator('interval')
    def validate_interval(cls, v: int) -> int:
        """Validate health check interval."""
        if v <= 0:
            raise ValueError("Health check interval must be positive")
        return v
    
    @validator('timeout')
    def validate_timeout(cls, v: int) -> int:
        """Validate health check timeout."""
        if v <= 0:
            raise ValueError("Health check timeout must be positive")
        return v


class CircuitBreakerConfig(BaseCircuitBreakerConfig):
    """Provider-specific circuit breaker configuration."""
    
    @validator('recovery_timeout')
    def validate_recovery_timeout(cls, v: int) -> int:
        """Validate recovery timeout."""
        if v <= 0:
            raise ValueError("Recovery timeout must be positive")
        return v


class ProviderInstanceConfig(BaseModel):
    """Configuration for individual provider instance."""
    
    name: str = Field(..., description="Unique name for this provider instance")
    type: str = Field(..., description="Provider type (aws, azure, gcp)")
    enabled: bool = Field(True, description="Whether this provider is enabled")
    priority: int = Field(0, description="Provider priority (lower = higher priority)")
    weight: int = Field(100, description="Provider weight for load balancing")
    config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")
    capabilities: List[str] = Field(default_factory=list, description="Provider capabilities")
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig, description="Health check configuration")
    
    @validator('name')
    def validate_name(cls, v: str) -> str:
        """Validate provider name."""
        if not v or not v.strip():
            raise ValueError("Provider name cannot be empty")
        # Ensure name is valid for use as identifier
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError("Provider name must contain only alphanumeric characters, hyphens, and underscores")
        return v.strip()
    
    @validator('type')
    def validate_type(cls, v: str) -> str:
        """Validate provider type."""
        valid_types = ['aws', 'azure', 'gcp']  # Extensible list
        if v not in valid_types:
            raise ValueError(f"Provider type must be one of {valid_types}")
        return v
    
    @validator('weight')
    def validate_weight(cls, v: int) -> int:
        """Validate provider weight."""
        if v <= 0:
            raise ValueError("Provider weight must be positive")
        return v


class ProviderConfig(BaseModel):
    """Provider configuration supporting single and multi-provider modes with advanced features."""
    
    # Provider strategy configuration
    selection_policy: str = Field("FIRST_AVAILABLE", description="Default provider selection policy")
    active_provider: Optional[str] = Field(None, description="Active provider for single-provider mode")
    health_check_interval: int = Field(300, description="Global health check interval in seconds")
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig, description="Circuit breaker configuration")
    providers: List[ProviderInstanceConfig] = Field(default_factory=list, description="List of provider instances")
    
    # Legacy support fields
    type: Optional[str] = Field(None, description="Legacy provider type")
    aws: Optional[Dict[str, Any]] = Field(None, description="Legacy AWS configuration")
    
    @validator('selection_policy')
    def validate_selection_policy(cls, v: str) -> str:
        """Validate selection policy."""
        valid_policies = [
            'FIRST_AVAILABLE', 'ROUND_ROBIN', 'WEIGHTED_ROUND_ROBIN',
            'LEAST_CONNECTIONS', 'FASTEST_RESPONSE', 'HIGHEST_SUCCESS_RATE',
            'CAPABILITY_BASED', 'HEALTH_BASED', 'RANDOM', 'PERFORMANCE_BASED'
        ]
        if v not in valid_policies:
            raise ValueError(f"Selection policy must be one of {valid_policies}")
        return v
    
    @validator('health_check_interval')
    def validate_health_check_interval(cls, v: int) -> int:
        """Validate health check interval."""
        if v <= 0:
            raise ValueError("Health check interval must be positive")
        return v
    
    @model_validator(mode='after')
    def validate_provider_configuration(self) -> 'ProviderConfig':
        """Validate overall provider configuration."""
        # Validate active_provider exists if specified
        if self.active_provider:
            provider_names = [p.name for p in self.providers]
            if self.active_provider not in provider_names:
                raise ValueError(f"Active provider '{self.active_provider}' not found in providers list")
        
        # Validate unique provider names
        provider_names = [p.name for p in self.providers]
        if len(provider_names) != len(set(provider_names)):
            raise ValueError("Provider names must be unique")
        
        # Validate at least one provider is configured (unless legacy mode)
        if not self.providers and not self.type:
            raise ValueError("At least one provider must be configured")
        
        return self
    
    def get_mode(self) -> ProviderMode:
        """Determine provider operation mode - strategy mode only."""
        if self.active_provider:
            return ProviderMode.SINGLE
        elif not self.providers:
            return ProviderMode.NONE
        else:
            # Count enabled providers
            enabled_providers = [p for p in self.providers if p.enabled]
            if len(enabled_providers) > 1:
                return ProviderMode.MULTI
            elif len(enabled_providers) == 1:
                return ProviderMode.SINGLE
            elif len(self.providers) == 1:
                return ProviderMode.SINGLE  # Single provider, even if disabled
            else:
                return ProviderMode.NONE
    
    def get_active_providers(self) -> List[ProviderInstanceConfig]:
        """Get active providers based on current mode."""
        mode = self.get_mode()
        
        if mode == ProviderMode.SINGLE and self.active_provider:
            # Explicit single provider mode
            return [p for p in self.providers if p.name == self.active_provider]
        elif mode == ProviderMode.MULTI:
            # Multi-provider mode - return all enabled providers
            return [p for p in self.providers if p.enabled]
        elif mode == ProviderMode.SINGLE:
            # Single provider mode - return enabled providers or first provider
            enabled_providers = [p for p in self.providers if p.enabled]
            if enabled_providers:
                return enabled_providers[:1]  # First enabled provider
            elif self.providers:
                return self.providers[:1]  # First provider even if disabled
            else:
                return []
        else:
            return []
    
    def is_multi_provider_mode(self) -> bool:
        """Check if configuration is in multi-provider mode."""
        return self.get_mode() == ProviderMode.MULTI
    
    def get_provider_by_name(self, name: str) -> Optional[ProviderInstanceConfig]:
        """Get provider configuration by name."""
        for provider in self.providers:
            if provider.name == name:
                return provider
        return None


# Backward compatibility - extend existing ProviderConfig
class ExtendedProviderConfig(BaseModel):
    """Extended provider configuration with unified support."""
    
    # Support both legacy and new formats
    config: Union[ProviderConfig, Dict[str, Any]] = Field(..., description="Provider configuration")
    
    @model_validator(mode='before')
    def parse_provider_config(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Parse provider configuration from various formats."""
        if isinstance(values, dict):
            # If it's already a dict, wrap it in config
            return {'config': values}
        return values
    
    @model_validator(mode='after')
    def validate_and_convert_config(self) -> 'ExtendedProviderConfig':
        """Validate and convert configuration to unified format."""
        if isinstance(self.config, dict):
            # Convert dict to ProviderConfig
            try:
                unified_config = ProviderConfig(**self.config)
                object.__setattr__(self, 'config', unified_config)
            except Exception as e:
                raise ValueError(f"Invalid provider configuration: {str(e)}")
        
        return self
    
    def get_unified_config(self) -> ProviderConfig:
        """Get unified provider configuration."""
        if isinstance(self.config, ProviderConfig):
            return self.config
        else:
            # This shouldn't happen after validation, but handle gracefully
            return ProviderConfig(**self.config)
