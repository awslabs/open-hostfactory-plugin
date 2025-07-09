# System Architecture Diagrams

This document provides visual representations of the Open Host Factory Plugin's architecture using diagrams to illustrate system components, data flow, and interactions.

## Overall System Architecture

```mermaid
graph TB
    subgraph "Interface Layer"
        CLI[CLI Interface]
        API[REST API]
        Scripts[Shell Scripts]
    end
    
    subgraph "Application Layer"
        AppService[Application Service]
        CommandBus[Command Bus]
        QueryBus[Query Bus]
        Handlers[Command/Query Handlers]
    end
    
    subgraph "Domain Layer"
        Templates[Template Aggregate]
        Requests[Request Aggregate]
        Machines[Machine Aggregate]
        DomainServices[Domain Services]
    end
    
    subgraph "Infrastructure Layer"
        DI[DI Container]
        Persistence[Persistence Layer]
        Providers[Provider Strategies]
        Config[Configuration]
        Logging[Logging]
    end
    
    subgraph "External Systems"
        AWS[AWS Services]
        Storage[Storage Backend]
        HostFactory[IBM HostFactory]
    end
    
    CLI --> AppService
    API --> AppService
    Scripts --> CLI
    HostFactory --> Scripts
    
    AppService --> CommandBus
    AppService --> QueryBus
    CommandBus --> Handlers
    QueryBus --> Handlers
    
    Handlers --> Templates
    Handlers --> Requests
    Handlers --> Machines
    Handlers --> DomainServices
    
    Handlers --> Persistence
    Handlers --> Providers
    
    DI --> AppService
    DI --> Handlers
    DI --> Persistence
    DI --> Providers
    
    Providers --> AWS
    Persistence --> Storage
    Config --> DI
    Logging --> DI
```

## Clean Architecture Layers

```mermaid
graph LR
    subgraph "External"
        User[User/HostFactory]
        Cloud[Cloud Provider]
        DB[Database]
    end
    
    subgraph "Interface Layer (Outermost)"
        CLI[CLI Interface]
        REST[REST API]
        Scripts[Shell Scripts]
    end
    
    subgraph "Infrastructure Layer"
        Repos[Repository Implementations]
        CloudAdapters[Cloud Adapters]
        ConfigMgr[Configuration Manager]
        Logger[Logging Implementation]
    end
    
    subgraph "Application Layer"
        UseCases[Use Cases]
        AppServices[Application Services]
        DTOs[DTOs]
        CommandHandlers[Command Handlers]
        QueryHandlers[Query Handlers]
    end
    
    subgraph "Domain Layer (Innermost)"
        Entities[Domain Entities]
        ValueObjects[Value Objects]
        DomainServices[Domain Services]
        RepoInterfaces[Repository Interfaces]
        Ports[Ports/Interfaces]
    end
    
    User --> CLI
    User --> REST
    User --> Scripts
    
    CLI --> UseCases
    REST --> UseCases
    Scripts --> CLI
    
    UseCases --> AppServices
    AppServices --> CommandHandlers
    AppServices --> QueryHandlers
    
    CommandHandlers --> Entities
    QueryHandlers --> Entities
    CommandHandlers --> DomainServices
    QueryHandlers --> DomainServices
    
    CommandHandlers --> RepoInterfaces
    QueryHandlers --> RepoInterfaces
    
    Repos -.-> RepoInterfaces
    CloudAdapters -.-> Ports
    ConfigMgr -.-> Ports
    Logger -.-> Ports
    
    Repos --> DB
    CloudAdapters --> Cloud
    
    style "Domain Layer (Innermost)" fill:#e1f5fe
    style "Application Layer" fill:#f3e5f5
    style "Infrastructure Layer" fill:#fff3e0
    style "Interface Layer (Outermost)" fill:#e8f5e8
```

## CQRS Pattern Flow

