"""System query handlers for administrative operations."""
from typing import Dict, Any, TYPE_CHECKING
from src.application.interfaces.command_query import QueryHandler
from src.application.queries.system import GetProviderConfigQuery, ValidateProviderConfigQuery
from src.application.decorators import query_handler
from src.domain.base.ports import LoggingPort, ContainerPort

# Use TYPE_CHECKING to avoid direct infrastructure imports
if TYPE_CHECKING:
    from src.infrastructure.factories.provider_strategy_factory import ProviderStrategyFactory


@query_handler(GetProviderConfigQuery)
class GetProviderConfigHandler(QueryHandler[GetProviderConfigQuery, Dict[str, Any]]):
    """Handler for getting provider configuration information."""
    
    def __init__(self, logger: LoggingPort, container: ContainerPort):
        """
        Initialize get provider config handler.
        
        Args:
            logger: Logging port for operation logging
            container: Container port for dependency access
        """
        self.logger = logger
        self.container = container
    
    
    def handle(self, query: GetProviderConfigQuery) -> Dict[str, Any]:
        """
        Handle get provider configuration query.
        
        Args:
            query: Query with options for configuration retrieval
            
        Returns:
            Current provider configuration information
        """
        self.logger.debug("Getting provider configuration information")
        
        try:
            # Get configuration manager from container
            from src.domain.base.ports import ConfigurationPort
            config_manager = self.container.get(ConfigurationPort)
            
            # Try to get provider strategy factory for detailed info
            try:
                factory = self.container.get('ProviderStrategyFactory')
                provider_info = factory.get_provider_info()
            except Exception:
                # Fallback to basic configuration information
                provider_info = {
                    "mode": "legacy",
                    "error": "Provider strategy factory not available"
                }
            
            # Get additional configuration details
            try:
                if hasattr(config_manager, 'get_provider_config'):
                    unified_config = config_manager.get_provider_config()
                    config_details = {
                        "unified_config_available": True,
                        "provider_mode": unified_config.get_mode().value,
                        "selection_policy": unified_config.selection_policy,
                        "health_check_interval": unified_config.health_check_interval,
                        "circuit_breaker_enabled": unified_config.circuit_breaker.enabled,
                        "total_providers": len(unified_config.providers),
                        "active_providers": len(unified_config.get_active_providers())
                    }
                    
                    if not query.include_sensitive:
                        # Remove sensitive configuration details
                        config_details["providers"] = [
                            {
                                "name": p.name,
                                "type": p.type,
                                "enabled": p.enabled,
                                "priority": p.priority,
                                "weight": p.weight,
                                "capabilities": p.capabilities
                            }
                            for p in unified_config.providers
                        ]
                    else:
                        config_details["providers"] = [p.model_dump() for p in unified_config.providers]
                        
                else:
                    config_details = {
                        "unified_config_available": False,
                        "provider_mode": "legacy"
                    }
            except Exception as e:
                config_details = {
                    "unified_config_available": False,
                    "error": str(e)
                }
            
            result = {
                "status": "success",
                "provider_info": provider_info,
                "config_details": config_details,
                "query_id": query.query_id,
                "include_sensitive": query.include_sensitive
            }
            
            self.logger.debug("Provider configuration information retrieved successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get provider configuration: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "query_id": query.query_id
            }


@query_handler(ValidateProviderConfigQuery)
class ValidateProviderConfigHandler(QueryHandler[ValidateProviderConfigQuery, Dict[str, Any]]):
    """Handler for validating provider configuration."""
    
    def __init__(self, logger: LoggingPort, container: ContainerPort):
        """
        Initialize validate provider config handler.
        
        Args:
            logger: Logging port for operation logging
            container: Container port for dependency access
        """
        self.logger = logger
        self.container = container
    
    
    def handle(self, query: ValidateProviderConfigQuery) -> Dict[str, Any]:
        """
        Handle validate provider configuration query.
        
        Args:
            query: Query with validation options
            
        Returns:
            Configuration validation result
        """
        self.logger.debug("Validating provider configuration")
        
        try:
            # Get provider strategy factory for validation
            validation_result = {
                "valid": False,
                "errors": [],
                "warnings": [],
                "details": {}
            }
            
            try:
                factory = self.container.get('ProviderStrategyFactory')
                validation_result = factory.validate_configuration()
            except Exception as e:
                validation_result["errors"].append(f"Provider strategy factory validation failed: {str(e)}")
            
            # Additional configuration validation
            try:
                from src.domain.base.ports import ConfigurationPort
                config_manager = self.container.get(ConfigurationPort)
                
                if hasattr(config_manager, 'get_provider_config'):
                    unified_config = config_manager.get_provider_config()
                    
                    # Basic validation checks
                    if query.detailed:
                        validation_result["details"]["provider_count"] = len(unified_config.providers)
                        validation_result["details"]["active_provider_count"] = len(unified_config.get_active_providers())
                        validation_result["details"]["selection_policy"] = unified_config.selection_policy
                        validation_result["details"]["provider_mode"] = unified_config.get_mode().value
                        
                        # Check for common configuration issues
                        if unified_config.get_mode().value == "multi" and len(unified_config.get_active_providers()) < 2:
                            validation_result["warnings"].append("Multi-provider mode configured but less than 2 active providers")
                        
                        if unified_config.active_provider and unified_config.active_provider not in [p.name for p in unified_config.providers]:
                            validation_result["errors"].append(f"Active provider '{unified_config.active_provider}' not found in providers list")
                
            except Exception as e:
                validation_result["errors"].append(f"Configuration validation failed: {str(e)}")
            
            # Update overall validation status
            validation_result["valid"] = len(validation_result["errors"]) == 0
            
            result = {
                "status": "success",
                "validation_result": validation_result,
                "query_id": query.query_id,
                "detailed": query.detailed
            }
            
            self.logger.debug(f"Provider configuration validation completed: valid={validation_result['valid']}")
            return result
            
        except Exception as e:
            self.logger.error(f"Provider configuration validation failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "query_id": query.query_id
            }
