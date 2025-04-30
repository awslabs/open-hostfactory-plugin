from typing import Dict, Any, Optional
import pytest
from unittest.mock import Mock
from src.api.request_machines import RequestMachines
from src.domain.request.request_aggregate import Request
from src.domain.request.value_objects import RequestStatus

@pytest.fixture
def mock_request_service():
    return Mock()

@pytest.fixture
def sample_request_data():
    return {
        "template": {
            "templateId": "test-template",
            "machineCount": 2
        }
    }

def test_request_machines_success(mock_request_service, sample_request_data):
    # Arrange
    mock_request_service.create_request.return_value.request_id = "req-12345"
    endpoint = RequestMachines(mock_request_service)

    # Act
    result = endpoint.execute(sample_request_data)

    # Assert
    assert result["requestId"] == "req-12345"
    assert result["message"] == "Request machines success."
    mock_request_service.create_request.assert_called_once_with(
        template_id="test-template",
        num_machines=2
    )

def test_request_machines_invalid_input(mock_request_service):
    # Arrange
    endpoint = RequestMachines(mock_request_service)

    # Act
    result = endpoint.execute({})

    # Assert
    assert "error" in result
    assert "Input must include 'template' key" in result["error"]

def test_request_machines_missing_fields(mock_request_service):
    # Arrange
    endpoint = RequestMachines(mock_request_service)
    invalid_data = {"template": {}}

    # Act
    result = endpoint.execute(invalid_data)

    # Assert
    assert "error" in result
    assert "templateId and machineCount are required" in result["error"]

def test_request_machines_service_error(mock_request_service, sample_request_data):
    # Arrange
    mock_request_service.create_request.side_effect = Exception("Service error")
    endpoint = RequestMachines(mock_request_service)

    # Act
    result = endpoint.execute(sample_request_data)

    # Assert
    assert "error" in result
    assert result["message"] == "Failed to request machines"
