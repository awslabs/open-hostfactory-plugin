# Application Layer - Use Cases and Orchestration

The application layer orchestrates domain objects and coordinates business workflows. It implements the CQRS (Command Query Responsibility Segregation) pattern for complex operations while using simpler service patterns for basic CRUD operations.

This layer contains 41 files implementing comprehensive use cases and business workflow orchestration.

## Architecture Overview

### Mixed Pattern Architecture
The application layer uses different patterns based on complexity:

**CQRS Pattern** (Complex Operations):
- **Commands**: Write operations with business logic
- **Queries**: Read operations with data projection
- **Handlers**: Use case implementations

**Service Pattern** (Simple Operations):
- **Services**: Direct CRUD operations
- **DTOs**: Data transfer objects

### Dependency Flow
```
API Layer → Application Layer → Domain Layer
```

## Package Structure

### 📁 `base/` - Base Application Components
Foundation classes and interfaces for the application layer.

**Key Components:**
- **`commands.py`**: Base command and command bus interfaces
- **`queries.py`**: Base query and query bus interfaces
- **Command/Query Bus**: Message routing infrastructure

### 📁 `dto/` - Data Transfer Objects
Objects for transferring data between layers and external systems.

**Key Components:**
- **`base.py`**: Base DTO classes with validation
- **`commands.py`**: Command DTOs for write operations
- **`queries.py`**: Query DTOs for read operations
- **`responses.py`**: Response DTOs for API layer

**Design Principles:**
- Immutable data structures
- Input validation and sanitization
- Layer boundary enforcement
- Serialization support

### 📁 `commands/` - Command Handlers (Write Operations)
Implements write operations using CQRS pattern for complex business logic.

**Key Components:**
- **`handlers.py`**: Main command handlers
- **`request_handlers.py`**: Request-specific command handlers
- **`machine_handlers.py`**: Machine-specific command handlers
- **`cleanup_handlers.py`**: Cleanup and maintenance handlers

**Command Types:**
- **CreateRequestCommand**: Create new provisioning request
- **UpdateRequestStatusCommand**: Update request status
- **TerminateMachinesCommand**: Terminate machine instances
- **CleanupExpiredRequestsCommand**: Clean up old requests

### 📁 `queries/` - Query Handlers (Read Operations)
Implements read operations using CQRS pattern for complex data projections.

**Key Components:**
- **`handlers.py`**: Main query handlers
- **`request_handlers.py`**: Request-specific query handlers
- **`machine_handlers.py`**: Machine-specific query handlers
- **`specialized_handlers.py`**: Complex query handlers

**Query Types:**
- **GetRequestStatusQuery**: Get request status and details
- **GetAvailableTemplatesQuery**: Get available VM templates
- **GetMachinesByRequestQuery**: Get machines for a request
- **GetReturnRequestsQuery**: Get return requests

### 📁 `events/` - Event Handlers
Handles domain events for cross-cutting concerns and workflow coordination.

**Event Handler Categories:**
- **Audit Handlers**: Log business events for audit trail
- **Notification Handlers**: Send notifications for important events
- **Workflow Handlers**: Coordinate multi-step business processes
- **Monitoring Handlers**: Update metrics and health status

**Key Event Handlers:**
- **RequestCreatedHandler**: Handle new request creation
- **MachineProvisionedHandler**: Handle machine provisioning
- **RequestCompletedHandler**: Handle request completion
- **ErrorOccurredHandler**: Handle error conditions

### 📁 `template/` - Template Services
Simple service pattern for template management (CRUD operations).

**Key Components:**
- **`service.py`**: Template service implementation
- **`dto.py`**: Template-specific DTOs
- **`commands.py`**: Template command definitions
- **`queries.py`**: Template query definitions

**Operations:**
- Get available templates
- Validate template configurations
- Resolve template parameters

### 📁 `request/` - Request Use Cases
Request-specific application logic and DTOs.

**Key Components:**
- **`commands.py`**: Request command definitions
- **`queries.py`**: Request query definitions
- **`dto.py`**: Request-specific DTOs

### 📁 `machine/` - Machine Use Cases
Machine-specific application logic and DTOs.

**Key Components:**
- **`commands.py`**: Machine command definitions
- **`queries.py`**: Machine query definitions
- **`dto.py`**: Machine-specific DTOs

### 📁 `interfaces/` - Application Interfaces
Contracts and interfaces for application layer components.

**Key Components:**
- **`command_query.py`**: Command and query interface definitions

