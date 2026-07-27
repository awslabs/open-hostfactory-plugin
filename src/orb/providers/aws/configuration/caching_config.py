"""AWS-specific caching configuration."""

from pydantic import BaseModel, Field, field_validator


class AMIResolutionCacheConfig(BaseModel):
    """AMI resolution caching configuration.

    AMI lookups are an AWS-specific concern (EC2 AMI IDs / SSM parameter paths),
    so this schema lives in the AWS provider package rather than the generic
    performance configuration.
    """

    enabled: bool = Field(True, description="Enable AMI resolution caching")
    ttl_seconds: int = Field(3600, description="AMI cache TTL in seconds")
    file: str = Field("ami_cache.json", description="AMI cache filename")

    @field_validator("ttl_seconds")
    @classmethod
    def validate_ttl_seconds(cls, v: int) -> int:
        """Validate AMI cache TTL."""
        if v < 0:
            raise ValueError("AMI cache TTL must be non-negative")
        return v