```mermaid
graph TB
    subgraph "Command Side (Write)"
        CreateCmd[Create Request Command]
        UpdateCmd[Update Status Command]
        DeleteCmd[Delete Command]
        
        CmdBus[Command Bus]
        
        CreateHandler[Create Request Handler]
        UpdateHandler[Update Status Handler]
        DeleteHandler[Delete Handler]
        
        WriteRepo[Write Repository]
        EventStore[Event Store]
    end
    
    subgraph "Query Side (Read)"
        GetQuery[Get Templates Query]
        ListQuery[List Requests Query]
        StatusQuery[Status Query]
        
        QueryBus[Query Bus]
        
        GetHandler[Get Templates Handler]
        ListHandler[List Requests Handler]
        StatusHandler[Status Handler]
        
        ReadRepo[Read Repository]
        ReadModel[Read Model]
    end
    
    subgraph "Domain"
        Aggregates[Domain Aggregates]
        Events[Domain Events]
    end
    
    CLI --> CreateCmd
    CLI --> GetQuery
    API --> UpdateCmd
    API --> ListQuery
    
    CreateCmd --> CmdBus
    UpdateCmd --> CmdBus
    DeleteCmd --> CmdBus
    
    GetQuery --> QueryBus
    ListQuery --> QueryBus
    StatusQuery --> QueryBus
    
    CmdBus --> CreateHandler
    CmdBus --> UpdateHandler
    CmdBus --> DeleteHandler
    
    QueryBus --> GetHandler
    QueryBus --> ListHandler
    QueryBus --> StatusHandler
    
    CreateHandler --> Aggregates
    UpdateHandler --> Aggregates
    DeleteHandler --> Aggregates
    
    GetHandler --> ReadRepo
    ListHandler --> ReadRepo
    StatusHandler --> ReadRepo
    
    CreateHandler --> WriteRepo
    UpdateHandler --> WriteRepo
    DeleteHandler --> WriteRepo
    
    Aggregates --> Events
    Events --> EventStore
    Events --> ReadModel
    
    WriteRepo --> Storage[(Storage)]
    ReadRepo --> ReadModel
    ReadModel --> Storage
```

## Provider Strategy Pattern

```mermaid
graph TB
    subgraph "Strategy Context"
        ProviderContext[Provider Context]
        StrategyFactory[Provider Strategy Factory]
    end
    
    subgraph "Strategy Interface"
        ProviderStrategy[Provider Strategy Interface]
    end
    
    subgraph "Concrete Strategies"
        AWSStrategy[AWS Provider Strategy]
        MockStrategy[Mock Provider Strategy]
        FutureStrategy[Future Provider Strategy]
    end
    
    subgraph "AWS Implementation"
        AWSClient[AWS Client]
        EC2Handler[EC2 Fleet Handler]
        SpotHandler[Spot Fleet Handler]
        ASGHandler[ASG Handler]
        RunInstancesHandler[Run Instances Handler]
    end
    
    subgraph "Handler Factory"
        HandlerFactory[AWS Handler Factory]
        HandlerRegistry[Handler Registry]
    end
    
    ProviderContext --> StrategyFactory
    StrategyFactory --> ProviderStrategy
    
    ProviderStrategy <|-- AWSStrategy
    ProviderStrategy <|-- MockStrategy
    ProviderStrategy <|-- FutureStrategy
    
    AWSStrategy --> AWSClient
    AWSStrategy --> HandlerFactory
    
    HandlerFactory --> HandlerRegistry
    HandlerRegistry --> EC2Handler
    HandlerRegistry --> SpotHandler
    HandlerRegistry --> ASGHandler
    HandlerRegistry --> RunInstancesHandler
    
    EC2Handler --> AWSClient
    SpotHandler --> AWSClient
    ASGHandler --> AWSClient
    RunInstancesHandler --> AWSClient
    
    AWSClient --> AWS[AWS Services]
```

## Dependency Injection Flow

```mermaid
graph TB
    subgraph "DI Container"
        Container[DI Container]
        ServiceRegistry[Service Registry]
        LifecycleManager[Lifecycle Manager]
    end
    
    subgraph "Service Registration"
        CoreServices[Core Services Registration]
        ProviderServices[Provider Services Registration]
        RepoServices[Repository Services Registration]
        HandlerServices[Handler Services Registration]
    end
    
    subgraph "Dependency Resolution"
        InterfaceRequest[Interface Request]
        DependencyGraph[Dependency Graph]
        InstanceCreation[Instance Creation]
        DependencyInjection[Dependency Injection]
    end
    
    subgraph "Service Types"
        Singletons[Singleton Services]
        Transients[Transient Services]
        Factories[Factory Services]
    end
    
    subgraph "Injected Services"
        AppService[Application Service]
        Repositories[Repositories]
        Providers[Provider Strategies]
        Handlers[Command/Query Handlers]
    end
    
    CoreServices --> Container
    ProviderServices --> Container
    RepoServices --> Container
    HandlerServices --> Container
    
    Container --> ServiceRegistry
    Container --> LifecycleManager
    
    InterfaceRequest --> Container
    Container --> DependencyGraph
    DependencyGraph --> InstanceCreation
    InstanceCreation --> DependencyInjection
    
    ServiceRegistry --> Singletons
    ServiceRegistry --> Transients
    ServiceRegistry --> Factories
    
    DependencyInjection --> AppService
    DependencyInjection --> Repositories
    DependencyInjection --> Providers
    DependencyInjection --> Handlers
    
    AppService --> Repositories
    AppService --> Providers
    AppService --> Handlers
```

