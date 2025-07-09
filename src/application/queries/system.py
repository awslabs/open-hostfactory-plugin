"""System-level queries for administrative operations."""
from pydantic import BaseModel, ConfigDict

from src.application.interfaces.command_query import Query


class GetProviderConfigQuery(Query, BaseModel):
    """Query to get current provider configuration information."""
    model_config = ConfigDict(frozen=True)
    
    include_sensitive: bool = False


class ValidateProviderConfigQuery(Query, BaseModel):
    """Query to validate current provider configuration."""
    model_config = ConfigDict(frozen=True)
    
    detailed: bool = True
