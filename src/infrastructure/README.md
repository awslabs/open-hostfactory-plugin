# Infrastructure Layer - Technical Implementations

The infrastructure layer provides technical implementations of domain interfaces and handles all external system interactions. This layer contains the technical concerns that support the business logic without polluting the domain layer.

## Architecture Overview

### Clean Architecture Compliance
```
Infrastructure Layer → Application Layer → Domain Layer
```

**Key Principles:**
- Implements domain interfaces
- Handles external system integration
- Provides technical utilities and cross-cutting concerns
- Zero business logic (pure technical implementation)

### Dependency Inversion
- High-level modules (domain) define interfaces
- Low-level modules (infrastructure) implement interfaces
- Dependencies point inward toward the domain

## Package Structure

### 📁 `persistence/` - Data Persistence
Comprehensive data persistence layer with multiple storage strategies.

**Key Features:**
- **Multiple Storage Strategies**: JSON, SQL, DynamoDB
- **Repository Pattern**: Domain repository implementations
- **Event Sourcing**: Complete audit trail of changes
- **Automatic Strategy Selection**: Based on configuration and load
- **Data Migration**: Between storage strategies
- **Concurrency Control**: Optimistic locking and conflict resolution

**Components:**
- **`repositories/`**: Repository implementations for each aggregate
- **`components/`**: Reusable storage components
- **`json/`**: JSON file-based storage implementation
- **`sql/`**: SQL database storage implementation
- **`dynamodb/`**: AWS DynamoDB storage implementation
- **`base/`**: Base classes and interfaces
- **`factories/`**: Repository factory implementations

### 📁 `events/` - Event Infrastructure
Event sourcing and publishing infrastructure.

**Key Features:**
- **Event Store**: Persistent event storage
- **Event Publisher**: Reliable event publishing
- **Event Registry**: Event type registration and discovery
- **Event Handlers**: Infrastructure event processing
- **Deduplication**: Prevents duplicate event processing

**Components:**
- **`publisher.py`**: Event publishing infrastructure
- **Event Store**: Persistent event storage implementations
- **Event Handlers**: Infrastructure-level event processing

### 📁 `di/` - Dependency Injection
Inversion of Control (IoC) container and service registration.

**Key Features:**
- **Service Registration**: Automatic service discovery
- **Lifecycle Management**: Singleton, transient, and scoped services
- **Configuration Integration**: Services configured from settings
- **Provider Integration**: Cloud provider service registration

**Components:**
- **`container.py`**: Main IoC container implementation
- **`services.py`**: Service registration and configuration
- **`exceptions.py`**: DI-specific exceptions

### 📁 `resilience/` - Resilience Patterns
Retry mechanisms, circuit breakers, and error handling.

**Key Features:**
- **Retry Strategies**: Exponential backoff, fixed delay, custom strategies
- **Circuit Breaker**: Fail-fast for unreliable services
- **Timeout Handling**: Configurable operation timeouts
- **Error Classification**: Transient vs permanent error handling

**Components:**
- **`strategies/`**: Different resilience strategy implementations
- **`retry_decorator.py`**: Decorator-based retry implementation
- **`config.py`**: Resilience configuration
- **`exceptions.py`**: Resilience-specific exceptions

### 📁 `logging/` - Logging Infrastructure
Structured logging with multiple outputs and formats.

**Key Features:**
- **Structured Logging**: JSON and text formats
- **Multiple Outputs**: Console, file, remote logging
- **Log Rotation**: Automatic log file rotation
- **Performance Logging**: Request timing and performance metrics
- **Correlation IDs**: Request tracing across components

**Components:**
- **`logger.py`**: Main logging implementation
- **`logger_singleton.py`**: Singleton logger access

### 📁 `interfaces/` - Technical Interfaces
Technical interfaces that were moved from domain layer.

**Key Components:**
- **`provider.py`**: Cloud provider interface contracts
- **`resource_manager.py`**: Resource management interfaces
- **`instance_manager.py`**: Instance management interfaces

**Design Note:**
These interfaces were moved from domain to infrastructure as they represent technical contracts rather than business concepts.

### 📁 `ports/` - External System Ports
Adapters for external system integration.

**Key Components:**
- **`cloud_resource_manager_port.py`**: Cloud resource management port
- **`resource_provisioning_port.py`**: Resource provisioning port
- **`request_adapter_port.py`**: Request adaptation port
- **`logger_port.py`**: Logging port

### 📁 `adapters/` - External System Adapters
Concrete implementations of external system ports.

**Key Components:**
- **`configuration_adapter.py`**: Configuration system adapter

### 📁 `utilities/` - Infrastructure Utilities
Common technical utilities and helper functions.

