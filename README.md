# Open Host Factory Plugin

A professional cloud provider integration plugin for IBM Spectrum Symphony Host Factory, enabling dynamic provisioning of compute resources with modern REST API interface and clean architecture implementation.

## Overview

The Open Host Factory Plugin provides seamless integration between IBM Spectrum Symphony Host Factory and cloud providers, implementing enterprise-grade patterns including Domain-Driven Design (DDD), Command Query Responsibility Segregation (CQRS), and Clean Architecture principles.

**Currently Supported Providers:**
- **AWS** - Amazon Web Services (RunInstances, EC2Fleet, SpotFleet, Auto Scaling Groups)

## Key Features

### Core Functionality
- **HostFactory Compatible Output**: Native compatibility with IBM Symphony Host Factory requirements
- **Multi-Provider Architecture**: Extensible provider system supporting multiple cloud platforms
- **REST API Interface**: Modern REST API with OpenAPI/Swagger documentation
- **Configuration-Driven**: Dynamic provider selection and configuration through unified config system

### Advanced Features
- **Clean Architecture**: Domain-driven design with clear separation of concerns
- **CQRS Pattern**: Command Query Responsibility Segregation for scalable operations
- **Dependency Injection**: Comprehensive DI container with automatic dependency resolution
- **Strategy Pattern**: Pluggable provider strategies with runtime selection
- **Resilience Patterns**: Built-in retry mechanisms, circuit breakers, and error handling

### Output Formats and Compatibility
- **Flexible Field Control**: Configurable output fields for different use cases
- **Multiple Output Formats**: JSON, YAML, Table, and List formats
- **Legacy Compatibility**: Support for camelCase field naming conventions
- **Professional Tables**: Rich Unicode table formatting for CLI output

## Quick Start

### Docker Deployment (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd open-hostfactory-plugin

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Start services
docker-compose up -d

# Verify deployment
curl http://localhost:8000/health
```

### Package Installation

```bash
# Install from PyPI
pip install open-hostfactory-plugin

# Verify installation
ohfp --version
ohfp --help
```

## Usage Examples

### Command Line Interface

```bash
# List available templates
ohfp templates list

# Get detailed template information
ohfp templates list --long

# Request machines
ohfp requests create --template-id my-template --count 5

# Check request status
ohfp requests status --request-id req-12345

# List active machines
ohfp machines list

# Return machines
ohfp requests return --request-id req-12345
```

### REST API

```bash
# Get available templates
curl -X GET "http://localhost:8000/api/v1/templates"

# Create machine request
curl -X POST "http://localhost:8000/api/v1/requests" \
  -H "Content-Type: application/json" \
  -d '{"templateId": "my-template", "maxNumber": 5}'

# Check request status
curl -X GET "http://localhost:8000/api/v1/requests/req-12345"
```

## Architecture

The plugin implements Clean Architecture principles with the following layers:

- **Domain Layer**: Core business logic, entities, and domain services
- **Application Layer**: Use cases, command/query handlers, and application services
- **Infrastructure Layer**: External integrations, persistence, and technical concerns
- **Interface Layer**: REST API, CLI, and external interfaces

### Design Patterns

- **Domain-Driven Design (DDD)**: Rich domain models with clear bounded contexts
- **CQRS**: Separate command and query responsibilities for scalability
- **Ports and Adapters**: Hexagonal architecture for testability and flexibility
- **Strategy Pattern**: Pluggable provider implementations
- **Factory Pattern**: Dynamic object creation based on configuration
- **Repository Pattern**: Data access abstraction with multiple storage strategies

## Configuration

### Environment Configuration

```bash
# Provider configuration
PROVIDER_TYPE=aws
AWS_REGION=us-east-1
AWS_PROFILE=default

# API configuration
API_HOST=0.0.0.0
API_PORT=8000

# Storage configuration
STORAGE_TYPE=dynamodb
STORAGE_TABLE_PREFIX=hostfactory
```

### Provider Configuration

```yaml
# config/providers.yml
providers:
  - name: aws-primary
    type: aws
    config:
      region: us-east-1
      profile: default
      handlers:
        default: ec2_fleet
        spot_fleet:
          enabled: true
        auto_scaling_group:
          enabled: true
```

## Development

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- AWS CLI (for AWS provider)

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd open-hostfactory-plugin

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt

# Install in development mode
pip install -e .

# Run tests
pytest

# Run linting
make lint

# Run type checking
make type-check
```

### Testing

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run integration tests
make test-integration

# Run performance tests
make test-performance
```

## Documentation

Comprehensive documentation is available at:

- **Architecture Guide**: Understanding the system design and patterns
- **API Reference**: Complete REST API documentation
- **Configuration Guide**: Detailed configuration options
- **Developer Guide**: Contributing and extending the plugin
- **Deployment Guide**: Production deployment scenarios

## HostFactory Integration

The plugin is designed for seamless integration with IBM Spectrum Symphony Host Factory:

- **API Compatibility**: Full compatibility with HostFactory API requirements
- **Output Format Compliance**: Native support for expected output formats
- **Configuration Integration**: Easy integration with existing HostFactory configurations
- **Monitoring Integration**: Compatible with HostFactory monitoring and logging

## Support and Contributing

### Getting Help

- **Documentation**: Comprehensive guides and API reference
- **Issues**: GitHub Issues for bug reports and feature requests
- **Discussions**: Community discussions and questions

### Contributing

We welcome contributions! Please see our Contributing Guide for details on:

- Code style and standards
- Testing requirements
- Pull request process
- Development workflow

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Security

For security concerns, please see our [Security Policy](SECURITY.md) for responsible disclosure procedures.
