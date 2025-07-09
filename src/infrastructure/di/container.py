"""
Dependency Injection Container implementation.

This container implements the domain DI contracts while preserving all existing
functionality. It bridges the domain DI abstractions with concrete infrastructure
implementation, maintaining Clean Architecture principles.
"""
from typing import Dict, Any, Type, TypeVar, Optional, Callable, cast, Set, List, Union
import inspect
import sys
import time
from contextlib import contextmanager
from typing import Iterator

# Domain imports (Clean Architecture compliant)
from src.domain.base.dependency_injection import (
    DependencyInjectionPort, is_injectable, get_injectable_metadata,
    InjectableMetadata, is_singleton
)
from src.domain.base.di_contracts import (
    DIContainerPort, DependencyRegistration, DIScope, DILifecycle,
    CQRSHandlerRegistrationPort, DependencyResolutionError as DomainDependencyResolutionError,
    CircularDependencyError as DomainCircularDependencyError,
    DependencyRegistrationError
)
from src.domain.base.ports import ContainerPort

# Infrastructure imports
from src.infrastructure.logging.logger import get_logger
from src.infrastructure.di.exceptions import (
    DependencyResolutionError,
    UnregisteredDependencyError,
    UntypedParameterError,
    CircularDependencyError,
    InstantiationError,
    FactoryError
)

T = TypeVar('T')
logger = get_logger(__name__)

@contextmanager
def timed_operation(operation_name: str) -> Iterator[None]:
    """Context manager to time and log an operation."""
    start_time = time.time()
    try:
        yield
    finally:
        elapsed_time = time.time() - start_time
        logger.debug(f"{operation_name} completed in {elapsed_time:.4f}s")


