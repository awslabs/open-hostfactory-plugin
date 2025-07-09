# System Architecture Overview

This document provides a high-level overview of the Open Host Factory Plugin's system architecture, focusing on the overall structure, key components, and architectural decisions.

> **Related Documentation:**
> - [Developer Guide: Architecture](../developer_guide/architecture.md) - Development-focused architectural guidance
> - [Architecture: Clean Architecture](./clean_architecture.md) - Detailed Clean Architecture implementation

## Architecture Principles

The plugin implements Clean Architecture principles with clear separation of concerns across four distinct layers:

1. **Domain Layer**: Core business logic and entities
2. **Application Layer**: Use cases and application services
3. **Infrastructure Layer**: External integrations and technical concerns
4. **Interface Layer**: External interfaces (CLI, REST API)

## Layer Structure

### Domain Layer (`src/domain/`)

The domain layer contains the core business logic and is independent of external concerns.

#### Core Aggregates
- **Template** (`src/domain/template/aggregate.py`): Represents VM template configurations
- **Machine** (`src/domain/machine/aggregate.py`): Represents provisioned compute instances
- **Request** (`src/domain/request/aggregate.py`): Represents provisioning requests

#### Value Objects
- **Machine Status** (`src/domain/machine/machine_status.py`): Machine state representations
- **Request Types** (`src/domain/request/value_objects.py`): Request classification and metadata
- **Template Configuration** (`src/domain/template/value_objects.py`): Template-specific value objects

#### Domain Services
- **AMI Resolver** (`src/domain/template/ami_resolver.py`): AMI resolution logic
- **Machine Metadata** (`src/domain/machine/machine_metadata.py`): Machine metadata handling

#### Repositories (Interfaces)
- **Template Repository** (`src/domain/template/repository.py`): Template data access interface
- **Machine Repository** (`src/domain/machine/repository.py`): Machine data access interface
- **Request Repository** (`src/domain/request/repository.py`): Request data access interface

### Application Layer (`src/application/`)

The application layer orchestrates domain objects and implements use cases.

#### Application Service
- **ApplicationService** (`src/application/service.py`): Main application orchestrator implementing CQRS pattern

#### Command Query Responsibility Segregation (CQRS)
- **Commands** (`src/application/*/commands.py`): State-changing operations
- **Queries** (`src/application/dto/queries.py`): State-retrieving operations
- **Command Handlers** (`src/application/commands/`): Process commands
- **Query Handlers** (`src/application/queries/`): Process queries

#### Data Transfer Objects (DTOs)
- **Base DTOs** (`src/application/dto/base.py`): Common DTO patterns
- **Command DTOs** (`src/application/dto/commands.py`): Command data structures
- **Query DTOs** (`src/application/dto/queries.py`): Query data structures
- **Response DTOs** (`src/application/dto/responses.py`): Response data structures

#### Domain-Specific Services
- **Template Services** (`src/application/template/`): Template-related use cases
- **Machine Services** (`src/application/machine/`): Machine-related use cases
- **Provider Services** (`src/application/provider/`): Provider-related use cases

### Infrastructure Layer (`src/infrastructure/`)

The infrastructure layer handles external concerns and technical implementation details.

#### Dependency Injection
- **DI Container** (`src/infrastructure/di/container.py`): Comprehensive dependency injection system
- **Service Registration** (`src/infrastructure/di/`): Service and component registration
- **Bus Registration** (`src/infrastructure/di/buses.py`): CQRS bus configuration

#### External Integrations
- **AWS Provider** (`src/providers/aws/`): AWS cloud provider implementation
- **Storage Adapters** (`src/infrastructure/persistence/`): Data persistence implementations
- **External APIs** (`src/infrastructure/external/`): Third-party service integrations

#### Technical Infrastructure
- **Logging** (`src/infrastructure/logging/`): Logging infrastructure
- **Configuration** (`src/infrastructure/config/`): Configuration management
- **Error Handling** (`src/infrastructure/error/`): Error handling and exceptions

### Interface Layer (`src/interface/`, `src/api/`, `src/cli/`)

The interface layer provides external access points to the system.

#### Command Line Interface
- **CLI Main** (`src/cli/main.py`): Primary CLI interface
- **Command Handlers** (`src/interface/`): CLI command processing
- **Formatters** (`src/cli/formatters.py`): Output formatting
- **Field Mapping** (`src/cli/field_mapping.py`): Field transformation

#### REST API Interface
- **API Server** (`src/api/server.py`): FastAPI server setup
- **Routers** (`src/api/routers/`): API endpoint definitions
- **Models** (`src/api/models/`): API data models
- **Middleware** (`src/api/middleware/`): Request/response processing