**Key Features:**
- **Common Utilities**: Shared technical functions
- **Factory Patterns**: Object creation utilities
- **Serialization**: JSON and other format handling
- **Validation**: Technical validation utilities

**Components:**
- **`common/`**: Common utility functions
- **`factories/`**: Factory pattern implementations

### 📁 `error/` - Error Handling Infrastructure
Centralized error handling and middleware.

**Key Features:**
- **Error Middleware**: Request/response error handling
- **Error Classification**: Technical vs business error separation
- **Error Reporting**: Structured error reporting
- **Error Recovery**: Automatic error recovery strategies

**Components:**
- **`error_handler.py`**: Main error handling logic
- **`error_middleware.py`**: Middleware for error processing

### 📁 `handlers/` - Infrastructure Handlers
Technical handlers for infrastructure concerns.

**Components:**
- **`base/`**: Base handler implementations

### 📁 `patterns/` - Infrastructure Patterns
Common infrastructure design patterns.

**Key Components:**
- **`singleton_registry.py`**: Singleton pattern implementation
- **`singleton_access.py`**: Singleton access utilities
- **`lazy_import.py`**: Lazy loading pattern

### 📁 `serialization/` - Serialization Infrastructure
Data serialization and deserialization utilities.

**Key Components:**
- **`encoders.py`**: Custom JSON encoders for domain objects

## Key Infrastructure Features

### 1. Multi-Strategy Persistence

**Automatic Strategy Selection:**
```python
class RepositoryFactory:
    """Factory for creating repositories with appropriate storage strategy."""
    
    def create_request_repository(self) -> RequestRepository:
        """Create request repository with optimal storage strategy."""
        config = self._get_repository_config()
        
        if config.type == "json":
            return JSONRequestRepository(config.json)
        elif config.type == "sql":
            return SQLRequestRepository(config.sql)
        elif config.type == "dynamodb":
            return DynamoDBRequestRepository(config.dynamodb)
        else:
            raise UnsupportedStorageTypeError(config.type)
```

**Storage Strategy Components:**
- **Single File**: All data in one JSON file
- **Multi File**: Separate files per aggregate type
- **SQL Database**: Relational database storage
- **DynamoDB**: NoSQL cloud storage

### 2. Event Sourcing Infrastructure

**Event Store Implementation:**
```python
class EventStore:
    """Persistent event storage with deduplication."""
    
    async def append_events(self, 
                          aggregate_id: str, 
                          events: List[DomainEvent],
                          expected_version: int) -> None:
        """Append events to store with optimistic concurrency control."""
        # Check for concurrent modifications
        current_version = await self._get_aggregate_version(aggregate_id)
        if current_version != expected_version:
            raise ConcurrencyConflictError(
                f"Expected version {expected_version}, got {current_version}"
            )
        
        # Store events with deduplication
        for event in events:
            if not await self._event_exists(event.event_id):
                await self._store_event(aggregate_id, event)
```

### 3. Resilience Infrastructure

**Retry Decorator:**
```python
@retry_with_backoff(
    max_attempts=3,
    backoff_strategy=ExponentialBackoffStrategy(
        initial_delay=1.0,
        max_delay=30.0,
        multiplier=2.0
    ),
    retry_on=[ConnectionError, TimeoutError],
    stop_on=[AuthenticationError, ValidationError]
)
async def provision_resources(self, request: ProvisionRequest) -> List[str]:
    """Provision resources with automatic retry on transient failures."""
    return await self._cloud_provider.provision_instances(request)
```

**Circuit Breaker:**
```python
class CircuitBreaker:
    """Circuit breaker for external service calls."""
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self._state == CircuitState.OPEN:
            if not self._should_attempt_reset():
                raise CircuitBreakerOpenError("Circuit breaker is open")
            self._state = CircuitState.HALF_OPEN
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
```

### 4. Dependency Injection Container

**Service Registration:**
```python
class DIContainer:
    """Dependency injection container."""
    
    def register_singleton(self, 
                          interface: Type[T], 
                          implementation: Type[T]) -> None:
        """Register singleton service."""
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            lifetime=ServiceLifetime.SINGLETON
        )
    
    def resolve(self, service_type: Type[T]) -> T:
        """Resolve service instance."""
        descriptor = self._services.get(service_type)
        if not descriptor:
            raise ServiceNotRegisteredError(service_type)
        
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            return self._get_or_create_singleton(descriptor)
        else:
            return self._create_instance(descriptor)
```

### 5. Structured Logging

**Logger Configuration:**
```python
def setup_logging(config: LoggingConfig) -> None:
    """Set up structured logging with multiple outputs."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.level.upper()))
    
    # Console handler
    if config.console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            StructuredFormatter(config.format)
        )
        logger.addHandler(console_handler)
    
    # File handler with rotation
    if config.file_path:
        file_handler = RotatingFileHandler(
            config.file_path,
            maxBytes=config.max_size,
            backupCount=config.backup_count
        )
        file_handler.setFormatter(
            StructuredFormatter(config.format)
        )
        logger.addHandler(file_handler)
```