class DIContainer(DIContainerPort, CQRSHandlerRegistrationPort, ContainerPort):
    """
    Dependency injection container implementing domain contracts.
    
    This container bridges domain DI abstractions with infrastructure implementation,
    maintaining Clean Architecture while preserving all existing functionality.
    
    Features:
    - Implements domain DIContainerPort interface
    - Supports CQRS handler registration
    - Preserves existing @injectable decorator functionality
    - Enhanced with domain DI metadata system
    - Backward compatible with existing code
    """
    
    def __init__(self):
        """Initialize container with enhanced domain support."""
        # Existing functionality preserved
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable] = {}
        self._instances: Dict[Type, Any] = {}
        self._resolution_stack: Set[Type] = set()
        
        # Enhanced domain DI support
        self._registrations: Dict[Type, DependencyRegistration] = {}
        self._cqrs_command_handlers: Dict[Type, Type] = {}
        self._cqrs_query_handlers: Dict[Type, Type] = {}
        self._cqrs_event_handlers: Dict[Type, List[Type]] = {}
        
        # Configuration
        self._auto_registration_enabled = True
        self._circular_dependency_detection = True
        self._lazy_loading_enabled = True
        self._factories: Dict[Type, Callable[..., Any]] = {}
        self._instances: Dict[Type, Any] = {}
        
    def is_registered(self, cls: Type) -> bool:
        """
        Check if a type is registered with the container.
        
        Args:
            cls: Class type to check
            
        Returns:
            True if the type is registered, False otherwise
        """
        return (
            cls in self._singletons or
            cls in self._factories or
            cls in self._instances
        )
    
    def has(self, service_type: Type[T]) -> bool:
        """
        Check if service is registered in container (ContainerPort interface).
        
        Args:
            service_type: Service type to check
            
        Returns:
            True if service is registered, False otherwise
        """
        return self.is_registered(service_type)
        
    def register_singleton(self, cls: Type[T], instance_or_factory: Any = None) -> None:
        """
        Register a singleton type.
        
        Args:
            cls: Class type to register
            instance_or_factory: Optional pre-created instance or factory function
        """
        if instance_or_factory is None:
            # No instance provided, register the class itself
            self._singletons[cls] = cls
            logger.debug(f"Registered singleton type {cls.__name__}")
        elif callable(instance_or_factory) and not isinstance(instance_or_factory, type):
            # It's a factory function - execute it immediately
            try:
                instance = instance_or_factory(self)
                self._singletons[cls] = instance
                logger.debug(f"Registered singleton from factory for {cls.__name__}")
            except Exception as e:
                logger.error(f"Failed to create singleton from factory for {cls.__name__}: {str(e)}")
                raise FactoryError(cls, f"Factory function failed: {str(e)}", e)
        else:
            # It's a pre-created instance
            self._singletons[cls] = instance_or_factory
            logger.debug(f"Registered pre-created singleton for {cls.__name__}")
            
    def register_factory(self, cls: Type[T], factory: Callable[..., T]) -> None:
        """
        Register a factory function for a type.
        
        Args:
            cls: Class type to register
            factory: Factory function to create instances
        """
        self._factories[cls] = factory
        cls_name = cls.__name__ if hasattr(cls, '__name__') else str(cls)
        logger.debug(f"Registered factory for {cls_name}")
        
    def register_instance(self, cls: Type[T], instance: T) -> None:
        """
        Register a specific instance for a type.
        
        Args:
            cls: Class type to register
            instance: Instance to use
        """
        self._instances[cls] = instance
        logger.debug(f"Registered instance for {cls.__name__}")
        
    def get(self, cls: Type[T], parent_type: Optional[Type] = None, 
            parameter_name: Optional[str] = None, 
            dependency_chain: Optional[Set[Type]] = None) -> T:
        """
        Get an instance of the specified type.
        
        Args:
            cls: Class type to get
            parent_type: Optional parent type that requires this dependency
            parameter_name: Optional parameter name in the parent type
            dependency_chain: Optional chain of dependencies being resolved to detect circular dependencies
            
        Returns:
            Instance of the requested type
            
        Raises:
            DependencyResolutionError: If the dependency cannot be resolved
        """
        # Get class name safely for logging
        class_name = cls.__name__ if hasattr(cls, '__name__') else str(cls)
        
        # Initialize or update dependency chain for circular dependency detection
        if dependency_chain is None:
            dependency_chain = set()
        
        # Check for circular dependencies
        if cls in dependency_chain:
            # Create a list representation of the dependency chain for the error message
            chain_list = list(dependency_chain)
            chain_list.append(cls)  # Add the current class to complete the circle
            raise CircularDependencyError(chain_list)
        
        # Add current class to dependency chain
        new_chain = dependency_chain.copy()
        new_chain.add(cls)
        
        logger.debug(f"Resolving dependency: {class_name}" + 
                    (f" for {parent_type.__name__}" if parent_type else "") +
                    (f" parameter '{parameter_name}'" if parameter_name else ""))
        
        with timed_operation(f"Resolve {class_name}"):
            # Check for pre-registered instance
            if cls in self._instances:
                logger.debug(f"Found pre-registered instance for {class_name}")
                return cast(T, self._instances[cls])
            
            # Check for singleton
            if cls in self._singletons:
                if isinstance(self._singletons[cls], type):
                    # Create singleton instance
                    logger.debug(f"Creating singleton instance for {class_name}")
                    try:
                        instance = self._create_instance(self._singletons[cls], new_chain)
                        self._singletons[cls] = instance
                        logger.debug(f"Singleton instance created for {class_name}")
                        return cast(T, instance)
                    except DependencyResolutionError as e:
                        # Re-raise with updated parent information if not already set
                        if not e.parent_type and parent_type:
                            raise DependencyResolutionError(
                                e.dependency_type,
                                str(e),
                                parent_type,
                                parameter_name,
                                e
                            ) from e
                        raise
                else:
                    # Return existing singleton instance
                    logger.debug(f"Using existing singleton instance for {class_name}")
                    return cast(T, self._singletons[cls])
            
            # Check for factory
            if cls in self._factories:
                logger.debug(f"Using factory to create instance of {class_name}")
                try:
                    instance = self._factories[cls](self)
                    logger.debug(f"Factory successfully created instance of {class_name}")
                    return cast(T, instance)
                except Exception as e:
                    logger.error(f"Factory failed to create instance of {class_name}: {str(e)}")
                    raise FactoryError(cls, f"Factory function failed: {str(e)}", e)
            
            # Check if class has @injectable decorator
            if hasattr(cls, '_injectable') and cls._injectable:
                logger.debug(f"Class {class_name} has @injectable decorator, resolving constructor dependencies")
                try:
                    # Get constructor signature and resolve dependencies
                    import inspect
                    sig = inspect.signature(cls.__init__)
                    kwargs = {}
                    
                    for param_name, param in sig.parameters.items():
                        if param_name == 'self':
                            continue
                            
                        param_type = param.annotation
                        
                        # Handle string annotations (from __future__ import annotations)
                        if isinstance(param_type, str):
                            param_type = self._resolve_string_annotation(param_type, cls)
                        
                        if param_type != inspect.Parameter.empty:
                            # Resolve dependency from container
                            dependency = self.get(param_type, cls, param_name, new_chain)
                            kwargs[param_name] = dependency
                    
                    instance = cls(**kwargs)
                    logger.debug(f"Successfully created @injectable instance of {class_name}")
                    return cast(T, instance)
                except Exception as e:
                    logger.error(f"Failed to create @injectable instance of {class_name}: {str(e)}")
                    raise InstantiationError(cls, f"@injectable constructor failed: {str(e)}", cause=e)
            
            # Try to create instance directly
            logger.debug(f"No registration found for {class_name}, attempting direct creation")
            try:
                return self._create_instance(cls, new_chain)
            except DependencyResolutionError as e:
                # Re-raise with updated parent information if not already set
                if not e.parent_type and parent_type:
                    raise DependencyResolutionError(
                        e.dependency_type,
                        str(e),
                        parent_type,
                        parameter_name,
                        e
                    ) from e
                raise
            except Exception as e:
                # If direct creation fails and no specific error is raised,
                # assume the dependency is not registered
                logger.error(f"Failed to create instance of {class_name}: {str(e)}")
                raise UnregisteredDependencyError(cls, parent_type, parameter_name) from e
    
    def _resolve_string_annotation(self, annotation: str, context_class: Type) -> Type:
        """
        Resolve string type annotations to actual types.
        
        This handles the case where 'from __future__ import annotations' is used,
        making all type annotations strings instead of actual types.
        """
        try:
            # Get the module where the context class is defined
            module = sys.modules[context_class.__module__]
            
            # Try to resolve the annotation in the module's namespace
            if hasattr(module, annotation):
                resolved_type = getattr(module, annotation)
                if isinstance(resolved_type, type):
                    return resolved_type
            
            # Try to resolve from globals in the module
            if hasattr(module, '__dict__') and annotation in module.__dict__:
                resolved_type = module.__dict__[annotation]
                if isinstance(resolved_type, type):
                    return resolved_type
            
            # Common type mappings for built-in types
            type_mappings = {
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'list': list,
                'dict': dict,
                'Any': Any,
            }
            
            if annotation in type_mappings:
                return type_mappings[annotation]
            
            # If we can't resolve it, try eval in the module's context
            # This is a fallback and should be used carefully
            try:
                resolved_type = eval(annotation, module.__dict__)
                if isinstance(resolved_type, type):
                    return resolved_type
            except (NameError, AttributeError, SyntaxError, TypeError) as e:
                logger.debug(f"Could not resolve annotation '{annotation}' in {context_class.__name__}: {e}")
                pass
            
            # If all else fails, return the string (will cause an error later)
            logger.warning(f"Could not resolve string annotation '{annotation}' in context of {context_class}")
            return annotation
            
        except Exception as e:
            logger.warning(f"Error resolving string annotation '{annotation}': {e}")
            return annotation

    def _create_instance(self, cls: Type[T], dependency_chain: Optional[Set[Type]] = None) -> T:
        """
        Create an instance of the specified type with dependencies.
        
        Args:
            cls: Class type to create
            dependency_chain: Optional chain of dependencies being resolved to detect circular dependencies
            
        Returns:
            Created instance
            
        Raises:
            DependencyResolutionError: If dependencies cannot be resolved
        """
        # Get class name safely
        class_name = cls.__name__ if hasattr(cls, '__name__') else str(cls)
        
        logger.debug(f"Creating instance of {class_name}")
        
        # Initialize dependency chain if not provided
        if dependency_chain is None:
            dependency_chain = {cls}
        
        with timed_operation(f"Create instance of {class_name}"):
            try:
                # Get constructor signature
                try:
                    signature = inspect.signature(cls.__init__)
                except (ValueError, TypeError) as e:
                    logger.error(f"Failed to get constructor signature for {class_name}: {str(e)}")
                    raise InstantiationError(cls, f"Failed to get constructor signature: {str(e)}", cause=e)
                
                # Skip self parameter
                params = list(signature.parameters.values())[1:]
                
                # Log dependencies
                if params:
                    logger.debug(f"Dependencies for {class_name}: {[p.name + ': ' + str(p.annotation) for p in params]}")
                else:
                    logger.debug(f"No dependencies for {class_name}")
                
                # Resolve dependencies
                args = []
                for param in params:
                    param_annotation = param.annotation
                    
                    # Handle string annotations (from __future__ import annotations)
                    if isinstance(param_annotation, str):
                        param_annotation = self._resolve_string_annotation(param_annotation, cls)
                    
                    if param_annotation == inspect.Parameter.empty:
                        # Cannot resolve untyped parameter
                        logger.error(f"Cannot resolve untyped parameter '{param.name}' for {class_name}")
                        raise UntypedParameterError(cls, param.name)
                    
                    # Get dependency
                    try:
                        logger.debug(f"Resolving dependency '{param.name}' of type {param_annotation} for {class_name}")
                        dependency = self.get(param_annotation, cls, param.name, dependency_chain)
                        args.append(dependency)
                        logger.debug(f"Successfully resolved dependency '{param.name}' for {class_name}")
                    except DependencyResolutionError:
                        # Re-raise DependencyResolutionError as is
                        raise
                    except Exception as e:
                        logger.error(f"Failed to resolve dependency '{param.name}' of type {param_annotation} for {class_name}: {str(e)}")
                        raise DependencyResolutionError(
                            param_annotation, 
                            f"Failed to resolve dependency: {str(e)}", 
                            cls, 
                            param.name, 
                            e
                        ) from e
                
                # Create instance
                try:
                    instance = cls(*args)
                    logger.debug(f"Successfully created instance of {class_name}")
                    return instance
                except Exception as e:
                    logger.error(f"Failed to instantiate {class_name} with resolved dependencies: {str(e)}")
                    raise InstantiationError(cls, f"Failed to instantiate with resolved dependencies: {str(e)}", cause=e)
                
            except DependencyResolutionError:
                # Re-raise DependencyResolutionError as is
                raise
            except Exception as e:
                logger.error(f"Unexpected error creating instance of {class_name}: {str(e)}")
                raise InstantiationError(cls, f"Unexpected error: {str(e)}", cause=e)
    
    def clear(self) -> None:
        """Clear all registrations."""
        self._singletons.clear()
        self._factories.clear()
        self._instances.clear()
        logger.debug("Cleared all registrations")
    
    # Domain Contract Implementation - DIContainerPort
    
    def register(self, registration: DependencyRegistration) -> None:
        """
        Register a dependency with full configuration (Domain Contract).
        
        Args:
            registration: Complete registration information
        """
        self._registrations[registration.dependency_type] = registration
        
        if registration.has_instance():
            self._instances[registration.dependency_type] = registration.instance
        elif registration.has_factory():
            if registration.is_singleton():
                self.register_singleton(registration.dependency_type, registration.factory)
            else:
                self.register_factory(registration.dependency_type, registration.factory)
        elif registration.is_singleton():
            self.register_singleton(registration.dependency_type, registration.implementation_type)
        else:
            # Register as transient
            self._factories[registration.dependency_type] = lambda: registration.implementation_type()
        
        logger.debug(f"Registered {registration.dependency_type.__name__} with domain registration")
    
    def register_type(
        self, 
        dependency_type: Type[T], 
        implementation_type: Optional[Type[T]] = None,
        scope: DIScope = DIScope.TRANSIENT
    ) -> None:
        """
        Register a type with optional implementation (Domain Contract).
        
        Args:
            dependency_type: The interface or base type
            implementation_type: The concrete implementation
            scope: The dependency scope
        """
        impl_type = implementation_type or dependency_type
        
        registration = DependencyRegistration(
            dependency_type=dependency_type,
            implementation_type=impl_type,
            scope=scope
        )
        
        self.register(registration)
    
    def register_instance(self, dependency_type: Type[T], instance: T) -> None:
        """
        Register a pre-created instance (Domain Contract).
        
        Args:
            dependency_type: The type to register
            instance: The instance to register
        """
        registration = DependencyRegistration(
            dependency_type=dependency_type,
            instance=instance,
            scope=DIScope.SINGLETON
        )
        
        self.register(registration)
    
    def get_optional(self, dependency_type: Type[T]) -> Optional[T]:
        """
        Resolve an optional dependency (Domain Contract).
        
        Args:
            dependency_type: The type to resolve
            
        Returns:
            Instance of the requested type or None if not registered
        """
        try:
            return self.get(dependency_type)
        except (DependencyResolutionError, UnregisteredDependencyError):
            return None
    
    def get_all(self, dependency_type: Type[T]) -> List[T]:
        """
        Resolve all instances of a type (Domain Contract).
        
        Args:
            dependency_type: The type to resolve
            
        Returns:
            List of all registered instances of the type
        """
        instances = []
        
        # Check for direct registration
        if self.is_registered(dependency_type):
            try:
                instance = self.get(dependency_type)
                instances.append(instance)
            except DependencyResolutionError as e:
                logger.warning(f"Failed to resolve registered dependency {dependency_type.__name__}: {e}")
                # Continue collecting other instances
            except Exception as e:
                logger.error(f"Unexpected error resolving {dependency_type.__name__}: {e}")
                # Continue but log the unexpected error
        
        return instances
    
    def unregister(self, dependency_type: Type[T]) -> bool:
        """
        Unregister a dependency (Domain Contract).
        
        Args:
            dependency_type: The type to unregister
            
        Returns:
            True if unregistered, False if not found
        """
        found = False
        
        if dependency_type in self._singletons:
            del self._singletons[dependency_type]
            found = True
        
        if dependency_type in self._factories:
            del self._factories[dependency_type]
            found = True
        
        if dependency_type in self._instances:
            del self._instances[dependency_type]
            found = True
        
        if hasattr(self, '_registrations') and dependency_type in self._registrations:
            del self._registrations[dependency_type]
            found = True
        
        if found:
            logger.debug(f"Unregistered {dependency_type.__name__}")
        
        return found
    
    def get_registrations(self) -> Dict[Type, DependencyRegistration]:
        """
        Get all current registrations (Domain Contract).
        
        Returns:
            Dictionary mapping types to their registrations
        """
        if hasattr(self, '_registrations'):
            return self._registrations.copy()
        return {}
    
    # CQRS Handler Registration Implementation
    
    def register_command_handler(self, command_type: Type, handler_type: Type) -> None:
        """
        Register a command handler (CQRS Contract).
        
        Args:
            command_type: The command type
            handler_type: The handler implementation type
        """
        if not hasattr(self, '_cqrs_command_handlers'):
            self._cqrs_command_handlers = {}
        
        self._cqrs_command_handlers[command_type] = handler_type
        
        # Also register the handler in the main container
        if is_injectable(handler_type):
            metadata = get_injectable_metadata(handler_type)
            if metadata and metadata.singleton:
                self.register_singleton(handler_type)
        
        logger.debug(f"Registered command handler {handler_type.__name__} for {command_type.__name__}")
    
    def register_query_handler(self, query_type: Type, handler_type: Type) -> None:
        """
        Register a query handler (CQRS Contract).
        
        Args:
            query_type: The query type
            handler_type: The handler implementation type
        """
        if not hasattr(self, '_cqrs_query_handlers'):
            self._cqrs_query_handlers = {}
        
        self._cqrs_query_handlers[query_type] = handler_type
        
        # Also register the handler in the main container
        if is_injectable(handler_type):
            metadata = get_injectable_metadata(handler_type)
            if metadata and metadata.singleton:
                self.register_singleton(handler_type)
        
        logger.debug(f"Registered query handler {handler_type.__name__} for {query_type.__name__}")
    
    def register_event_handler(self, event_type: Type, handler_type: Type) -> None:
        """
        Register an event handler (CQRS Contract).
        
        Args:
            event_type: The event type
            handler_type: The handler implementation type
        """
        if not hasattr(self, '_cqrs_event_handlers'):
            self._cqrs_event_handlers = {}
        
        if event_type not in self._cqrs_event_handlers:
            self._cqrs_event_handlers[event_type] = []
        
        self._cqrs_event_handlers[event_type].append(handler_type)
        
        # Also register the handler in the main container
        if is_injectable(handler_type):
            metadata = get_injectable_metadata(handler_type)
            if metadata and metadata.singleton:
                self.register_singleton(handler_type)
        
        logger.debug(f"Registered event handler {handler_type.__name__} for {event_type.__name__}")
    
    def get_command_handler(self, command_type: Type) -> Any:
        """
        Get command handler for command type (CQRS Contract).
        
        Args:
            command_type: The command type
            
        Returns:
            Handler instance
        """
        if not hasattr(self, '_cqrs_command_handlers') or command_type not in self._cqrs_command_handlers:
            raise DomainDependencyResolutionError(
                command_type, 
                f"No command handler registered for {command_type.__name__}"
            )
        
        handler_type = self._cqrs_command_handlers[command_type]
        return self.get(handler_type)
    
    def get_query_handler(self, query_type: Type) -> Any:
        """
        Get query handler for query type (CQRS Contract).
        
        Args:
            query_type: The query type
            
        Returns:
            Handler instance
        """
        if not hasattr(self, '_cqrs_query_handlers') or query_type not in self._cqrs_query_handlers:
            raise DomainDependencyResolutionError(
                query_type,
                f"No query handler registered for {query_type.__name__}"
            )
        
        handler_type = self._cqrs_query_handlers[query_type]
        return self.get(handler_type)
    
    def get_event_handlers(self, event_type: Type) -> List[Any]:
        """
        Get all event handlers for event type (CQRS Contract).
        
        Args:
            event_type: The event type
            
        Returns:
            List of handler instances
        """
        if not hasattr(self, '_cqrs_event_handlers') or event_type not in self._cqrs_event_handlers:
            return []
        
        handler_types = self._cqrs_event_handlers[event_type]
        return [self.get(handler_type) for handler_type in handler_types]
    
    # Enhanced Injectable Support
    
    def register_injectable_class(self, cls: Type[T]) -> None:
        """
        Register a single @injectable class.
        
        Args:
            cls: The class to register
        """
        if not is_injectable(cls):
            return
        
        metadata = get_injectable_metadata(cls)
        if not metadata:
            # Fallback for classes with old-style @injectable
            if is_singleton(cls):
                self.register_singleton(cls)
            return
        
        registration = DependencyRegistration(
            dependency_type=cls,
            implementation_type=cls,
            scope=DIScope.SINGLETON if metadata.singleton else DIScope.TRANSIENT,
            lifecycle=DILifecycle.LAZY if metadata.lazy else DILifecycle.EAGER,
            dependencies=metadata.dependencies,
            factory=metadata.factory
        )
        
        self.register(registration)
        
        # Register CQRS handlers
        if hasattr(cls, '_cqrs_handler') and cls._cqrs_handler:
            handler_type = getattr(cls, '_handler_type', None)
            
            if handler_type == 'command' and hasattr(cls, '_command_type'):
                self.register_command_handler(cls._command_type, cls)
            elif handler_type == 'query' and hasattr(cls, '_query_type'):
                self.register_query_handler(cls._query_type, cls)
            elif handler_type == 'event' and hasattr(cls, '_event_type'):
                self.register_event_handler(cls._event_type, cls)
        
        logger.debug(f"Auto-registered @injectable class {cls.__name__}")


