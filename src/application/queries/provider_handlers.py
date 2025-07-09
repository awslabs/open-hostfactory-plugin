"""Provider Strategy Query Handlers - CQRS handlers for provider strategy queries.

This module implements query handlers for retrieving provider strategy information,
leveraging the existing provider strategy ecosystem through clean CQRS interfaces.
"""

from typing import Dict, Any
import time

from src.application.interfaces.command_query import QueryHandler
from src.application.provider.queries import (
    GetProviderHealthQuery,
    ListAvailableProvidersQuery,
    GetProviderCapabilitiesQuery,
    GetProviderMetricsQuery,
    GetProviderStrategyConfigQuery
)

from src.providers.base.strategy import (
    ProviderContext
)

from src.domain.base.ports import LoggingPort
from src.domain.base.dependency_injection import injectable
# Logging through LoggingPort (Clean Architecture compliant)


@injectable
class GetProviderHealthHandler(QueryHandler):
    """Handler for retrieving provider health status."""
    
    def __init__(self, 
                 provider_context: ProviderContext,
                 logger: LoggingPort):
        self._provider_context = provider_context
        self._logger = logger
    
    
    def handle(self, query: GetProviderHealthQuery) -> Dict[str, Any]:
        """Handle provider health status query."""
        self._logger.debug(f"Getting health status for provider: {query.provider_name or 'all'}")
        
        try:
            if query.provider_name:
                # Get health for specific provider
                health_status = self._provider_context.get_provider_health(query.provider_name)
                
                if health_status is None:
                    return {
                        "provider_name": query.provider_name,
                        "status": "not_found",
                        "message": f"Provider '{query.provider_name}' not found"
                    }
                
                result = {
                    "provider_name": query.provider_name,
                    "is_healthy": health_status.is_healthy,
                    "status_message": health_status.status_message
                }
                
                if query.include_details:
                    result.update({
                        "last_check_time": health_status.last_check_time,
                        "response_time_ms": health_status.response_time_ms,
                        "error_details": health_status.error_details
                    })
                
                return result
            else:
                # Get health for all providers
                all_providers = self._provider_context.get_available_strategies()
                health_results = {}
                
                for strategy in all_providers:
                    health_status = self._provider_context.get_provider_health(strategy.name)
                    
                    if health_status:
                        provider_health = {
                            "is_healthy": health_status.is_healthy,
                            "status_message": health_status.status_message
                        }
                        
                        if query.include_details:
                            provider_health.update({
                                "last_check_time": health_status.last_check_time,
                                "response_time_ms": health_status.response_time_ms,
                                "error_details": health_status.error_details
                            })
                        
                        health_results[strategy.name] = provider_health
                
                return {
                    "providers": health_results,
                    "total_providers": len(all_providers),
                    "healthy_providers": sum(1 for h in health_results.values() if h["is_healthy"])
                }
                
        except Exception as e:
            self._logger.error(f"Failed to get provider health: {str(e)}")
            raise


@injectable
class ListAvailableProvidersHandler(QueryHandler):
    """Handler for listing available provider strategies."""
    
    def __init__(self,
                 provider_context: ProviderContext,
                 logger: LoggingPort):
        self._provider_context = provider_context
        self._logger = logger
    
    
    def handle(self, query: ListAvailableProvidersQuery) -> Dict[str, Any]:
        """Handle list available providers query."""
        self._logger.debug("Listing available provider strategies")
        
        try:
            available_strategies = self._provider_context.get_available_strategies()
            providers = []
            
            for strategy in available_strategies:
                # Filter by provider type if specified
                if query.provider_type and strategy.provider_type != query.provider_type:
                    continue
                
                provider_info = {
                    "name": strategy.name,
                    "provider_type": strategy.provider_type,
                    "status": "available"
                }
                
                # Include health information if requested
                if query.include_health:
                    health_status = self._provider_context.get_provider_health(strategy.name)
                    if health_status:
                        provider_info["health"] = {
                            "is_healthy": health_status.is_healthy,
                            "status_message": health_status.status_message,
                            "last_check_time": health_status.last_check_time
                        }
                        
                        # Filter healthy providers if requested
                        if query.filter_healthy_only and not health_status.is_healthy:
                            continue
                
                # Include capabilities if requested
                if query.include_capabilities:
                    try:
                        capabilities = strategy.get_capabilities()
                        provider_info["capabilities"] = {
                            "supported_operations": [op.value for op in capabilities.supported_operations],
                            "features": capabilities.features,
                            "limitations": capabilities.limitations
                        }
                    except Exception as e:
                        self._logger.warning(f"Failed to get capabilities for {strategy.name}: {str(e)}")
                        provider_info["capabilities"] = {"error": "Failed to retrieve capabilities"}
                
                # Include metrics if requested
                if query.include_metrics:
                    try:
                        metrics = self._provider_context.get_strategy_metrics(strategy.name)
                        if metrics:
                            provider_info["metrics"] = {
                                "total_operations": metrics.total_operations,
                                "success_rate": metrics.success_rate,
                                "average_response_time_ms": metrics.average_response_time_ms,
                                "last_used_time": metrics.last_used_time
                            }
                    except Exception as e:
                        self._logger.warning(f"Failed to get metrics for {strategy.name}: {str(e)}")
                
                providers.append(provider_info)
            
            return {
                "providers": providers,
                "total_count": len(providers),
                "query_filters": {
                    "provider_type": query.provider_type,
                    "healthy_only": query.filter_healthy_only
                }
            }
            
        except Exception as e:
            self._logger.error(f"Failed to list available providers: {str(e)}")
            raise


