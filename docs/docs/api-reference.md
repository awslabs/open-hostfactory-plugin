# API Reference - Configuration-Driven Provider Strategy

This document provides comprehensive API reference for the configuration-driven provider strategy system, covering all CLI operations, CQRS commands/queries, and programmatic interfaces.

## Table of Contents

1. [CLI Operations](#cli-operations)
2. [CQRS Commands](#cqrs-commands)
3. [CQRS Queries](#cqrs-queries)
4. [Configuration Schema](#configuration-schema)
5. [Provider Strategy API](#provider-strategy-api)
6. [Error Codes](#error-codes)

## CLI Operations

### Configuration Management Operations

#### getProviderConfig

Retrieve current provider configuration information.

**Usage:**
```bash
python run.py getProviderConfig [--data JSON_DATA]
```

**Parameters:**
- `--data` (optional): JSON string with query options

**Data Schema:**
```json
{
  "include_sensitive": false  // Include sensitive configuration data
}
```

**Response:**
```json
{
  "status": "success",
  "provider_info": {
    "mode": "single|multi|legacy",
    "selection_policy": "ROUND_ROBIN",
    "active_providers": 2,
    "provider_names": ["aws-primary", "aws-backup"],
    "health_check_interval": 30,
    "circuit_breaker_enabled": true
  },
  "config_details": {
    "unified_config_available": true,
    "provider_mode": "multi",
    "total_providers": 2,
    "active_providers": 2,
    "providers": [
      {
        "name": "aws-primary",
        "type": "aws",
        "enabled": true,
        "priority": 1,
        "weight": 70,
        "capabilities": ["compute", "storage"]
      }
    ]
  }
}
```

#### validateProviderConfig

Validate current provider configuration.

**Usage:**
```bash
python run.py validateProviderConfig [--data JSON_DATA]
```

**Parameters:**
- `--data` (optional): JSON string with validation options

**Data Schema:**
```json
{
  "detailed": true  // Include detailed validation information
}
```

**Response:**
```json
{
  "status": "success",
  "validation_result": {
    "valid": true,
    "errors": [],
    "warnings": ["Multi-provider mode configured but less than 2 active providers"],
    "mode": "multi",
    "provider_count": 2,
    "details": {
      "provider_count": 2,
      "active_provider_count": 2,
      "selection_policy": "ROUND_ROBIN",
      "provider_mode": "multi"
    }
  }
}
```

#### reloadProviderConfig

Reload provider configuration from file.

**Usage:**
```bash
python run.py reloadProviderConfig [--config-path PATH] [--data JSON_DATA]
```

**Parameters:**
- `--config-path` (optional): Path to configuration file
- `--data` (optional): JSON string with reload options

**Data Schema:**
```json
{
  "config_path": "/path/to/config.json"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Provider configuration reloaded successfully",
  "config_path": "/path/to/config.json",
  "provider_mode": "multi",
  "active_providers": ["aws-primary", "aws-backup"]
}
```

#### migrateProviderConfig

Migrate provider configuration to unified format.

**Usage:**
```bash
python run.py migrateProviderConfig [--data JSON_DATA]
```

**Parameters:**
- `--data` (optional): JSON string with migration options

**Data Schema:**
```json
{
  "save_to_file": true,      // Save migrated configuration to file
  "backup_original": true    // Create backup of original configuration
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Provider configuration migration completed",
  "migration_summary": {
    "migration_type": "legacy_aws_to_unified",
    "providers_before": 1,
    "providers_after": 1,
    "changes": [
      "Converted legacy AWS configuration to unified format",
      "Added provider strategy configuration",
      "Preserved existing AWS settings"
    ]
  },
  "save_to_file": true,
  "backup_original": true
}
```

### Provider Strategy Operations

#### selectProviderStrategy

Select optimal provider strategy for an operation.

**Usage:**
```bash
python run.py selectProviderStrategy --data JSON_DATA
```

**Data Schema:**
```json
{
  "operation_type": "CREATE_INSTANCES|TERMINATE_INSTANCES|LIST_INSTANCES",
  "required_capabilities": ["compute", "storage"],
  "min_success_rate": 0.95,
  "max_response_time_ms": 5000,
  "require_healthy": true,
  "exclude_strategies": ["aws-backup"],
  "prefer_strategies": ["aws-primary"],
  "context": {
    "region": "us-east-1",
    "instance_type": "t2.micro"
  }
}
```

**Response:**
```json
{
  "selected_strategy": "aws-primary",
  "selection_reason": "Best match for required capabilities and performance criteria",
  "strategy_info": {
    "name": "aws-primary",
    "type": "aws",
    "health_status": "healthy",
    "success_rate": 0.98,
    "avg_response_time_ms": 1200,
    "capabilities": ["compute", "storage", "networking"]
  },
  "alternatives": [
    {
      "name": "aws-backup",
      "reason": "Lower success rate (0.92 < 0.95)"
    }
  ]
}
```

#### executeProviderOperation

Execute an operation using provider strategy selection.

**Usage:**
```bash
python run.py executeProviderOperation --data JSON_DATA
```

**Data Schema:**
```json
{
  "operation_type": "CREATE_INSTANCES",
  "operation_data": {
    "instance_count": 2,
    "instance_type": "t2.micro",
    "image_id": "ami-12345678",
    "subnet_id": "subnet-12345678"
  },
  "selection_criteria": {
    "required_capabilities": ["compute"],
    "prefer_strategies": ["aws-primary"]
  }
}
```

**Response:**
```json
{
  "status": "success",
  "operation_id": "op-12345678-1234-1234-1234-123456789012",
  "selected_strategy": "aws-primary",
  "operation_result": {
    "instances": [
      {
        "instance_id": "i-1234567890abcdef0",
        "state": "pending",
        "instance_type": "t2.micro"
      }
    ]
  },
  "execution_time_ms": 1250
}
```

### Enhanced Template Operations

#### getAvailableTemplates

Get available templates with provider strategy support.

**Usage:**
```bash
python run.py getAvailableTemplates [--provider-api PROVIDER_NAME]
```

**Parameters:**
- `--provider-api` (optional): Filter templates by provider

**Response:**
```json
{
  "templates": [
    {
      "template_id": "basic-template",
      "name": "Basic AWS Template",
      "provider_api": "aws-primary",
      "image_id": "ami-12345678",
      "instance_type": "t2.micro",
      "capabilities": ["compute"],
      "available": true
    }
  ],
  "total_count": 1,
  "provider_info": {
    "mode": "multi",
    "active_providers": ["aws-primary", "aws-backup"]
  }
}
```

#### requestMachines

Request machines with provider strategy selection.

**Usage:**
```bash
python run.py requestMachines --data JSON_DATA
```

**Data Schema:**
```json
{
  "template_id": "basic-template",
  "machine_count": 2,
  "provider_preference": "aws-primary",
  "selection_criteria": {
    "required_capabilities": ["compute"],
    "min_success_rate": 0.95
  },
  "timeout": 300,
  "tags": {
    "Environment": "production",
    "Project": "test"
  }
}
```

**Response:**
```json
{
  "request_id": "req-12345678-1234-1234-1234-123456789012",
  "status": "submitted",
  "selected_provider": "aws-primary",
  "machine_count": 2,
  "estimated_completion_time": "2024-01-01T12:05:00Z"
}
```

## CQRS Commands

### System Commands

#### ReloadProviderConfigCommand

**Class:** `src.application.commands.system.ReloadProviderConfigCommand`

**Fields:**
- `config_path: Optional[str]` - Path to configuration file

**Handler:** `src.application.commands.system_handlers.ReloadProviderConfigHandler`

**Usage:**
```python
from src.application.commands.system import ReloadProviderConfigCommand

command = ReloadProviderConfigCommand(config_path="/path/to/config.json")
result = command_bus.dispatch(command)
```

#### MigrateProviderConfigCommand

**Class:** `src.application.commands.system.MigrateProviderConfigCommand`

**Fields:**
- `save_to_file: bool = False` - Save migrated configuration to file
- `backup_original: bool = True` - Create backup of original configuration

**Handler:** `src.application.commands.system_handlers.MigrateProviderConfigHandler`

**Usage:**
```python
from src.application.commands.system import MigrateProviderConfigCommand

command = MigrateProviderConfigCommand(
    save_to_file=True,
    backup_original=True
)
result = command_bus.dispatch(command)
```

### Provider Strategy Commands

#### SelectProviderStrategyCommand

**Class:** `src.application.provider.commands.SelectProviderStrategyCommand`

**Fields:**
- `operation_type: ProviderOperationType` - Type of operation
- `selection_criteria: SelectionCriteria` - Criteria for provider selection
- `context: Optional[Dict[str, Any]]` - Additional context for selection

**Handler:** `src.application.provider.handlers.SelectProviderStrategyHandler`

#### ExecuteProviderOperationCommand

**Class:** `src.application.provider.commands.ExecuteProviderOperationCommand`

**Fields:**
- `operation_type: ProviderOperationType` - Type of operation to execute
- `operation_data: Dict[str, Any]` - Data for the operation
- `selection_criteria: Optional[SelectionCriteria]` - Provider selection criteria

**Handler:** `src.application.provider.handlers.ExecuteProviderOperationHandler`

## CQRS Queries

### System Queries

#### GetProviderConfigQuery

**Class:** `src.application.queries.system.GetProviderConfigQuery`

**Fields:**
- `include_sensitive: bool = False` - Include sensitive configuration data

**Handler:** `src.application.queries.system_handlers.GetProviderConfigHandler`

**Usage:**
```python
from src.application.queries.system import GetProviderConfigQuery

query = GetProviderConfigQuery(include_sensitive=False)
result = query_bus.dispatch(query)
```

#### ValidateProviderConfigQuery

**Class:** `src.application.queries.system.ValidateProviderConfigQuery`

**Fields:**
- `detailed: bool = True` - Include detailed validation information

**Handler:** `src.application.queries.system_handlers.ValidateProviderConfigHandler`

**Usage:**
```python
from src.application.queries.system import ValidateProviderConfigQuery

query = ValidateProviderConfigQuery(detailed=True)
result = query_bus.dispatch(query)
```

### Provider Strategy Queries

#### GetProviderHealthQuery

**Class:** `src.application.provider.queries.GetProviderHealthQuery`

**Fields:**
- `provider_name: Optional[str]` - Specific provider name (optional)

**Handler:** `src.application.provider.handlers.GetProviderHealthHandler`

#### ListAvailableProvidersQuery

**Class:** `src.application.provider.queries.ListAvailableProvidersQuery`

**Fields:**
- `include_disabled: bool = False` - Include disabled providers
- `filter_capabilities: Optional[List[str]]` - Filter by capabilities

**Handler:** `src.application.provider.handlers.ListAvailableProvidersHandler`

## Configuration Schema

### UnifiedProviderConfig

**Class:** `src.config.schemas.provider_strategy_schema.UnifiedProviderConfig`

**Fields:**
```python
selection_policy: str = "FIRST_AVAILABLE"
active_provider: Optional[str] = None
health_check_interval: int = 30
circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()
providers: List[ProviderInstanceConfig] = []
type: Optional[str] = None  # Legacy compatibility
aws: Optional[Dict[str, Any]] = None  # Legacy compatibility
```

**Methods:**
- `get_mode() -> ProviderMode` - Determine provider mode
- `get_active_providers() -> List[ProviderInstanceConfig]` - Get enabled providers

### ProviderInstanceConfig

**Class:** `src.config.schemas.provider_strategy_schema.ProviderInstanceConfig`

**Fields:**
```python
name: str
type: Literal["aws", "azure", "gcp"]
enabled: bool = True
priority: int = 1
weight: int = 100
capabilities: List[str] = []
config: Dict[str, Any] = {}
```

### CircuitBreakerConfig

**Class:** `src.config.schemas.provider_strategy_schema.CircuitBreakerConfig`

**Fields:**
```python
enabled: bool = False
failure_threshold: int = 5
recovery_timeout: int = 60
half_open_max_calls: int = 3
```

## Provider Strategy API

### ProviderStrategyFactory

**Class:** `src.infrastructure.factories.provider_strategy_factory.ProviderStrategyFactory`

**Methods:**

#### create_provider_context()
Create configured provider context based on unified configuration.

**Returns:** `ProviderContext`

**Raises:**
- `ConfigurationError` - Invalid configuration
- `ProviderCreationError` - Provider creation failed

#### get_provider_info()
Get information about current provider configuration.

**Returns:**
```python
{
    "mode": str,
    "selection_policy": str,
    "active_provider": Optional[str],
    "total_providers": int,
    "active_providers": int,
    "provider_names": List[str],
    "health_check_interval": int,
    "circuit_breaker_enabled": bool
}
```

#### validate_configuration()
Validate current provider configuration.

**Returns:**
```python
{
    "valid": bool,
    "errors": List[str],
    "warnings": List[str],
    "provider_count": int,
    "mode": str
}
```

### ProviderContext

**Class:** `src.providers.base.strategy.ProviderContext`

**Methods:**

#### register_strategy(strategy, name)
Register a provider strategy with the context.

**Parameters:**
- `strategy: ProviderStrategy` - Provider strategy instance
- `name: str` - Strategy name

#### select_strategy(criteria)
Select optimal provider strategy based on criteria.

**Parameters:**
- `criteria: SelectionCriteria` - Selection criteria

**Returns:** `ProviderStrategy`

#### get_available_strategies()
Get list of available provider strategies.

**Returns:** `List[ProviderStrategy]`

### SelectionCriteria

**Class:** `src.providers.base.strategy.SelectionCriteria`

**Fields:**
```python
required_capabilities: List[str] = []
min_success_rate: float = 0.0
max_response_time_ms: float = float('inf')
require_healthy: bool = True
exclude_strategies: List[str] = []
prefer_strategies: List[str] = []
```

## Error Codes

### Configuration Errors

| Code | Error | Description |
|------|-------|-------------|
| `CONFIG_001` | `ConfigurationError` | Invalid configuration format |
| `CONFIG_002` | `ConfigurationError` | Missing required configuration |
| `CONFIG_003` | `ConfigurationError` | Invalid provider configuration |
| `CONFIG_004` | `ConfigurationError` | Configuration validation failed |

### Provider Errors

| Code | Error | Description |
|------|-------|-------------|
| `PROVIDER_001` | `ProviderCreationError` | Failed to create provider |
| `PROVIDER_002` | `ProviderCreationError` | Unsupported provider type |
| `PROVIDER_003` | `ProviderNotAvailableError` | Provider not available |
| `PROVIDER_004` | `ProviderHealthError` | Provider health check failed |

### Strategy Errors

| Code | Error | Description |
|------|-------|-------------|
| `STRATEGY_001` | `StrategySelectionError` | No suitable strategy found |
| `STRATEGY_002` | `StrategyExecutionError` | Strategy execution failed |
| `STRATEGY_003` | `StrategyConfigurationError` | Invalid strategy configuration |

### System Errors

| Code | Error | Description |
|------|-------|-------------|
| `SYSTEM_001` | `InfrastructureError` | Infrastructure component error |
| `SYSTEM_002` | `ApplicationError` | Application layer error |
| `SYSTEM_003` | `DomainError` | Domain logic error |

## Response Formats

### Success Response

```json
{
  "status": "success",
  "data": {},
  "message": "Operation completed successfully",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Error Response

```json
{
  "status": "error",
  "error": "Error message",
  "error_code": "CONFIG_001",
  "details": {
    "field": "provider.type",
    "value": "invalid",
    "expected": "aws|azure|gcp"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Validation Response

```json
{
  "status": "success",
  "validation_result": {
    "valid": false,
    "errors": ["Error message"],
    "warnings": ["Warning message"],
    "details": {}
  }
}
```

This API reference provides comprehensive coverage of all interfaces in the configuration-driven provider strategy system. For usage examples and integration patterns, see the examples directory.