# Global container instance
_container: Optional[DIContainer] = None

def get_container() -> DIContainer:
    """
    Get the global container instance.
    
    Returns:
        Global container instance
    """
    global _container
    if _container is None:
        _container = DIContainer()
        _setup_core_dependencies(_container)
    return _container


def _setup_cqrs_infrastructure(container: DIContainer) -> None:
    """Setup CQRS infrastructure: handler discovery and buses."""
    from src.infrastructure.di.handler_discovery import create_handler_discovery_service
    from src.infrastructure.di.buses import BusFactory
    from src.domain.base.ports import LoggingPort
    
    logger.info("Setting up CQRS infrastructure")
    
    # Step 1: Discover and register all handlers
    logger.info("Creating handler discovery service")
    discovery_service = create_handler_discovery_service(container)
    
    logger.info("Starting handler discovery")
    discovery_service.discover_and_register_handlers()
    
    # Check registration results
    from src.application.decorators import get_handler_registry_stats
    stats = get_handler_registry_stats()
    logger.info(f"Handler discovery results: {stats}")
    
    # Step 2: Create and register buses
    logger.info("Creating CQRS buses")
    logging_port = container.get(LoggingPort)
    query_bus, command_bus = BusFactory.create_buses(container, logging_port)
    
    # Register buses as singletons
    from src.infrastructure.di.buses import QueryBus, CommandBus
    container.register_instance(QueryBus, query_bus)
    container.register_instance(CommandBus, command_bus)
    
    logger.info("CQRS infrastructure setup complete")