## CQRS Implementation

### Command Side (Write Operations)

**Command Pattern:**
```python
@dataclass(frozen=True)
class CreateRequestCommand:
    """Command to create a new provisioning request."""
    template_id: str
    machine_count: int
    request_type: RequestType = RequestType.PROVISION
    timeout: Optional[int] = None
    tags: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None
```

**Command Handler:**
```python
class CreateRequestHandler:
    """Handler for CreateRequestCommand."""
    
    def __init__(self, 
                 request_repository: RequestRepository,
                 template_repository: TemplateRepository):
        self._request_repository = request_repository
        self._template_repository = template_repository
    
    async def handle(self, command: CreateRequestCommand) -> RequestId:
        """Handle request creation command."""
        # Validate template exists
        template = await self._template_repository.find_by_id(command.template_id)
        if not template:
            raise TemplateNotFoundError(command.template_id)
        
        # Create request aggregate
        request = Request.create_new_request(
            template_id=command.template_id,
            machine_count=command.machine_count,
            request_type=command.request_type,
            timeout=command.timeout,
            tags=Tags(command.tags) if command.tags else None,
            metadata=command.metadata
        )
        
        # Save request (events will be published automatically)
        await self._request_repository.save(request)
        
        return request.request_id
```

### Query Side (Read Operations)

**Query Pattern:**
```python
@dataclass(frozen=True)
class GetRequestStatusQuery:
    """Query to get request status and details."""
    request_id: str
```

**Query Handler:**
```python
class GetRequestStatusHandler:
    """Handler for GetRequestStatusQuery."""
    
    def __init__(self, request_repository: RequestRepository):
        self._request_repository = request_repository
    
    async def handle(self, query: GetRequestStatusQuery) -> RequestStatusDTO:
        """Handle request status query."""
        request_id = RequestId(query.request_id)
        request = await self._request_repository.find_by_id(request_id)
        
        if not request:
            raise RequestNotFoundError(query.request_id)
        
        return RequestStatusDTO(
            request_id=str(request.request_id.value),
            status=request.status.value,
            machine_count=request.machine_count,
            machine_ids=request.machine_ids,
            created_at=request.created_at,
            updated_at=request.updated_at,
            completed_at=request.completed_at,
            error_message=request.error_message
        )
```

## Service Pattern Implementation

### Template Service (Simple CRUD)
For simple operations that don't require complex business logic:

```python
class TemplateService:
    """Service for template management operations."""
    
    def __init__(self, template_repository: TemplateRepository):
        self._template_repository = template_repository
    
    async def get_available_templates(self) -> List[TemplateDTO]:
        """Get all available templates."""
        templates = await self._template_repository.find_all()
        return [self._to_dto(template) for template in templates]
    
    async def get_template_by_id(self, template_id: str) -> Optional[TemplateDTO]:
        """Get template by ID."""
        template = await self._template_repository.find_by_id(template_id)
        return self._to_dto(template) if template else None
```

## Event-Driven Coordination

### Domain Event Handling
Application layer responds to domain events for cross-cutting concerns:

```python
class RequestCreatedHandler:
    """Handle RequestCreatedEvent for audit and notification."""
    
    def __init__(self, 
                 audit_service: AuditService,
                 notification_service: NotificationService):
        self._audit_service = audit_service
        self._notification_service = notification_service
    
    async def handle(self, event: RequestCreatedEvent) -> None:
        """Handle request created event."""
        # Log for audit trail
        await self._audit_service.log_event(
            event_type="REQUEST_CREATED",
            request_id=str(event.request_id.value),
            details={
                "template_id": event.template_id,
                "machine_count": event.machine_count,
                "created_at": event.created_at.isoformat()
            }
        )
        
        # Send notification if configured
        if self._should_notify_on_request_created():
            await self._notification_service.send_notification(
                message=f"New request created: {event.request_id.value}",
                details=event
            )
```

## Application Service Orchestration

### Main Application Service
Coordinates between different patterns and bounded contexts:

