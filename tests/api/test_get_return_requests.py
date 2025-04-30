from typing import Dict, Any, Optional
# tests/api/test_get_return_requests.py
import pytest
from src.api.get_return_requests import GetReturnRequests

def test_get_return_requests_success(mock_request_service):
    # Arrange
    mock_request_service.get_return_requests.return_value = [
        {
            "requestId": "ret-12345",
            "status": "running",
            "message": "Return request is running",
            "machines": [
                {
                    "machine": "test-machine-1",
                    "gracePeriod": 300
                }
            ]
        }
    ]
    endpoint = GetReturnRequests(mock_request_service)

    # Act
    result = endpoint.execute()

    # Assert
    assert "requests" in result
    assert len(result["requests"]) == 1
    assert result["requests"][0]["requestId"] == "ret-12345"
    assert result["message"] == "Return requests retrieved successfully."

def test_get_return_requests_empty(mock_request_service):
    # Arrange
    mock_request_service.get_return_requests.return_value = []
    endpoint = GetReturnRequests(mock_request_service)

    # Act
    result = endpoint.execute()

    # Assert
    assert "requests" in result
    assert len(result["requests"]) == 0
    assert result["message"] == "Return requests retrieved successfully."

def test_get_return_requests_with_long_flag(mock_request_service):
    # Arrange
    endpoint = GetReturnRequests(mock_request_service)

    # Act
    result = endpoint.execute(long=True)

    # Assert
    mock_request_service.get_return_requests.assert_called_once()

def test_get_return_requests_service_error(mock_request_service):
    # Arrange
    mock_request_service.get_return_requests.side_effect = Exception("Service error")
    endpoint = GetReturnRequests(mock_request_service)

    # Act
    result = endpoint.execute()

    # Assert
    assert "error" in result
    assert result["message"] == "Failed to retrieve return requests"