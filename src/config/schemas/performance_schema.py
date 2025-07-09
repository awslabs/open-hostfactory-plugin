"""Performance configuration schemas."""
from typing import Dict, Any, List
from pydantic import BaseModel, Field, validator, model_validator

from .base_config import BaseCircuitBreakerConfig


class BatchSizesConfig(BaseModel):
    """Batch sizes for different operations."""
    
    terminate_instances: int = Field(25, description="Batch size for terminate_instances operations")
    create_tags: int = Field(20, description="Batch size for create_tags operations")
    describe_instances: int = Field(25, description="Batch size for describe_instances operations")
    run_instances: int = Field(10, description="Batch size for run_instances operations")
    
    @validator('terminate_instances', 'create_tags', 'describe_instances', 'run_instances')
    def validate_batch_size(cls, v: int) -> int:
        """Validate batch size."""
        if v < 1:
            raise ValueError("Batch size must be at least 1")
        return v


class AdaptiveBatchSizingConfig(BaseModel):
    """Adaptive batch sizing configuration."""
    
    initial_batch_size: int = Field(10, description="Initial batch size for operations")
    min_batch_size: int = Field(5, description="Minimum batch size")
    max_batch_size: int = Field(50, description="Maximum batch size")
    increase_factor: float = Field(1.5, description="Factor to increase batch size on success")
    decrease_factor: float = Field(0.5, description="Factor to decrease batch size on failure")
    success_threshold: int = Field(3, description="Number of successful batches before increasing size")
    failure_threshold: int = Field(1, description="Number of failed batches before decreasing size")
    history_size: int = Field(10, description="Size of history to maintain for each operation")
    
    @validator('min_batch_size', 'max_batch_size', 'initial_batch_size')
    def validate_batch_sizes(cls, v: int) -> int:
        """Validate batch sizes."""
        if v < 1:
            raise ValueError("Batch size must be at least 1")
        return v
    
    @validator('increase_factor', 'decrease_factor')
    def validate_factors(cls, v: float) -> float:
        """Validate increase/decrease factors."""
        if v <= 0:
            raise ValueError("Factor must be positive")
        return v
    
    @validator('success_threshold', 'failure_threshold')
    def validate_thresholds(cls, v: int) -> int:
        """Validate thresholds."""
        if v < 1:
            raise ValueError("Threshold must be at least 1")
        return v
    
    @validator('history_size')
    def validate_history_size(cls, v: int) -> int:
        """Validate history size."""
        if v < 1:
            raise ValueError("History size must be at least 1")
        return v
    
    @model_validator(mode='after')
    def validate_batch_size_relationships(self) -> 'AdaptiveBatchSizingConfig':
        """Validate relationships between batch sizes."""
        if self.min_batch_size > self.max_batch_size:
            raise ValueError("Minimum batch size cannot be greater than maximum batch size")
        
        if self.initial_batch_size < self.min_batch_size or self.initial_batch_size > self.max_batch_size:
            raise ValueError("Initial batch size must be between minimum and maximum batch sizes")
        
        return self


class PerformanceConfig(BaseModel):
    """Performance optimization configuration."""
    
    enable_batching: bool = Field(True, description="Whether to enable batching of API calls")
    batch_sizes: BatchSizesConfig = Field(default_factory=lambda: BatchSizesConfig())
    enable_parallel: bool = Field(True, description="Whether to enable parallel processing")
    max_workers: int = Field(10, description="Maximum number of worker threads for parallel processing")
    enable_caching: bool = Field(True, description="Whether to enable resource caching")
    cache_ttl: int = Field(300, description="Cache time-to-live in seconds")
    enable_adaptive_batch_sizing: bool = Field(True, description="Whether to enable adaptive batch sizing")
    adaptive_batch_sizing: AdaptiveBatchSizingConfig = Field(default_factory=lambda: AdaptiveBatchSizingConfig())
    
    @validator('max_workers')
    def validate_max_workers(cls, v: int) -> int:
        """Validate max workers."""
        if v < 1:
            raise ValueError("Maximum workers must be at least 1")
        return v
    
    @validator('cache_ttl')
    def validate_cache_ttl(cls, v: int) -> int:
        """Validate cache TTL."""
        if v < 0:
            raise ValueError("Cache TTL must be non-negative")
        return v


class CircuitBreakerConfig(BaseCircuitBreakerConfig):
    """Performance-focused circuit breaker configuration with service-specific settings."""
    
    # Service-specific configurations
    service_configs: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "ec2": {
                "failure_threshold": 3,
                "recovery_timeout": 30,
                "backoff": {
                    "strategy_type": "exponential",
                    "max_retries": 3,
                    "base_delay": 1.0,
                    "max_delay": 30.0
                }
            },
            "dynamodb": {
                "failure_threshold": 5,
                "reset_timeout": 60,
                "backoff": {
                    "strategy_type": "exponential",
                    "max_retries": 5,
                    "base_delay": 0.5,
                    "max_delay": 20.0
                }
            },
            "s3": {
                "failure_threshold": 3,
                "reset_timeout": 30,
                "backoff": {
                    "strategy_type": "exponential",
                    "max_retries": 4,
                    "base_delay": 0.5,
                    "max_delay": 15.0
                }
            }
        },
        description="Service-specific circuit breaker configurations"
    )
    
    # Retryable exceptions by service
    retryable_exceptions: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "ec2": [
                "RequestLimitExceeded",
                "InsufficientInstanceCapacity",
                "InternalError"
            ],
            "dynamodb": [
                "ProvisionedThroughputExceededException",
                "ThrottlingException",
                "RequestLimitExceeded"
            ],
            "s3": [
                "SlowDown",
                "ServiceUnavailable",
                "InternalError"
            ]
        },
        description="Retryable exceptions by service"
    )
