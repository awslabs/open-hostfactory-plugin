import pytest
from unittest.mock import Mock, call
from src.application.template.service import TemplateApplicationService
from src.domain.template.exceptions import TemplateNotFoundError, TemplateValidationError
from src.domain.template.template_aggregate import Template
from src.domain.template.value_objects import TemplateId, AWSHandlerType

@pytest.fixture
def mock_template_repository():
    return Mock()

@pytest.fixture
def template_service(mock_template_repository):
    return TemplateApplicationService(template_repository=mock_template_repository)

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
        "securityGroupIds": ["sg-12345"],
        "instanceTags": {
            "Name": "test-instance",
            "Environment": "testing"
        }
    }

def test_get_available_templates(template_service, mock_template_repository, sample_template_data):
    # Arrange
    template = Template.from_dict(sample_template_data)
    mock_template_repository.find_all.return_value = [template]

    # Act
    result = template_service.get_available_templates()

    # Assert
    assert "templates" in result
    assert len(result["templates"]) == 1
    assert result["templates"][0]["templateId"] == "test-template"
    assert result["message"] == "Get available templates success."
    mock_template_repository.find_all.assert_called_once()

def test_get_template_by_id_success(template_service, mock_template_repository, sample_template_data):
    # Arrange
    template = Template.from_dict(sample_template_data)
    mock_template_repository.find_by_id.return_value = template

    # Act
    result = template_service.get_template("test-template")

    # Assert
    assert result.template_id == "test-template"
    assert result.aws_handler == "EC2Fleet"
    assert result.max_number == 10
    mock_template_repository.find_by_id.assert_called_once()

def test_get_template_by_id_not_found(template_service, mock_template_repository):
    # Arrange
    mock_template_repository.find_by_id.return_value = None

    # Act & Assert
    with pytest.raises(TemplateNotFoundError) as exc:
        template_service.get_template("non-existent")
    assert "non-existent" in str(exc.value)

def test_get_templates_by_handler_type(template_service, mock_template_repository, sample_template_data):
    # Arrange
    template = Template.from_dict(sample_template_data)
    mock_template_repository.find_by_handler_type.return_value = [template]

    # Act
    result = template_service.get_templates_by_handler("EC2Fleet")

    # Assert
    assert len(result) == 1
    assert result[0].aws_handler == "EC2Fleet"
    mock_template_repository.find_by_handler_type.assert_called_once_with("EC2Fleet")

def test_validate_template_success(template_service, mock_template_repository, sample_template_data):
    # Arrange
    template = Template.from_dict(sample_template_data)
    mock_template_repository.find_by_id.return_value = template

    # Act
    result = template_service.validate_template("test-template")

    # Assert
    assert result["valid"] is True
    assert result["templateId"] == "test-template"
    assert result["message"] == "Template configuration is valid"

def test_validate_template_invalid(template_service, mock_template_repository):
    # Arrange
    invalid_template_data = {
        "templateId": "test-template",
        "awsHandler": "EC2Fleet",
        "maxNumber": -1,  # Invalid value
        "attributes": {},
        "imageId": "ami-12345678"
    }
    template = Template.from_dict(invalid_template_data)
    mock_template_repository.find_by_id.return_value = template

    # Act & Assert
    with pytest.raises(TemplateValidationError) as exc:
        template_service.validate_template("test-template")
    assert "maxNumber" in str(exc.value)

def test_format_template_response_short(template_service, sample_template_data):
    # Arrange
    template = Template.from_dict(sample_template_data)

    # Act
    result = template_service.format_template_response(template, long=False)

    # Assert
    assert "templateId" in result
    assert "awsHandler" in result
    assert "maxNumber" in result
    assert "attributes" in result
    assert "imageId" not in result  # Should not include detailed fields
    assert "subnetId" not in result  # Should not include detailed fields

def test_format_template_response_long(template_service, sample_template_data):
    # Arrange
    template = Template.from_dict(sample_template_data)

    # Act
    result = template_service.format_template_response(template, long=True)

    # Assert
    assert "templateId" in result
    assert "awsHandler" in result
    assert "maxNumber" in result
    assert "attributes" in result
    assert "imageId" in result
    assert "subnetId" in result
    assert "vmType" in result
    assert "securityGroupIds" in result
    assert "instanceTags" in result

def test_get_available_templates_empty(template_service, mock_template_repository):
    # Arrange
    mock_template_repository.find_all.return_value = []

    # Act
    result = template_service.get_available_templates()

    # Assert
    assert "templates" in result
    assert len(result["templates"]) == 0
    assert result["message"] == "Get available templates success."

def test_get_templates_by_handler_type_empty(template_service, mock_template_repository):
    # Arrange
    mock_template_repository.find_by_handler_type.return_value = []

    # Act
    result = template_service.get_templates_by_handler("NonExistentHandler")

    # Assert
    assert len(result) == 0

def test_validate_template_not_found(template_service, mock_template_repository):
    # Arrange
    mock_template_repository.find_by_id.return_value = None

    # Act & Assert
    with pytest.raises(TemplateNotFoundError) as exc:
        template_service.validate_template("non-existent")
    assert "non-existent" in str(exc.value)

def test_get_available_templates_with_filters(template_service, mock_template_repository, sample_template_data):
    # Arrange
    template1 = Template.from_dict(sample_template_data)
    template2 = Template.from_dict({**sample_template_data, "templateId": "test-template-2", "awsHandler": "SpotFleet"})
    mock_template_repository.find_all.return_value = [template1, template2]

    # Act
    result = template_service.get_available_templates()

    # Assert
    assert len(result["templates"]) == 2
    handlers = {t["awsHandler"] for t in result["templates"]}
    assert handlers == {"EC2Fleet", "SpotFleet"}

def test_validate_template_with_all_handlers(template_service, mock_template_repository, sample_template_data):
    # Test validation with all supported AWS handlers
    for handler in AWSHandlerType:
        # Arrange
        template_data = {**sample_template_data, "awsHandler": handler.value}
        template = Template.from_dict(template_data)
        mock_template_repository.find_by_id.return_value = template

        # Act
        result = template_service.validate_template("test-template")

        # Assert
        assert result["valid"] is True
        assert result["templateId"] == "test-template"