```python
class ApplicationService:
    """Main application service orchestrating all operations."""
    
    def __init__(self, 
                 provider_type: str,
                 template_service: TemplateService,  # Service pattern
                 command_bus: CommandBus,            # CQRS commands
                 query_bus: QueryBus,               # CQRS queries
                 provider: Optional[ProviderInterface] = None):
        self._provider_type = provider_type
        self._template_service = template_service
        self._command_bus = command_bus
        self._query_bus = query_bus
        self._provider = provider
    
    # Simple operations use service pattern
    async def get_available_templates(self) -> List[TemplateDTO]:
        """Get available templates (simple operation)."""
        return await self._template_service.get_available_templates()
    
    # Complex operations use CQRS pattern
    async def request_machines(self, 
                             template_id: str, 
                             machine_count: int) -> str:
        """Request machines (complex operation)."""
        command = CreateRequestCommand(
            template_id=template_id,
            machine_count=machine_count
        )
        request_id = await self._command_bus.dispatch(command)
        return str(request_id.value)
    
    async def get_request_status(self, request_id: str) -> RequestStatusDTO:
        """Get request status (complex query)."""
        query = GetRequestStatusQuery(request_id=request_id)
        return await self._query_bus.dispatch(query)
```

## Data Transfer Objects (DTOs)

### Input Validation
DTOs provide input validation and sanitization:

```python
@dataclass(frozen=True)
class CreateRequestDTO:
    """DTO for creating a new request."""
    template_id: str
    machine_count: int
    request_type: str = "provision"
    timeout: Optional[int] = None
    tags: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        """Validate DTO fields."""
        if not self.template_id or not self.template_id.strip():
            raise ValueError("Template ID cannot be empty")
        
        if self.machine_count <= 0:
            raise ValueError("Machine count must be positive")
        
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("Timeout must be positive")
```

### Response Formatting
DTOs format responses for external consumers:

```python
@dataclass(frozen=True)
class RequestStatusDTO:
    """DTO for request status response."""
    request_id: str
    status: str
    machine_count: int
    machine_ids: List[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "requestId": self.request_id,
            "status": self.status,
            "machineCount": self.machine_count,
            "machineIds": self.machine_ids,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "errorMessage": self.error_message
        }
```

## Error Handling

### Application-Level Exceptions
Application layer defines its own exception hierarchy:

```python
class ApplicationException(Exception):
    """Base application exception."""
    pass

class ValidationError(ApplicationException):
    """Input validation error."""
    pass

class BusinessRuleViolationError(ApplicationException):
    """Business rule violation error."""
    pass

class ResourceNotFoundError(ApplicationException):
    """Resource not found error."""
    pass
```

### Error Handling Patterns
```python
async def handle_command(self, command: Command) -> Any:
    """Handle command with proper error handling."""
    try:
        # Validate command
        self._validate_command(command)
        
        # Execute business logic
        result = await self._execute_command(command)
        
        return result
        
    except DomainException as e:
        # Domain errors are business rule violations
        raise BusinessRuleViolationError(str(e)) from e
    
    except ValidationError:
        # Re-raise validation errors
        raise
    
    except Exception as e:
        # Wrap unexpected errors
        raise ApplicationException(f"Command execution failed: {str(e)}") from e
```

## Testing Strategy

### Unit Testing
Test application logic in isolation:

```python
class TestCreateRequestHandler:
    """Test CreateRequestHandler."""
    
    @pytest.fixture
    def handler(self):
        """Create handler with mocked dependencies."""
        request_repo = Mock(spec=RequestRepository)
        template_repo = Mock(spec=TemplateRepository)
        return CreateRequestHandler(request_repo, template_repo)
    
    async def test_handle_valid_command(self, handler):
        """Test handling valid create request command."""
        # Arrange
        command = CreateRequestCommand(
            template_id="template-1",
            machine_count=2
        )
        
        # Mock template exists
        template = Mock(spec=Template)
        handler._template_repository.find_by_id.return_value = template
        
        # Act
        result = await handler.handle(command)
        
        # Assert
        assert isinstance(result, RequestId)
        handler._request_repository.save.assert_called_once()
```

### Integration Testing
Test layer interactions:

```python
async def test_request_machines_integration():
    """Test complete request machines workflow."""
    # Arrange
    app_service = create_application_service()
    
    # Act
    request_id = await app_service.request_machines(
        template_id="template-1",
        machine_count=2
    )
    
    # Assert
    status = await app_service.get_request_status(request_id)
    assert status.status == "PENDING"
    assert status.machine_count == 2
```

## Future Extensions

### Adding New Use Cases
1. Define command/query DTOs
2. Implement handlers
3. Register with command/query bus
4. Add event handlers if needed

### Adding New Bounded Contexts
1. Create new package under `application/`
2. Define context-specific commands and queries
3. Implement handlers
4. Add to application service orchestration

---

This application layer provides a clean, testable, and maintainable implementation of business use cases while maintaining proper separation between simple and complex operations.