@injectable
class GetProviderCapabilitiesHandler(QueryHandler):
    """Handler for retrieving provider capabilities."""
    
    def __init__(self,
                 provider_context: ProviderContext,
                 logger: LoggingPort):
        self._provider_context = provider_context
        self._logger = logger
    
    
    def handle(self, query: GetProviderCapabilitiesQuery) -> Dict[str, Any]:
        """Handle provider capabilities query."""
        self._logger.debug(f"Getting capabilities for provider: {query.provider_name}")
        
        try:
            strategy = self._provider_context.get_strategy(query.provider_name)
            
            if not strategy:
                return {
                    "provider_name": query.provider_name,
                    "status": "not_found",
                    "message": f"Provider '{query.provider_name}' not found"
                }
            
            capabilities = strategy.get_capabilities()
            
            result = {
                "provider_name": query.provider_name,
                "provider_type": capabilities.provider_type,
                "supported_operations": [op.value for op in capabilities.supported_operations],
                "features": capabilities.features
            }
            
            if query.include_limitations:
                result["limitations"] = capabilities.limitations
            
            if query.include_performance_metrics:
                result["performance_metrics"] = capabilities.performance_metrics
            
            return result
            
        except Exception as e:
            self._logger.error(f"Failed to get provider capabilities: {str(e)}")
            raise


@injectable
class GetProviderMetricsHandler(QueryHandler):
    """Handler for retrieving provider performance metrics."""
    
    def __init__(self,
                 provider_context: ProviderContext,
                 logger: LoggingPort):
        self._provider_context = provider_context
        self._logger = logger
    
    
    def handle(self, query: GetProviderMetricsQuery) -> Dict[str, Any]:
        """Handle provider metrics query."""
        self._logger.debug(f"Getting metrics for provider: {query.provider_name or 'all'}")
        
        try:
            if query.provider_name:
                # Get metrics for specific provider
                metrics = self._provider_context.get_strategy_metrics(query.provider_name)
                
                if not metrics:
                    return {
                        "provider_name": query.provider_name,
                        "status": "not_found",
                        "message": f"No metrics found for provider '{query.provider_name}'"
                    }
                
                result = {
                    "provider_name": query.provider_name,
                    "total_operations": metrics.total_operations,
                    "successful_operations": metrics.successful_operations,
                    "failed_operations": metrics.failed_operations,
                    "success_rate": metrics.success_rate,
                    "average_response_time_ms": metrics.average_response_time_ms,
                    "last_used_time": metrics.last_used_time,
                    "health_check_count": metrics.health_check_count,
                    "last_health_check": metrics.last_health_check
                }
                
                return result
            else:
                # Get metrics for all providers
                all_strategies = self._provider_context.get_available_strategies()
                metrics_results = {}
                
                for strategy in all_strategies:
                    metrics = self._provider_context.get_strategy_metrics(strategy.name)
                    if metrics:
                        metrics_results[strategy.name] = {
                            "total_operations": metrics.total_operations,
                            "success_rate": metrics.success_rate,
                            "average_response_time_ms": metrics.average_response_time_ms,
                            "last_used_time": metrics.last_used_time
                        }
                
                return {
                    "providers": metrics_results,
                    "total_providers": len(all_strategies),
                    "query_time_range_hours": query.time_range_hours
                }
                
        except Exception as e:
            self._logger.error(f"Failed to get provider metrics: {str(e)}")
            raise


@injectable
class GetProviderStrategyConfigHandler(QueryHandler):
    """Handler for retrieving provider strategy configuration."""
    
    def __init__(self,
                 provider_context: ProviderContext,
                 logger: LoggingPort):
        self._provider_context = provider_context
        self._logger = logger
    
    
    def handle(self, query: GetProviderStrategyConfigQuery) -> Dict[str, Any]:
        """Handle provider strategy configuration query."""
        self._logger.debug("Getting provider strategy configuration")
        
        try:
            config = {}
            
            if query.include_selection_policies:
                config["selection_policies"] = {
                    "default_policy": self._provider_context.get_default_selection_policy(),
                    "available_policies": [policy.value for policy in self._provider_context.get_available_policies()]
                }
            
            if query.include_fallback_config:
                config["fallback_config"] = self._provider_context.get_fallback_configuration()
            
            if query.include_health_check_config:
                config["health_check_config"] = {
                    "interval_seconds": self._provider_context.get_health_check_interval(),
                    "timeout_seconds": self._provider_context.get_health_check_timeout(),
                    "retry_count": self._provider_context.get_health_check_retry_count()
                }
            
            if query.include_circuit_breaker_config:
                config["circuit_breaker_config"] = self._provider_context.get_circuit_breaker_configuration()
            
            return {
                "configuration": config,
                "retrieved_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            self._logger.error(f"Failed to get provider strategy configuration: {str(e)}")
            raise
