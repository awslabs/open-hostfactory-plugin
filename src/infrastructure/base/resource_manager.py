"""
Infrastructure Base Resource Manager - Unified implementation foundation.

This module provides the unified base implementation for all resource managers,
eliminating the confusion between multiple ResourceManager classes and providing
a single source of truth for infrastructure resource management patterns.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from src.domain.base.ports import LoggingPort
from src.domain.base.resource_manager import (
    ResourceAllocation,
    ResourceId,
    ResourceManagerPort,
    ResourceSpecification,
    ResourceType,
)
from src.infrastructure.error.exception_handler import InfrastructureErrorResponse

T = TypeVar("T")  # For provider-specific client types


class BaseResourceManager(ResourceManagerPort, ABC):
    """
    Unified base resource manager implementation.

    This class eliminates the confusion between multiple ResourceManager classes
    by providing a single, well-designed base implementation that all concrete
    resource managers should inherit from.

    Features:
    - Unified logging and error handling
    - Performance monitoring and metrics
    - Retry logic for transient failures
    - Resource lifecycle management
    - Provider-agnostic interface implementation
    """

    def __init__(self, logger: Optional[LoggingPort] = None):
        """Initialize base resource manager."""
        self.logger = logger
        self._metrics: Dict[str, Any] = {}
        self.max_retries = 3
        self.retry_delay = 2.0

    async def provision_resources(self, specification: ResourceSpecification) -> ResourceAllocation:
        """
        Provision resources with monitoring and retry logic.

        Template method that provides consistent resource provisioning
        across all resource manager implementations.
        """
        operation_id = f"{self.__class__.__name__}.provision_resources"
        start_time = time.time()

        if self.logger:
            self.logger.info(
                f"Starting resource provisioning: { specification.name} ({ specification.resource_type.value})"
            )

        try:
            # Validate specification
            await self.validate_specification(specification)

            # Check quota before provisioning
            await self.check_quota(specification)

            # Provision with retry logic
            allocation = await self._provision_with_retry(specification)

            # Post-provisioning validation
            await self.validate_allocation(allocation)

            duration = time.time() - start_time
            if self.logger:
                self.logger.info(f"Resource provisioned successfully: { allocation.resource_id} in { duration:.3f}s")

            self._record_metric(operation_id, duration, "success")
            return allocation

        except Exception as e:
            duration = time.time() - start_time
            if self.logger:
                self.logger.error(f"Resource provisioning failed: { specification.name} in {duration:.3f}s - { str(e)}")

            self._record_metric(operation_id, duration, "error", str(e))
            raise

    async def deprovision_resources(self, allocation: ResourceAllocation) -> None:
        """
        Deprovision resources with monitoring and cleanup.

        Template method that provides consistent resource deprovisioning
        across all resource manager implementations.
        """
        operation_id = f"{self.__class__.__name__}.deprovision_resources"
        start_time = time.time()

        if self.logger:
            self.logger.info(f"Starting resource deprovisioning: {allocation.resource_id}")

        try:
            # Pre-deprovisioning checks
            await self.validate_deprovisioning(allocation)

            # Deprovision with retry logic
            await self._deprovision_with_retry(allocation)

            # Post-deprovisioning cleanup
            await self.cleanup_after_deprovisioning(allocation)

            duration = time.time() - start_time
            if self.logger:
                self.logger.info(f"Resource deprovisioned successfully: { allocation.resource_id} in { duration:.3f}s")

            self._record_metric(operation_id, duration, "success")

        except Exception as e:
            duration = time.time() - start_time
            if self.logger:
                self.logger.error(
                    f"Resource deprovisioning failed: { allocation.resource_id} in {duration:.3f}s - { str(e)}"
                )

            self._record_metric(operation_id, duration, "error", str(e))
            raise

    async def get_resource_status(self, resource_id: ResourceId) -> ResourceAllocation:
        """Get resource status with caching and monitoring."""
        operation_id = f"{self.__class__.__name__}.get_resource_status"
        start_time = time.time()

        try:
            allocation = await self.fetch_resource_status(resource_id)

            duration = time.time() - start_time
            self._record_metric(operation_id, duration, "success")

            return allocation

        except Exception as e:
            duration = time.time() - start_time
            self._record_metric(operation_id, duration, "error", str(e))
            raise

    async def list_resources(self, resource_type: Optional[ResourceType] = None) -> List[ResourceAllocation]:
        """List resources with filtering and monitoring."""
        operation_id = f"{self.__class__.__name__}.list_resources"
        start_time = time.time()

        try:
            resources = await self.fetch_resource_list(resource_type)

            duration = time.time() - start_time
            if self.logger:
                self.logger.debug(f"Listed {len(resources)} resources in {duration:.3f}s")

            self._record_metric(operation_id, duration, "success")
            return resources

        except Exception as e:
            duration = time.time() - start_time
            self._record_metric(operation_id, duration, "error", str(e))
            raise

    async def get_resource_quota(self, resource_type: ResourceType, region: Optional[str] = None) -> Dict[str, Any]:
        """Get resource quota with caching."""
        operation_id = f"{self.__class__.__name__}.get_resource_quota"
        start_time = time.time()

        try:
            quota = await self.fetch_resource_quota(resource_type, region)

            duration = time.time() - start_time
            self._record_metric(operation_id, duration, "success")

            return quota

        except Exception as e:
            duration = time.time() - start_time
            self._record_metric(operation_id, duration, "error", str(e))
            raise

    # Template methods for concrete implementations

    async def validate_specification(self, specification: ResourceSpecification) -> None:
        """
        Validate resource specification before provisioning.

        Override in concrete implementations for provider-specific validation.
        """
        if not specification.name:
            raise ValueError("Resource name is required")
        if not specification.configuration:
            raise ValueError("Resource configuration is required")

    async def check_quota(self, specification: ResourceSpecification) -> None:
        """
        Check if quota allows for resource provisioning.

        Override in concrete implementations for provider-specific quota checks.
        """
        try:
            quota = await self.get_resource_quota(specification.resource_type, specification.region)
            # Basic quota check - override for more sophisticated logic
            if quota.get("available", 0) <= 0:
                raise ValueError(f"Insufficient quota for {specification.resource_type.value}")
        except Exception:
            # If quota check fails, log warning but don't block provisioning
            if self.logger:
                self.logger.warning(f"Could not check quota for {specification.resource_type.value}")

    async def validate_allocation(self, allocation: ResourceAllocation) -> None:
        """
        Validate resource allocation after provisioning.

        Override in concrete implementations for provider-specific validation.
        """
        if not allocation.resource_id:
            raise ValueError("Resource allocation must have a valid resource_id")
        if not allocation.is_active() and not allocation.is_provisioning():
            raise ValueError(f"Resource allocation has invalid status: {allocation.status}")

    async def validate_deprovisioning(self, allocation: ResourceAllocation) -> None:
        """
        Validate that resource can be deprovisioned.

        Override in concrete implementations for provider-specific checks.
        """
        if not allocation.resource_id:
            raise ValueError("Cannot deprovision resource without valid resource_id")

    async def cleanup_after_deprovisioning(self, allocation: ResourceAllocation) -> None:
        """
        Cleanup after successful deprovisioning.

        Override in concrete implementations for provider-specific cleanup.
        """
        if self.logger:
            self.logger.debug(f"Cleanup completed for resource: {allocation.resource_id}")

    # Abstract methods that must be implemented by concrete classes

    @abstractmethod
    async def execute_provisioning(self, specification: ResourceSpecification) -> ResourceAllocation:
        """
        Execute the actual resource provisioning.

        Must be implemented by concrete resource managers.
        """

    @abstractmethod
    async def execute_deprovisioning(self, allocation: ResourceAllocation) -> None:
        """
        Execute the actual resource deprovisioning.

        Must be implemented by concrete resource managers.
        """

    @abstractmethod
    async def fetch_resource_status(self, resource_id: ResourceId) -> ResourceAllocation:
        """
        Fetch current resource status from provider.

        Must be implemented by concrete resource managers.
        """

    @abstractmethod
    async def fetch_resource_list(self, resource_type: Optional[ResourceType] = None) -> List[ResourceAllocation]:
        """
        Fetch list of resources from provider.

        Must be implemented by concrete resource managers.
        """

    @abstractmethod
    async def fetch_resource_quota(self, resource_type: ResourceType, region: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch resource quota information from provider.

        Must be implemented by concrete resource managers.
        """

    # Private helper methods

    async def _provision_with_retry(self, specification: ResourceSpecification) -> ResourceAllocation:
        """Provision resources with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                return await self.execute_provisioning(specification)
            except Exception as e:
                if attempt == self.max_retries:
                    raise
                else:
                    if self.logger:
                        self.logger.warning(f"Provisioning attempt {attempt + 1} failed: {str(e)}")
                    await asyncio.sleep(self.retry_delay * (attempt + 1))

    async def _deprovision_with_retry(self, allocation: ResourceAllocation) -> None:
        """Deprovision resources with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                await self.execute_deprovisioning(allocation)
                return
            except Exception as e:
                if attempt == self.max_retries:
                    raise
                else:
                    if self.logger:
                        self.logger.warning(f"Deprovisioning attempt {attempt + 1} failed: {str(e)}")
                    await asyncio.sleep(self.retry_delay * (attempt + 1))

    def _record_metric(self, operation: str, duration: float, status: str, error: Optional[str] = None) -> None:
        """Record performance metrics."""
        self._metrics[operation] = {
            "duration": duration,
            "status": status,
            "timestamp": datetime.utcnow(),
            "error": error,
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return self._metrics.copy()

    def handle_error(self, error: Exception, context: str) -> InfrastructureErrorResponse:
        """Handle errors consistently."""
        if self.logger:
            self.logger.error(f"Resource manager error in {context}: {str(error)}")

        return InfrastructureErrorResponse.from_exception(error, context)


class CloudProviderResourceManager(BaseResourceManager, Generic[T]):
    """
    Base class for cloud provider-specific resource managers.

    Provides additional functionality specific to cloud providers,
    such as client management and provider-specific error handling.
    """

    def __init__(self, provider_client: T, logger: Optional[LoggingPort] = None):
        """Initialize with provider-specific client."""
        super().__init__(logger)
        self.provider_client = provider_client
        self.provider_name = self.__class__.__name__.replace("ResourceManager", "").replace("Impl", "")

    async def validate_provider_connection(self) -> bool:
        """
        Validate connection to cloud provider.

        Override in concrete implementations for provider-specific validation.
        """
        try:
            # Basic connectivity check - override for provider-specific logic
            await self.fetch_resource_quota(ResourceType.COMPUTE_INSTANCE)
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Provider connection validation failed: {str(e)}")
            return False

    def get_provider_name(self) -> str:
        """Get the name of the cloud provider."""
        return self.provider_name
