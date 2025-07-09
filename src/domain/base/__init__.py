"""Base domain layer - shared kernel for all bounded contexts."""

from .entity import Entity, AggregateRoot
from .value_objects import (
    ValueObject, ResourceId, InstanceId, IPAddress, InstanceType, Tags, 
    ARN, PriceType, AllocationStrategy
)
from .events import (
    DomainEvent, EventPublisher, InfrastructureEvent,
    # Request Events
    RequestEvent, RequestCreatedEvent, RequestStatusChangedEvent, 
    RequestCompletedEvent, RequestFailedEvent, RequestTimeoutEvent,
    # Machine Events
    MachineEvent, MachineCreatedEvent, MachineStatusChangedEvent,
    MachineProvisionedEvent, MachineTerminatedEvent, MachineHealthCheckEvent,
    # Template Events
    TemplateEvent, TemplateCreatedEvent, TemplateValidatedEvent,
    TemplateUpdatedEvent, TemplateDeletedEvent,
    # Infrastructure Events
    ResourceEvent, ResourceCreatedEvent, ResourceUpdatedEvent,
    ResourceDeletedEvent, ResourceErrorEvent, OperationStartedEvent,
    OperationCompletedEvent, OperationFailedEvent
)
from .exceptions import (
    DomainException, ValidationError, BusinessRuleViolationError,
    EntityNotFoundError, ConcurrencyError, InvariantViolationError,
    InfrastructureError, ConfigurationError
)
from .domain_interfaces import (
    RepositoryProtocol, Repository, AggregateRepository, UnitOfWork,
    UnitOfWorkFactory
)

__all__ = [
    # Entities
    'Entity', 'AggregateRoot',
    
    # Value Objects
    'ValueObject', 'ResourceId', 'InstanceId', 'IPAddress', 'InstanceType', 'Tags',
    'ARN', 'PriceType', 'AllocationStrategy',
    
    # Events
    'DomainEvent', 'EventPublisher', 'InfrastructureEvent',
    
    # Repository
    'Repository', 'AggregateRepository', 'UnitOfWork',
    
    # Exceptions
    'DomainException', 'ValidationError', 'BusinessRuleViolationError',
    'EntityNotFoundError', 'ConcurrencyError', 'InvariantViolationError',
    'InfrastructureError', 'ConfigurationError',
    
    # Domain Interfaces (clean)
    'RepositoryProtocol', 'IRepository', 'IUnitOfWork'
]