def _setup_core_dependencies(container: DIContainer) -> None:
    """Setup core dependencies required by CQRS handlers."""
    from src.infrastructure.utilities.factories.repository_factory import UnitOfWorkFactory as ConcreteUnitOfWorkFactory
    from src.domain.base import UnitOfWorkFactory as AbstractUnitOfWorkFactory
    from src.infrastructure.adapters.logging_adapter import LoggingAdapter
    from src.infrastructure.adapters.container_adapter import ContainerAdapter
    from src.config.manager import get_config_manager
    from src.config.manager import ConfigurationManager
    
    # Register ConfigurationManager as singleton (it's already a singleton)
    config_manager = get_config_manager()
    container.register_singleton(ConfigurationManager, lambda c: config_manager)
    
    # Register LoggingPort first (needed by UnitOfWorkFactory)
    from src.domain.base.ports import LoggingPort
    container.register_singleton(LoggingPort, lambda c: LoggingAdapter("cqrs.handlers"))
    
    # Register UnitOfWorkFactory (single registration for clean resolution)
    container.register_instance(AbstractUnitOfWorkFactory, ConcreteUnitOfWorkFactory(config_manager, LoggingAdapter("unit_of_work")))
    
    # Setup CQRS Handler Discovery and Buses
    _setup_cqrs_infrastructure(container)
    
    # Note: ContainerPort registration moved to port_registrations.py to avoid circular dependency

def reset_container() -> None:
    """Reset the global container instance."""
    global _container
    if _container:
        _container.clear()
    _container = None
