from typing import Dict, Any, Optional
import pytest
from unittest.mock import Mock
from src.api.get_request_status import GetRequestStatus
from src.domain.request.value_objects import RequestStatus

@pytest.fixture
def mock_request_service():
    return Mock()

@pytest.fixture
def sample_request_response():
    return {
        "requestId": "req-12345",
        "status": "running",
        "message": "Request is running",
        "machines": [
            {
                "machineId": "i-12345",
                "name": "test-machine",
                "status": "running",
                "privateIpAddress": "10.0.0.1"
            }
        ]
    }

def test_get_request_status_single_request(mock_request_service, sample_request_response):
    # Arrange
    request_data = {
        "requests": [{"requestId": "req-12345"}]
    }
    mock_request_service.get_request_status.return_value.to_dict.return_value = sample_request_response
    endpoint = GetRequestStatus(mock_request_service)

    # Act
    result = endpoint.execute(request_data)

    # Assert
    assert "requests" in result
    assert len(result["requests"]) == 1
    assert result["requests"][0]["requestId"] == "req-12345"
    assert result["requests"][0]["status"] == "running"
    mock_request_service.get_request_status.assert_called_once_with("req-12345", False)

def test_get_request_status_all_flag(mock_request_service, sample_request_response):
    # Arrange
    mock_request_service.get_active_requests.return_value = [
        Mock(to_dict=lambda: sample_request_response)
    ]
    endpoint = GetRequestStatus(mock_request_service)

    # Act
    result = endpoint.execute(all_flag=True)

    # Assert
    assert "requests" in result
    assert len(result["requests"]) == 1
    mock_request_service.get_active_requests.assert_called_once()

def test_get_request_status_with_long_flag(mock_request_service, sample_request_response):
    # Arrange
    request_data = {
        "requests": [{"requestId": "req-12345"}]
    }
    mock_request_service.get_request_status.return_value.to_dict.return_value = sample_request_response
    endpoint = GetRequestStatus(mock_request_service)

    # Act
    result = endpoint.execute(request_data, long=True)

    # Assert
    mock_request_service.get_request_status.assert_called_once_with("req-12345", True)

def test_get_request_status_invalid_input(mock_request_service):
    # Arrange
    endpoint = GetRequestStatus(mock_request_service)

    # Act
    result = endpoint.execute({})

    # Assert
    assert "error" in result
    assert "Input must include 'requests' key" in result["error"]

def test_get_request_status_service_error(mock_request_service):
    # Arrange
    request_data = {
        "requests": [{"requestId": "req-12345"}]
    }
    mock_request_service.get_request_status.side_effect = Exception("Service error")
    endpoint = GetRequestStatus(mock_request_service)

    # Act
    result = endpoint.execute(request_data)

    # Assert
    assert "error" in result
    assert result["message"] == "Failed to retrieve request status"
