from typing import Dict, Any, Optional
import pytest
from unittest.mock import Mock
from src.api.request_return_machines import RequestReturnMachines

@pytest.fixture
def mock_request_service():
    return Mock()

@pytest.fixture
def sample_return_data():
    return {
        "machines": [
            {"machineId": "i-12345"},
            {"machineId": "i-67890"}
        ]
    }

def test_request_return_machines_success(mock_request_service, sample_return_data):
    # Arrange
    mock_request_service.create_return_request.return_value.request_id = "ret-12345"
    endpoint = RequestReturnMachines(mock_request_service)

    # Act
    result = endpoint.execute(sample_return_data)

    # Assert
    assert result["requestId"] == "ret-12345"
    assert result["message"] == "Delete VM success."
    mock_request_service.create_return_request.assert_called_once_with(
        ["i-12345", "i-67890"]
    )

def test_request_return_machines_all_flag(mock_request_service):
    # Arrange
    mock_request_service.create_return_request_all.return_value.request_id = "ret-12345"
    endpoint = RequestReturnMachines(mock_request_service)

    # Act
    result = endpoint.execute(None, all_flag=True)

    # Assert
    assert result["requestId"] == "ret-12345"
    assert result["message"] == "Delete VM success."
    mock_request_service.create_return_request_all.assert_called_once()

def test_request_return_machines_invalid_input(mock_request_service):
    # Arrange
    endpoint = RequestReturnMachines(mock_request_service)

    # Act
    result = endpoint.execute({})

    # Assert
    assert "error" in result
    assert "Input must include 'machines' key" in result["error"]

def test_request_return_machines_empty_machines(mock_request_service):
    # Arrange
    input_data = {"machines": []}
    endpoint = RequestReturnMachines(mock_request_service)

    # Act
    result = endpoint.execute(input_data)

    # Assert
    assert result["requestId"] is None
    assert result["message"] == "No machines to return"

def test_request_return_machines_service_error(mock_request_service, sample_return_data):
    # Arrange
    mock_request_service.create_return_request.side_effect = Exception("Service error")
    endpoint = RequestReturnMachines(mock_request_service)

    # Act
    result = endpoint.execute(sample_return_data)

    # Assert
    assert "error" in result
    assert result["message"] == "Failed to create return request"
