# Testing Guide

This guide covers testing strategies, frameworks, and best practices for the Open Host Factory Plugin.

## Testing Strategy

The plugin uses a comprehensive testing approach with multiple test levels:

### Unit Tests
- **Location**: `tests/unit/`
- **Framework**: pytest
- **Coverage**: Individual components and functions
- **Mocking**: Extensive use of mocks for external dependencies

### Integration Tests
- **Location**: `tests/integration/`
- **Framework**: pytest
- **Coverage**: Component interactions and workflows
- **Environment**: Test containers and mock services

### End-to-End Tests
- **Location**: `tests/e2e/`
- **Framework**: pytest + requests
- **Coverage**: Full API workflows
- **Environment**: Docker Compose test environment

## Running Tests

### All Tests
```bash
pytest
```

### Unit Tests Only
```bash
pytest tests/unit/
```

### Integration Tests
```bash
pytest tests/integration/
```

### With Coverage
```bash
pytest --cov=src --cov-report=html
```

## Test Configuration

Tests use the configuration in `pytest.ini` and `tests/conftest.py`.

## Related Documentation
- [Development Guide](../development/testing.md) - Detailed testing implementation
- [Developer Guide](../developer_guide/architecture.md) - Architecture for testing