## Component Interactions

### Request Flow (CLI)
1. **CLI Interface** receives command
2. **Interface Handlers** process command
3. **Application Service** coordinates execution
4. **Command/Query Handlers** execute business logic
5. **Domain Objects** perform business operations
6. **Infrastructure Services** handle external operations
7. **Response** formatted and returned

### Request Flow (REST API)
1. **API Router** receives HTTP request
2. **API Handler** processes request
3. **Application Service** coordinates execution
4. **Command/Query Handlers** execute business logic
5. **Domain Objects** perform business operations
6. **Infrastructure Services** handle external operations
7. **JSON Response** returned to client

## Design Patterns

### Domain-Driven Design (DDD)
- **Aggregates**: Template, Machine, Request as consistency boundaries
- **Value Objects**: Immutable objects representing domain concepts
- **Domain Services**: Business logic that doesn't belong to entities
- **Repositories**: Data access abstraction

### Command Query Responsibility Segregation (CQRS)
- **Commands**: Operations that change system state
- **Queries**: Operations that retrieve system state
- **Separate Handlers**: Dedicated handlers for commands and queries
- **Event Sourcing**: Domain events for state changes

### Dependency Injection
- **Constructor Injection**: Dependencies provided through constructors
- **Interface Segregation**: Depend on abstractions, not implementations
- **Automatic Resolution**: DI container resolves dependencies automatically
- **Lifecycle Management**: Singleton and transient object lifecycles

### Strategy Pattern
- **Provider Strategies**: Pluggable cloud provider implementations
- **Storage Strategies**: Multiple data persistence options
- **Authentication Strategies**: Various authentication mechanisms

## Configuration-Driven Architecture

The system uses configuration to drive behavior:

### Provider Selection
```json
{
  "provider": {
    "active_provider": "aws-default",
    "selection_policy": "FIRST_AVAILABLE",
    "providers": [
      {
        "name": "aws-default",
        "type": "aws",
        "enabled": true,
        "config": {
          "region": "us-east-1",
          "profile": "default"
        }
      }
    ]
  }
}
```

### Strategy Configuration
```json
{
  "storage": {
    "strategy": "json",
    "json_strategy": {
      "storage_type": "single_file",
      "base_path": "data"
    }
  }
}
```

## Scalability and Performance

### CQRS Benefits
- **Read/Write Separation**: Optimized read and write operations
- **Independent Scaling**: Scale read and write sides independently
- **Performance Optimization**: Specialized handlers for different operations

### Dependency Injection Benefits
- **Loose Coupling**: Components depend on abstractions
- **Testability**: Easy mocking and testing
- **Flexibility**: Runtime behavior modification

### Strategy Pattern Benefits
- **Extensibility**: Easy addition of new providers
- **Runtime Selection**: Dynamic provider selection
- **Configuration-Driven**: Behavior controlled through configuration

## Error Handling and Resilience

### Domain-Level Error Handling
- **Domain Exceptions**: Business rule violations
- **Validation Errors**: Input validation failures
- **State Consistency**: Aggregate consistency enforcement

### Infrastructure-Level Error Handling
- **Retry Mechanisms**: Automatic retry for transient failures
- **Circuit Breakers**: Prevent cascading failures
- **Graceful Degradation**: Fallback mechanisms

### Interface-Level Error Handling
- **Structured Responses**: Consistent error response formats
- **HTTP Status Codes**: Appropriate status code usage
- **Error Logging**: Comprehensive error logging

## Security Considerations

### Authentication
- **Multiple Strategies**: JWT, AWS IAM, Cognito support
- **Token Validation**: Secure token validation
- **Role-Based Access**: Permission-based access control

### Authorization
- **Resource-Level**: Fine-grained resource access control
- **Operation-Level**: Specific operation permissions
- **Context-Aware**: Request context consideration

### Data Protection
- **Input Validation**: Comprehensive input validation
- **Output Sanitization**: Safe output generation
- **Secure Configuration**: Secure configuration management

## Monitoring and Observability

### Logging
- **Structured Logging**: JSON-formatted log entries
- **Correlation IDs**: Request tracing across components
- **Log Levels**: Appropriate log level usage

### Metrics
- **Performance Metrics**: Response time and throughput
- **Business Metrics**: Request success rates
- **System Metrics**: Resource utilization

### Health Checks
- **Component Health**: Individual component status
- **Dependency Health**: External dependency status
- **Overall Health**: System-wide health status

This architecture provides a solid foundation for maintainable, scalable, and testable cloud resource management functionality while maintaining clear separation of concerns and adherence to established software engineering principles.
