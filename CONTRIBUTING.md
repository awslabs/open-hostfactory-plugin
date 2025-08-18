# Contributing to Open Host Factory Plugin

Thank you for your interest in contributing to the Open Host Factory Plugin! This guide will help you get started with development and testing.

## Development Setup

### Prerequisites

- Python 3.9+ (tested on 3.9, 3.10, 3.11, 3.12, 3.13)
- Docker and Docker Compose
- AWS CLI (for AWS provider testing)

### Quick Setup with UV (Recommended)

```bash
# Clone repository
git clone https://github.com/awslabs/open-hostfactory-plugin.git
cd open-hostfactory-plugin

# Fast development setup with uv
make dev-install-uv

# Or manually with uv
uv pip install -e ".[dev]"
```

### Traditional Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install development dependencies
make dev-install-pip
```

## Testing

### Local Testing

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test categories
make test-unit
make test-integration
```

### PR Comment Commands

You can trigger CI/CD actions by commenting on pull requests:

#### Testing Commands
- **`/test`** - Run full CI pipeline (tests, linting, type checking)
- **`/build`** - Run CI pipeline including package build verification
- **`/ci`** - Same as `/test` - run complete CI pipeline  

#### Publishing Commands
- **`/package`** - Build and publish to TestPyPI for testing
  - Creates a dev version: `0.1.0.dev20250818125457+abc1234`
  - Publishes to https://test.pypi.org for installation testing
  - Use: `pip install --index-url https://test.pypi.org/simple/ open-hostfactory-plugin`

#### Future Commands (planned)
- **`/container`** - Build and test container images

### Automated Publishing

The project uses a three-tier publishing strategy:

1. **PR Comments** (`/build-package`) → TestPyPI with dev versions
2. **Merge to main/develop** → TestPyPI with dev versions  
3. **GitHub Releases** → PyPI with release versions

## Code Quality

### Formatting and Linting

```bash
# Format code
make format

# Run linting
make lint

# Type checking
make type-check
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

## Architecture

The plugin follows Clean Architecture principles:

- **Domain Layer**: Core business logic (`src/domain/`)
- **Application Layer**: Use cases and handlers (`src/application/`)
- **Infrastructure Layer**: External integrations (`src/infrastructure/`)
- **Interface Layer**: CLI and API (`src/interface/`, `src/api/`)

### Key Patterns

- **CQRS**: Command Query Responsibility Segregation
- **DDD**: Domain-Driven Design with rich domain models
- **Dependency Injection**: Comprehensive DI container
- **Strategy Pattern**: Pluggable provider implementations

## Pull Request Guidelines

### Before Submitting

1. **Run tests locally**: `make test`
2. **Format code**: `make format`
3. **Update documentation** if needed
4. **Add tests** for new functionality

### PR Description

Please include:
- **What**: Brief description of changes
- **Why**: Motivation and context
- **How**: Implementation approach
- **Testing**: How you tested the changes

### Testing Your PR

Use comment commands to test your changes:

```bash
# Test the full CI pipeline
/test

# Build and test package installation
/package
```

The bot will add a reaction to confirm the command was received.

## Container Development

### Building Containers

```bash
# Build container locally
make container-build

# Test container
make container-test
```

### Container Commands

The container supports multiple entry points:

```bash
# CLI usage
docker run --rm image --version

# API server
docker run -p 8000:8000 image system serve

# Health check
docker run --rm image --health
```

## Documentation

### Building Docs

```bash
# Build documentation
make docs-build

# Serve locally
make docs-serve
```

### Documentation Structure

- `README.md` - Main project documentation
- `docs/` - Detailed documentation
- `CONTRIBUTING.md` - This file
- `docs/deployment/` - Deployment guides

## Release Process

### Version Management

- **Development**: `0.1.0.dev20250818125457+abc1234`
- **Release Candidates**: `0.1.0rc1`
- **Releases**: `0.1.0`

### Creating Releases

1. **Update version** in `.project.yml`
2. **Create GitHub release** with tag `v0.1.0`
3. **Automatic publishing** to PyPI via trusted publishing

## Security

### Trusted Publishing

The project uses PyPI Trusted Publishing (OIDC) instead of API tokens:

- **No secrets to manage** - authentication via GitHub OIDC
- **Automatic attestations** - digital signatures for packages
- **Environment protection** - optional approval workflows

### Reporting Security Issues

Please see our [Security Policy](SECURITY.md) for responsible disclosure procedures.

## Getting Help

- **Documentation**: Comprehensive guides in `docs/`
- **Issues**: GitHub Issues for bug reports and feature requests
- **Discussions**: Community discussions and questions

## Code of Conduct

This project follows the [AWS Open Source Code of Conduct](https://aws.github.io/code-of-conduct).

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
