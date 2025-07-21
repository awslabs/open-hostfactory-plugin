"""Provider Strategy Query Handlers - CQRS handlers for provider strategy queries.

This module implements query handlers for retrieving provider strategy information,
leveraging the existing provider strategy ecosystem through clean CQRS interfaces.
"""

import time
from typing import Any, Dict, List

from src.application.base.handlers import BaseQueryHandler
from src.application.decorators import query_handler
from src.application.dto.system import (
    ProviderCapabilitiesDTO,
    ProviderHealthDTO,
    ProviderMetricsDTO,
    ProviderStrategyConfigDTO,
)
from src.application.provider.queries import (
    GetProviderCapabilitiesQuery,
    GetProviderHealthQuery,
    GetProviderMetricsQuery,
    GetProviderStrategyConfigQuery,
    ListAvailableProvidersQuery,
)
from src.domain.base.ports import ErrorHandlingPort, LoggingPort
from src.providers.base.strategy import ProviderContext


@query_handler(GetProviderHealthQuery)
class GetProviderHealthHandler(BaseQueryHandler[GetProviderHealthQuery, ProviderHealthDTO]):
    """Handler for retrieving provider health status."""

    def __init__(
        self,
        provider_context: ProviderContext,
        logger: LoggingPort,
        error_handler: ErrorHandlingPort,
    ):
        """
        Initialize provider health handler.

        Args:
            provider_context: Provider context for accessing strategies
            logger: Logging port for operation logging
            error_handler: Error handling port for exception management
        """
        super().__init__(logger, error_handler)
        self.provider_context = provider_context

    async def execute_query(self, query: GetProviderHealthQuery) -> Dict[str, Any]:
        """Execute provider health query."""
        self.logger.info(f"Getting health for provider: {query.provider_name}")

        try:
            # Get provider strategy
            strategy = self.provider_context.get_strategy(query.provider_name)
            if not strategy:
                return {
                    "provider_name": query.provider_name,
                    "status": "not_found",
                    "health": "unknown",
                    "message": f"Provider '{query.provider_name}' not found",
                }

            # Get health information
            health_info = {
                "provider_name": query.provider_name,
                "status": "active",
                "health": "healthy",
                "last_check": time.time(),
                "capabilities": [],
            }

            # Try to get detailed health if available
            if hasattr(strategy, "get_health_status"):
                detailed_health = strategy.get_health_status()
                health_info.update(detailed_health)

            self.logger.info(f"Provider {query.provider_name} health: {health_info['health']}")
            return health_info

        except Exception as e:
            self.logger.error(f"Failed to get provider health: {e}")
            return {
                "provider_name": query.provider_name,
                "status": "error",
                "health": "unhealthy",
                "message": str(e),
            }


@query_handler(ListAvailableProvidersQuery)
class ListAvailableProvidersHandler(
    BaseQueryHandler[ListAvailableProvidersQuery, List[Dict[str, Any]]]
):
    """Handler for listing available providers."""

    def __init__(
        self,
        provider_context: ProviderContext,
        logger: LoggingPort,
        error_handler: ErrorHandlingPort,
    ):
        """
        Initialize list providers handler.

        Args:
            provider_context: Provider context for accessing strategies
            logger: Logging port for operation logging
            error_handler: Error handling port for exception management
        """
        super().__init__(logger, error_handler)
        self.provider_context = provider_context

    async def execute_query(self, query: ListAvailableProvidersQuery) -> List[Dict[str, Any]]:
        """Execute list available providers query."""
        self.logger.info("Listing available providers")

        try:
            available_providers = []

            # Get all available strategies
            strategy_names = self.provider_context.get_available_strategies()

            for strategy_name in strategy_names:
                try:
                    strategy = self.provider_context.get_strategy(strategy_name)
                    provider_info = {
                        "name": strategy_name,
                        "type": getattr(strategy, "provider_type", "unknown"),
                        "status": "active",
                        "capabilities": getattr(strategy, "capabilities", []),
                    }
                    available_providers.append(provider_info)
                except Exception as e:
                    self.logger.warning(f"Could not get info for provider {strategy_name}: {e}")
                    available_providers.append(
                        {
                            "name": strategy_name,
                            "type": "unknown",
                            "status": "error",
                            "error": str(e),
                        }
                    )

            self.logger.info(f"Found {len(available_providers)} available providers")
            return available_providers

        except Exception as e:
            self.logger.error(f"Failed to list available providers: {e}")
            raise


