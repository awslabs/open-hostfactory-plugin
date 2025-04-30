import pytest
from unittest.mock import Mock
from src.api.get_available_templates import GetAvailableTemplates
from src.domain.template.template_aggregate import Template

@pytest.fixture
def mock_template_service():
    return Mock()

@pytest.fixture
def sample_template_data():
    return {
        "templateId": "test-template",
        "awsHandler": "EC2Fleet",
        "maxNumber": 10,
        "attributes": {
            "type": ["String", "X86_64"],
            "ncores": ["Numeric", "2"],
            "ncpus": ["Numeric", "1"],
            "nram": ["Numeric", "4096"]
        },
        "imageId": "ami-12345678",
        "subnetId": "subnet-12345",
        "vmType": "t2.micro",
        "securityGroupIds": ["sg-12345"]
    }

def test_get_available_templates_success(mock_template_service, sample_template_data):
    # Arrange
    mock_template_service.get_available_templates.return_value = {
        "templates": [sample_template_data],
        "message": "Get available templates success."
    }
    endpoint = GetAvailableTemplates(mock_template_service)

    # Act
    result = endpoint.execute()

    # Assert
    assert "templates" in result
    assert len(result["templates"]) == 1
    assert result["templates"][0]["templateId"] == "test-template"
    assert result["message"] == "Get available templates success."
    mock_template_service.get_available_templates.assert_called_once()

def test_get_available_templates_empty(mock_template_service):
    # Arrange
    mock_template_service.get_available_templates.return_value = {
        "templates": [],
        "message": "Get available templates success."
    }
    endpoint = GetAvailableTemplates(mock_template_service)

    # Act
    result = endpoint.execute()

    # Assert
    assert "templates" in result
    assert len(result["templates"]) == 0
    assert result["message"] == "Get available templates success."

def test_get_available_templates_error(mock_template_service):
    # Arrange
    mock_template_service.get_available_templates.side_effect = Exception("Test error")
    endpoint = GetAvailableTemplates(mock_template_service)

    # Act
    result = endpoint.execute()

    # Assert
    assert "error" in result
    assert result["message"] == "Failed to retrieve available templates"

def test_get_available_templates_with_long_flag(mock_template_service, sample_template_data):
    # Arrange
    mock_template_service.get_available_templates.return_value = {
        "templates": [sample_template_data],
        "message": "Get available templates success."
    }
    endpoint = GetAvailableTemplates(mock_template_service)

    # Act
    result = endpoint.execute(long=True)

    # Assert
    assert "templates" in result
    assert len(result["templates"]) == 1
    template_result = result["templates"][0]
    assert "imageId" in template_result
    assert "subnetId" in template_result
    assert "vmType" in template_result