## Request Processing Flow

```mermaid
sequenceDiagram
    participant HF as HostFactory
    participant Script as Shell Script
    participant CLI as CLI Interface
    participant App as Application Service
    participant Bus as Command Bus
    participant Handler as Command Handler
    participant Domain as Domain Aggregate
    participant Repo as Repository
    participant Provider as Provider Strategy
    participant AWS as AWS Service
    
    HF->>Script: Execute requestMachines.sh
    Script->>CLI: invoke_provider.sh machines create
    CLI->>App: create_request(template_id, count)
    App->>Bus: execute(CreateRequestCommand)
    Bus->>Handler: handle(command)
    Handler->>Domain: Request.create()
    Handler->>Repo: save(request)
    Handler->>Provider: provision_instances(request)
    Provider->>AWS: run_instances()
    AWS-->>Provider: instance_response
    Provider-->>Handler: machines_list
    Handler-->>Bus: request_id
    Bus-->>App: request_id
    App-->>CLI: request_response
    CLI-->>Script: JSON output
    Script-->>HF: JSON response
```

## Data Flow Architecture

```mermaid
graph LR
    subgraph "Input Sources"
        HFInput[HostFactory Input]
        CLIInput[CLI Input]
        APIInput[API Input]
    end
    
    subgraph "Processing Pipeline"
        Validation[Input Validation]
        Transformation[Data Transformation]
        BusinessLogic[Business Logic]
        Persistence[Data Persistence]
    end
    
    subgraph "External Operations"
        CloudOps[Cloud Operations]
        Monitoring[Monitoring]
        Logging[Logging]
    end
    
    subgraph "Output Destinations"
        HFOutput[HostFactory Output]
        CLIOutput[CLI Output]
        APIOutput[API Output]
        Storage[Storage Systems]
    end
    
    HFInput --> Validation
    CLIInput --> Validation
    APIInput --> Validation
    
    Validation --> Transformation
    Transformation --> BusinessLogic
    BusinessLogic --> Persistence
    
    BusinessLogic --> CloudOps
    BusinessLogic --> Monitoring
    BusinessLogic --> Logging
    
    Persistence --> Storage
    BusinessLogic --> HFOutput
    BusinessLogic --> CLIOutput
    BusinessLogic --> APIOutput
    
    CloudOps --> AWS[AWS Services]
    Monitoring --> Metrics[Metrics Store]
    Logging --> Logs[Log Store]
```

## Component Interaction Matrix

```mermaid
graph TB
    subgraph "High-Level Components"
        Interface[Interface Components]
        Application[Application Components]
        Domain[Domain Components]
        Infrastructure[Infrastructure Components]
    end
    
    subgraph "Interface Details"
        CLI[CLI]
        REST[REST API]
        Scripts[Shell Scripts]
    end
    
    subgraph "Application Details"
        AppSvc[Application Service]
        CmdBus[Command Bus]
        QryBus[Query Bus]
        Handlers[Handlers]
    end
    
    subgraph "Domain Details"
        Entities[Entities]
        ValueObjs[Value Objects]
        DomainSvcs[Domain Services]
        RepoIntf[Repository Interfaces]
    end
    
    subgraph "Infrastructure Details"
        RepoImpl[Repository Implementations]
        ProviderImpl[Provider Implementations]
        ConfigImpl[Configuration Implementation]
        LogImpl[Logging Implementation]
    end
    
    Interface --> Application
    Application --> Domain
    Infrastructure --> Domain
    Infrastructure --> Application
    
    CLI --> AppSvc
    REST --> AppSvc
    Scripts --> CLI
    
    AppSvc --> CmdBus
    AppSvc --> QryBus
    CmdBus --> Handlers
    QryBus --> Handlers
    
    Handlers --> Entities
    Handlers --> DomainSvcs
    Handlers --> RepoIntf
    
    RepoImpl -.-> RepoIntf
    ProviderImpl --> Entities
    ConfigImpl --> AppSvc
    LogImpl --> Handlers
```

These diagrams provide visual representations of the system architecture, making it easier to understand the relationships between components, data flow, and architectural patterns implemented in the Open Host Factory Plugin.
