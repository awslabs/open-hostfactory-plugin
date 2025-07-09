"""Domain events package - Complete event system with proper domain separation."""

# Base classes and protocols
from .base_events import (
    DomainEvent, InfrastructureEvent, EventPublisher,
    TimedEvent, ErrorEvent, OperationEvent, PerformanceEvent, StatusChangeEvent
)

# Domain events (Request, Machine, Template)
from .domain_events import (
    # Request Events
    RequestEvent, RequestCreatedEvent, RequestStatusChangedEvent, 
    RequestCompletedEvent, RequestFailedEvent, RequestTimeoutEvent,
    # Machine Events
    MachineEvent, MachineCreatedEvent, MachineStatusChangedEvent,
    MachineProvisionedEvent, MachineTerminatedEvent, MachineHealthCheckEvent,
    # Template Events
    TemplateEvent, TemplateCreatedEvent, TemplateValidatedEvent,
    TemplateUpdatedEvent, TemplateDeletedEvent,
)

# Infrastructure events (Provider resources and operations)
from .infrastructure_events import (
    ResourceEvent, ResourceCreatedEvent, ResourceUpdatedEvent,
    ResourceDeletedEvent, ResourceErrorEvent, OperationStartedEvent,
    OperationCompletedEvent, OperationFailedEvent,
)

# Persistence events (Repository and storage)
from .persistence_events import (
    # Repository operations
    PersistenceEvent, RepositoryOperationStartedEvent, RepositoryOperationCompletedEvent,
    RepositoryOperationFailedEvent, SlowQueryDetectedEvent, TransactionStartedEvent,
    TransactionCommittedEvent,
    # Storage strategy
    StorageEvent, StorageStrategySelectedEvent, StorageStrategyFailoverEvent,
    ConnectionPoolEvent, StoragePerformanceEvent, DataMigrationEvent,
    StorageHealthCheckEvent,
)

# System events (Configuration, lifecycle, security, performance)
from .system_events import (
    # System base
    SystemEvent,
    # Configuration events
    ConfigurationLoadedEvent, ConfigurationChangedEvent, ConfigurationErrorEvent,
    # Application lifecycle events
    ApplicationStartedEvent, ApplicationShutdownEvent, ApplicationErrorEvent,
    # Security and audit events
    SecurityEvent, AuditTrailEvent, ComplianceEvent,
    # Performance and monitoring events
    PerformanceMetricEvent, HealthCheckEvent,
)

# Provider events (Provider-agnostic)
from .provider_events import (
    ProviderOperationEvent, ProviderRateLimitEvent, ProviderCredentialsEvent,
    ProviderResourceStateChangedEvent, ProviderConfigurationEvent, ProviderHealthCheckEvent
)

# Export all events
__all__ = [
    # Base classes and protocols
    'DomainEvent', 'InfrastructureEvent', 'EventPublisher',
    'TimedEvent', 'ErrorEvent', 'OperationEvent', 'PerformanceEvent', 'StatusChangeEvent',
    
    # Request Events
    'RequestEvent', 'RequestCreatedEvent', 'RequestStatusChangedEvent', 
    'RequestCompletedEvent', 'RequestFailedEvent', 'RequestTimeoutEvent',
    
    # Machine Events
    'MachineEvent', 'MachineCreatedEvent', 'MachineStatusChangedEvent',
    'MachineProvisionedEvent', 'MachineTerminatedEvent', 'MachineHealthCheckEvent',
    
    # Template Events
    'TemplateEvent', 'TemplateCreatedEvent', 'TemplateValidatedEvent',
    'TemplateUpdatedEvent', 'TemplateDeletedEvent',
    
    # Infrastructure Events
    'ResourceEvent', 'ResourceCreatedEvent', 'ResourceUpdatedEvent',
    'ResourceDeletedEvent', 'ResourceErrorEvent', 'OperationStartedEvent',
    'OperationCompletedEvent', 'OperationFailedEvent',
    
    # Repository Operation Events
    'PersistenceEvent', 'RepositoryOperationStartedEvent', 'RepositoryOperationCompletedEvent',
    'RepositoryOperationFailedEvent', 'SlowQueryDetectedEvent', 'TransactionStartedEvent',
    'TransactionCommittedEvent',
    
    # Storage Strategy Events
    'StorageEvent', 'StorageStrategySelectedEvent', 'StorageStrategyFailoverEvent',
    'ConnectionPoolEvent', 'StoragePerformanceEvent', 'DataMigrationEvent',
    'StorageHealthCheckEvent',
    
    # System Events
    'SystemEvent', 'ConfigurationLoadedEvent', 'ConfigurationChangedEvent', 
    'ConfigurationErrorEvent', 'ApplicationStartedEvent', 'ApplicationShutdownEvent', 
    'ApplicationErrorEvent', 'SecurityEvent', 'AuditTrailEvent', 'ComplianceEvent',
    'PerformanceMetricEvent', 'HealthCheckEvent',
    
    # Provider Events (Provider-agnostic)
    'ProviderOperationEvent', 'ProviderRateLimitEvent', 'ProviderCredentialsEvent',
    'ProviderResourceStateChangedEvent', 'ProviderConfigurationEvent', 'ProviderHealthCheckEvent',
]