## Repository Implementations

### Base Repository Pattern
```python
class BaseRepository(ABC):
    """Base repository with common infrastructure concerns."""
    
    def __init__(self, storage_strategy: BaseStorageStrategy):
        self._storage = storage_strategy
        self._event_publisher = get_event_publisher()
        self._logger = get_logger(__name__)
    
    async def save(self, aggregate: AggregateRoot) -> None:
        """Save aggregate and publish events."""
        try:
            # Save aggregate data
            await self._storage.save(aggregate)
            
            # Extract and publish domain events
            events = aggregate.get_domain_events()
            if events:
                await self._event_publisher.publish_events(events)
                aggregate.clear_domain_events()
            
            self._logger.info(f"Saved {type(aggregate).__name__} with {len(events)} events")
            
        except Exception as e:
            self._logger.error(f"Failed to save {type(aggregate).__name__}: {str(e)}")
            raise
```

### Specific Repository Implementation
```python
class RequestRepository(BaseRepository):
    """Request repository with request-specific operations."""
    
    async def find_by_status(self, status: RequestStatus) -> List[Request]:
        """Find requests by status with caching."""
        cache_key = f"requests_by_status_{status.value}"
        
        # Try cache first
        cached_result = await self._cache.get(cache_key)
        if cached_result:
            return [Request.from_dict(data) for data in cached_result]
        
        # Query storage
        request_data = await self._storage.find_by_field("status", status.value)
        requests = [Request.from_dict(data) for data in request_data]
        
        # Cache result
        await self._cache.set(cache_key, 
                            [req.to_dict() for req in requests], 
                            ttl=300)
        
        return requests
```

## Configuration Integration

### Configuration Adapter
```python
class ConfigurationAdapter:
    """Adapter for configuration system integration."""
    
    def __init__(self, config_manager: ConfigurationManager):
        self._config_manager = config_manager
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration."""
        return self._config_manager.get_database_config()
    
    def get_aws_config(self) -> AWSConfig:
        """Get AWS configuration."""
        return self._config_manager.get_aws_config()
    
    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration."""
        return self._config_manager.get_logging_config()
```

## Performance Monitoring

### Performance Metrics
```python
class PerformanceMonitor:
    """Monitor infrastructure performance."""
    
    async def monitor_operation(self, 
                              operation_name: str,
                              operation: Callable) -> Any:
        """Monitor operation performance."""
        start_time = time.time()
        
        try:
            result = await operation()
            
            duration = time.time() - start_time
            self._record_success_metric(operation_name, duration)
            
            if duration > self._slow_operation_threshold:
                await self._handle_slow_operation(operation_name, duration)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self._record_error_metric(operation_name, duration, type(e).__name__)
            raise
```

## Testing Infrastructure

### Test Utilities
```python
class InMemoryRepository(BaseRepository):
    """In-memory repository for testing."""
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._events: List[DomainEvent] = []
    
    async def save(self, aggregate: AggregateRoot) -> None:
        """Save aggregate in memory."""
        self._data[str(aggregate.id)] = aggregate.to_dict()
        
        # Collect events for testing
        events = aggregate.get_domain_events()
        self._events.extend(events)
        aggregate.clear_domain_events()
    
    def get_published_events(self) -> List[DomainEvent]:
        """Get events for testing verification."""
        return self._events.copy()
```

## Error Handling Patterns

### Infrastructure Error Handling
```python
class InfrastructureErrorHandler:
    """Handle infrastructure-level errors."""
    
    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Handle infrastructure error with appropriate response."""
        if isinstance(error, ConnectionError):
            await self._handle_connection_error(error, context)
        elif isinstance(error, TimeoutError):
            await self._handle_timeout_error(error, context)
        elif isinstance(error, ConfigurationError):
            await self._handle_configuration_error(error, context)
        else:
            await self._handle_unexpected_error(error, context)
```

## Future Extensions

### Adding New Storage Strategies
1. Implement `BaseStorageStrategy` interface
2. Add configuration support
3. Register with repository factory
4. Add migration support

### Adding New Cloud Providers
1. Implement provider interfaces in `interfaces/`
2. Add provider-specific adapters
3. Register with DI container
4. Add configuration support

### Adding New Resilience Patterns
1. Implement new strategy in `resilience/strategies/`
2. Add configuration options
3. Integrate with existing decorators
4. Add monitoring and metrics

---

This infrastructure layer provides a robust, scalable, and maintainable foundation for the application while maintaining clean separation from business logic.