@query_handler(GetProviderCapabilitiesQuery)
class GetProviderCapabilitiesHandler(
    BaseQueryHandler[GetProviderCapabilitiesQuery, ProviderCapabilitiesDTO]
):
    """Handler for retrieving provider capabilities."""

    def __init__(
        self,
        provider_context: ProviderContext,
        logger: LoggingPort,
        error_handler: ErrorHandlingPort,
    ):
        """
        Initialize provider capabilities handler.

        Args:
            provider_context: Provider context for accessing strategies
            logger: Logging port for operation logging
            error_handler: Error handling port for exception management
        """
        super().__init__(logger, error_handler)
        self.provider_context = provider_context

    async def execute_query(self, query: GetProviderCapabilitiesQuery) -> Dict[str, Any]:
        """Execute provider capabilities query."""
        self.logger.info(f"Getting capabilities for provider: {query.provider_name}")

        try:
            # Get provider strategy
            strategy = self.provider_context.get_strategy(query.provider_name)
            if not strategy:
                return {
                    "provider_name": query.provider_name,
                    "capabilities": [],
                    "error": f"Provider '{query.provider_name}' not found",
                }

            # Get capabilities
            capabilities = {
                "provider_name": query.provider_name,
                "capabilities": getattr(strategy, "capabilities", []),
                "supported_operations": getattr(strategy, "supported_operations", []),
                "configuration_schema": getattr(strategy, "configuration_schema", {}),
            }

            # Try to get detailed capabilities if available
            if hasattr(strategy, "get_capabilities"):
                detailed_capabilities = strategy.get_capabilities()
                capabilities.update(detailed_capabilities)

            self.logger.info(f"Retrieved capabilities for provider: {query.provider_name}")
            return capabilities

        except Exception as e:
            self.logger.error(f"Failed to get provider capabilities: {e}")
            raise


class GetProviderMetricsHandler(BaseQueryHandler[GetProviderMetricsQuery, Dict[str, Any]]):
    """Handler for retrieving provider metrics."""

    def __init__(
        self,
        provider_context: ProviderContext,
        logger: LoggingPort,
        error_handler: ErrorHandlingPort,
    ):
        """
        Initialize provider metrics handler.

        Args:
            provider_context: Provider context for accessing strategies
            logger: Logging port for operation logging
            error_handler: Error handling port for exception management
        """
        super().__init__(logger, error_handler)
        self.provider_context = provider_context

    async def execute_query(self, query: GetProviderMetricsQuery) -> Dict[str, Any]:
        """Execute provider metrics query."""
        self.logger.info(f"Getting metrics for provider: {query.provider_name}")

        try:
            # Get provider strategy
            strategy = self.provider_context.get_strategy(query.provider_name)
            if not strategy:
                return {
                    "provider_name": query.provider_name,
                    "metrics": {},
                    "error": f"Provider '{query.provider_name}' not found",
                }

            # Get basic metrics
            metrics = {
                "provider_name": query.provider_name,
                "timestamp": time.time(),
                "requests_total": 0,
                "requests_successful": 0,
                "requests_failed": 0,
                "average_response_time": 0.0,
            }

            # Try to get detailed metrics if available
            if hasattr(strategy, "get_metrics"):
                detailed_metrics = strategy.get_metrics()
                metrics.update(detailed_metrics)

            self.logger.info(f"Retrieved metrics for provider: {query.provider_name}")
            return metrics

        except Exception as e:
            self.logger.error(f"Failed to get provider metrics: {e}")
            raise


class GetProviderStrategyConfigHandler(
    BaseQueryHandler[GetProviderStrategyConfigQuery, ProviderStrategyConfigDTO]
):
    """Handler for retrieving provider strategy configuration."""

    def __init__(
        self,
        provider_context: ProviderContext,
        logger: LoggingPort,
        error_handler: ErrorHandlingPort,
    ):
        """
        Initialize provider strategy config handler.

        Args:
            provider_context: Provider context for accessing strategies
            logger: Logging port for operation logging
            error_handler: Error handling port for exception management
        """
        super().__init__(logger, error_handler)
        self.provider_context = provider_context

    async def execute_query(self, query: GetProviderStrategyConfigQuery) -> Dict[str, Any]:
        """Execute provider strategy configuration query."""
        self.logger.info(f"Getting strategy config for provider: {query.provider_name}")

        try:
            # Get provider strategy
            strategy = self.provider_context.get_strategy(query.provider_name)
            if not strategy:
                return {
                    "provider_name": query.provider_name,
                    "configuration": {},
                    "error": f"Provider '{query.provider_name}' not found",
                }

            # Get configuration
            config = {
                "provider_name": query.provider_name,
                "strategy_type": getattr(strategy, "strategy_type", "unknown"),
                "configuration": getattr(strategy, "configuration", {}),
                "default_settings": getattr(strategy, "default_settings", {}),
            }

            # Try to get detailed configuration if available
            if hasattr(strategy, "get_configuration"):
                detailed_config = strategy.get_configuration()
                config.update(detailed_config)

            self.logger.info(f"Retrieved strategy config for provider: {query.provider_name}")
            return config

        except Exception as e:
            self.logger.error(f"Failed to get provider strategy config: {e}")
            raise
