"""
Application Service - Main orchestrator for the application layer.

This service coordinates between different bounded contexts and provides
a unified interface for external consumers (API, CLI, etc.).

Architecture:
- Uses CQRS for complex operations (requests, machines)
- Uses Service pattern for simple operations (templates)
- No fallback logic - clear boundaries between patterns
- Dependency injection instead of singletons
"""
from typing import Dict, Any, List, Optional, TYPE_CHECKING

# Domain imports
from src.domain.base.ports import LoggingPort, ContainerPort, ConfigurationPort, ErrorHandlingPort
from src.domain.base.dependency_injection import injectable

# Exception handling through ErrorHandlingPort (Clean Architecture compliant)

# Type checking imports
from src.providers.base.strategy import ProviderContext
from src.application.base.commands import CommandBus
from src.application.base.queries import QueryBus

@injectable
class ApplicationService:
    """
    Main application service orchestrating all operations.
    
    Uses dependency injection instead of singletons for better testability
    and cleaner architecture.
    """
    
    def __init__(self, 
                 provider_type: str,
                 command_bus: CommandBus,
                 query_bus: QueryBus,
                 logger: LoggingPort,
                 container: ContainerPort,
                 config: ConfigurationPort,
                 error_handler: ErrorHandlingPort,
                 provider_context: ProviderContext):  # REQUIRED, not optional
        """
        Initialize ApplicationService with strategy mode only.
        
        Args:
            provider_type: Type of provider (kept for backward compatibility)
            command_bus: Bus for handling commands
            query_bus: Bus for handling queries
            logger: Logging port for application logging
            container: Container port for dependency resolution
            config: Configuration port for accessing configuration
            provider_context: Provider context for strategy pattern (REQUIRED)
        """
        if not provider_type:
            raise ValueError("Provider type is required")
        if not provider_context:
            raise ValueError("Provider context is required")
            
        self._provider_type = provider_type
        self._command_bus = command_bus
        self._query_bus = query_bus
        self._logger = logger
        self._container = container
        self._config = config
        self._error_handler = error_handler
        self._provider_context = provider_context  # Always required
        self._initialized = False
    
    
    @property
    def provider_type(self) -> str:
        """Get the provider type."""
        return self._provider_type
    
    
    def initialize(self) -> bool:
        """Initialize the application service in strategy mode."""
        if self._initialized:
            return True
        
        self._logger.info("Initializing ApplicationService in strategy mode")
        
        try:
            # Initialize provider context
            if not self._provider_context:
                raise ValueError("Provider context is required")
            
            # Initialize provider context if it has an initialize method
            if hasattr(self._provider_context, 'initialize'):
                if not self._provider_context.initialize():
                    raise RuntimeError("Failed to initialize provider context")
            
            # Log provider strategy information
            if hasattr(self._provider_context, 'get_available_strategies'):
                strategies = self._provider_context.get_available_strategies()
                strategy_names = [getattr(s, 'name', 'unknown') for s in strategies]
                self._logger.info(f"Provider strategy mode initialized with strategies: {strategy_names}")
            
            self._initialized = True
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to initialize ApplicationService: {str(e)}")
            return False
            if hasattr(self._provider_context, 'get_available_strategies'):
                strategies = self._provider_context.get_available_strategies()
                strategy_names = [s.name for s in strategies] if strategies else []
                self._logger.info(f"Provider strategy mode initialized with strategies: {strategy_names}")
            
            self._initialized = True
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to initialize ApplicationService: {str(e)}")
            return False
    
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about current provider configuration.
        
        Returns:
            Dictionary with provider information
        """
        self._ensure_initialized()
        
        try:
            if not self._provider_context:
                return {"mode": "strategy", "error": "Provider context not available"}
            
            # Get provider strategy factory for detailed info
            try:
                factory = self._container.get('ProviderStrategyFactory')
                return factory.get_provider_info()
            except Exception:
                # Fallback to basic context info
                strategies = getattr(self._provider_context, 'get_available_strategies', lambda: [])()
                return {
                    "mode": "strategy",
                    "available_strategies": len(strategies),
                    "strategy_names": [getattr(s, 'name', 'unknown') for s in strategies]
                }
                
        except Exception as e:
            return {"mode": "strategy", "error": str(e)}
            if not self._provider_context:
                return {"mode": "strategy", "error": "Provider context not available"}
            
            # Get provider strategy factory for detailed info
            try:
                factory = self._container.get('ProviderStrategyFactory')
                return factory.get_provider_info()
            except Exception:
                # Fallback to basic context info
                strategies = getattr(self._provider_context, 'get_available_strategies', lambda: [])()
                return {
                    "mode": "strategy",
                    "available_strategies": len(strategies),
                    "strategy_names": [getattr(s, 'name', 'unknown') for s in strategies]
                }
                
        except Exception as e:
            return {"mode": "strategy", "error": str(e)}
    
    def _ensure_initialized(self):
        """Ensure the service is initialized."""
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Application service not initialized")
    
    # =============================================================================
    # MACHINE REQUEST OPERATIONS (Complex Business Logic - CQRS Pattern)
    # =============================================================================
    
    
    def request_machines(self, 
                        template_id: str, 
                        machine_count: int,
                        timeout: Optional[int] = None,
                        tags: Optional[Dict[str, str]] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Request new machines using CQRS CommandBus.
        
        This is a complex operation that orchestrates multiple steps:
        1. Validation of input parameters
        2. Command creation and enrichment
        3. CQRS dispatch with proper error handling
        
        Args:
            template_id: ID of the template to use
            machine_count: Number of machines to request
            timeout: Optional timeout in seconds
            tags: Optional tags to apply to machines
            metadata: Optional metadata for the request
            
        Returns:
            str: Request ID for tracking the operation
            
        Raises:
            ValidationError: If input parameters are invalid
            ApplicationError: If the operation fails
        """
        self._ensure_initialized()
        
        # Input validation (enhanced)
        if not template_id or not template_id.strip():
            raise ValueError("template_id cannot be empty")
        if machine_count <= 0:
            raise ValueError("machine_count must be positive")
        if machine_count > 100:  # Reasonable limit
            raise ValueError("machine_count cannot exceed 100")
        
        # Import DOMAIN command type (not DTO)
        from src.application.dto.commands import CreateRequestCommand
        
        # Prepare metadata with additional info (enhanced)
        request_metadata = metadata or {}
        request_metadata.update({
            'timeout': timeout,
            'tags': tags or {},
            'created_via': 'ApplicationService.request_machines',
            'validation_passed': True,
            'request_timestamp': self._get_current_timestamp()
        })
        
        # Create DOMAIN command
        command = CreateRequestCommand(
            template_id=template_id,
            machine_count=machine_count,
            timeout=timeout,
            tags=tags or {},
            metadata=request_metadata
        )
        
        # Dispatch through CommandBus
        request_id = self._command_bus.dispatch(command)
        
        # Log successful operation
        self._logger.info(f"Machine request created successfully: {request_id}")
        
        return request_id

    
    def request_return_machines(self, 
                               machine_ids: List[str],
                               requester_id: Optional[str] = None,
                               reason: Optional[str] = None,
                               timeout: Optional[int] = None,
                               metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Terminate machines using CQRS CommandBus.
        
        This is a complex operation that orchestrates multiple steps:
        1. Validation of machine IDs
        2. Command creation and enrichment
        3. CQRS dispatch with proper error handling
        
        Args:
            machine_ids: List of machine IDs to terminate
            requester_id: Optional ID of the requester
            reason: Optional reason for termination
            timeout: Optional timeout in seconds
            metadata: Optional metadata for the request
            
        Returns:
            str: Request ID for tracking the operation
            
        Raises:
            ValidationError: If input parameters are invalid
            ApplicationError: If the operation fails
        """
        self._ensure_initialized()
        
        # Input validation (enhanced)
        if not machine_ids:
            raise ValueError("machine_ids cannot be empty")
        if len(machine_ids) > 50:  # Reasonable limit
            raise ValueError("Cannot terminate more than 50 machines at once")
        
        # Validate machine ID format
        for machine_id in machine_ids:
            if not machine_id or not machine_id.strip():
                raise ValueError("All machine_ids must be non-empty")
        
        # Import DOMAIN command type (not DTO)
        from src.application.dto.commands import CreateReturnRequestCommand
        
        # Prepare metadata with additional info (enhanced)
        request_metadata = metadata or {}
        request_metadata.update({
            'requester_id': requester_id,
            'reason': reason,
            'timeout': timeout,
            'machine_count': len(machine_ids),
            'created_via': 'ApplicationService.request_return_machines',
            'validation_passed': True,
            'request_timestamp': self._get_current_timestamp()
        })
        
        # Create DOMAIN command
        command = CreateReturnRequestCommand(
            machine_ids=machine_ids,
            metadata=request_metadata
        )
        
        # Dispatch through CommandBus
        request_id = self._command_bus.dispatch(command)
        
        # Log successful operation
        self._logger.info(f"Machine return request created successfully: {request_id}")
        
        return request_id

    
    def get_machine_status(self, machine_ids: List[str]) -> List[Dict[str, Any]]:
        """Get machine status using CQRS QueryBus."""
        self._ensure_initialized()
        
        # Import query type
        from src.application.machine.queries import GetMachineStatusQuery
        
        # Create query
        query = GetMachineStatusQuery(machine_ids=machine_ids)
        
        # Execute through QueryBus
        machines = self._query_bus.dispatch(query)
        return [machine.model_dump() if hasattr(machine, 'model_dump') else machine for machine in machines]

    
    def get_request_status(self, request_id: str) -> Dict[str, Any]:
        """Get request status using CQRS QueryBus."""
        self._ensure_initialized()
        
        # Import query type
        from src.application.dto.queries import GetRequestStatusQuery
        
        # Create query
        query = GetRequestStatusQuery(request_id=request_id)
        
        # Execute through QueryBus
        status = self._query_bus.dispatch(query)
        return status.to_dict() if hasattr(status, 'to_dict') else status

    
    def get_request(self, request_id: str, long: bool = False) -> Dict[str, Any]:
        """Get full request details using CQRS QueryBus."""
        self._ensure_initialized()
        
        # Create query for full request details
        from src.application.dto.queries import GetRequestQuery
        query = GetRequestQuery(request_id=request_id, long=long)
        
        # Execute through QueryBus to get RequestDTO
        request_dto = self._query_bus.dispatch(query)
        
        # Convert DTO to dictionary
        return request_dto.to_dict()

    
    def get_return_requests(self, 
                           status: Optional[str] = None, 
                           requester_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get return requests with optional filtering using CQRS QueryBus."""
        self._ensure_initialized()
        
        # Import query type
        from src.application.dto.queries import ListReturnRequestsQuery
        
        # Create query with parameters
        query = ListReturnRequestsQuery(status=status, requester_id=requester_id)
            
        # Execute through QueryBus
        requests = self._query_bus.dispatch(query)
        return [request.model_dump() if hasattr(request, 'model_dump') else request for request in requests]

    
    def get_machines_by_request(self, request_id: str) -> List[Dict[str, Any]]:
        """Get all machines for a specific request using CQRS QueryBus."""
        self._ensure_initialized()
        
        # Import query type
        from src.application.dto.queries import ListMachinesQuery
        
        # Create query with request_id filter
        query = ListMachinesQuery(request_id=request_id)
        
        # Execute through QueryBus
        machines = self._query_bus.dispatch(query)
        return [machine.model_dump() if hasattr(machine, 'model_dump') else machine for machine in machines]

    
    def get_provider_health(self) -> bool:
        """Check if the cloud provider is healthy and accessible."""
        # If we have a provider instance, use its health check
        if hasattr(self, '_provider') and self._provider and hasattr(self._provider, 'health_check'):
            health_result = self._provider.health_check()
            return health_result.get('status') == 'healthy' if isinstance(health_result, dict) else bool(health_result)
        
        # If no provider is configured, return False
        if not hasattr(self, '_provider') or not self._provider:
            return False
        
        # Fallback: Simple health check - if we can get templates, provider is healthy
        self.get_available_templates()
        return True

    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get detailed information about the configured provider."""
        if not hasattr(self, '_provider_type') or not self._provider_type:
            return {
                "provider_type": "none", 
                "status": "not_configured",
                "message": "No provider configured"
            }
        
        # If we have provider_type but no provider instance, it's not initialized
        if not hasattr(self, '_provider') or not self._provider:
            return {
                "provider_type": self._provider_type,
                "status": "not_initialized"
            }
        
        # Get basic provider info
        info = {
            "provider_type": self._provider_type,
            "status": "configured",
            "healthy": self.get_provider_health()
        }
        
        # If we have a provider instance, get its capabilities
        if hasattr(self._provider, 'get_capabilities'):
            try:
                capabilities = self._provider.get_capabilities()
                info.update(capabilities)
            except Exception as e:
                self._logger.warning(
                    f"Failed to get provider capabilities: {e}",
                    extra={"provider_type": self._provider_type}
                )
        
        # Add template count if available
        try:
            templates = self.get_available_templates()  # List[Template]
            info["templates_available"] = len(templates)
        except Exception:
            info["templates_available"] = 0
        
        return info

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format for metadata."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def __str__(self) -> str:
        """String representation of ApplicationService for debugging."""
        provider_type = getattr(self, '_provider_type', 'unknown')
        return f"ApplicationService(provider={provider_type})"

    def __repr__(self) -> str:
        """Detailed representation of ApplicationService for debugging."""
        provider_type = getattr(self, '_provider_type', 'unknown')
        return f"ApplicationService(provider={provider_type})"

    # =============================================================================
    # LEGACY COMPATIBILITY METHODS (Deprecated - Use CQRS methods above)
    # =============================================================================
    
    def create_request(self, 
                      template_id: str, 
                      machine_count: int,
                      timeout: Optional[int] = None,
                      tags: Optional[Dict[str, str]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new machine request (Legacy method - use request_machines instead).
        
        This method delegates to the CQRS method.
        """
        self._logger.warning("create_request is deprecated, use request_machines instead")
        return self.request_machines(template_id, machine_count, timeout, tags, metadata)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_application_service(provider_type: str) -> ApplicationService:
    """
    Factory function to create ApplicationService with proper dependencies.
    
    This replaces the singleton pattern with a factory that sets up all dependencies.
    Provider type must be explicitly specified.
    """
    # Use injected container port instead of direct import
    # This will be handled by the DI system, not called directly
    raise NotImplementedError("Use DI container to create ApplicationService instead of factory function")
    command_bus = container.get(CommandBus)
    query_bus = container.get(QueryBus)
    
    # Create and return service
    return ApplicationService(
        provider_type=provider_type,
        template_service=template_service,
        command_bus=command_bus,
        query_bus=query_bus
    )


def get_application_service() -> ApplicationService:
    """
    Get ApplicationService instance (Legacy compatibility).
    
    This maintains compatibility while using the new factory approach.
    """
    return create_application_service()
