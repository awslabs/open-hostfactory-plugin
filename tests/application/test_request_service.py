import pytest
from datetime import datetime
from unittest.mock import Mock, call
from src.application.request.service import RequestApplicationService
from src.domain.request.request_aggregate import Request
from src.domain.request.value_objects import RequestStatus, RequestType, RequestId
from src.domain.template.template_aggregate import Template
from src.domain.machine.machine_aggregate import Machine
from src.domain.machine.value_objects import MachineStatus, MachineId
from src.domain.template.exceptions import TemplateNotFoundError
from src.domain.core.common_types import IPAddress

@pytest.fixture
def mock_template_service():
    return Mock()

@pytest.fixture
def mock_machine_service():
    return Mock()

@pytest.fixture
def mock_request_repository():
    return Mock()

@pytest.fixture
def request_service(mock_template_service, mock_machine_service, mock_request_repository):
    return RequestApplicationService(
        request_repository=mock_request_repository,
        template_service=mock_template_service,
        machine_service=mock_machine_service
    )

@pytest.fixture
def sample_template():
    return Template.from_dict({
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
    })

@pytest.fixture
def sample_machine():
    return Machine(
        machine_id=MachineId("i-123"),
        request_id=RequestId("req-123"),
        name="test-machine",
        status=MachineStatus.RUNNING,
        instance_type="t2.micro",
        private_ip=IPAddress("10.0.0.1"),
        aws_handler="EC2Fleet",
        resource_id="fleet-123"
    )

def test_create_request_success(request_service, mock_template_service, mock_request_repository, sample_template):
    # Arrange
    mock_template_service.get_template.return_value = sample_template
    mock_request_repository.save.return_value = None

    # Act
    result = request_service.create_request("test-template", 2)

    # Assert
    assert result.template_id == "test-template"
    assert result.num_requested == 2
    assert result.status == RequestStatus.PENDING.value
    mock_template_service.get_template.assert_called_once_with("test-template")
    mock_request_repository.save.assert_called_once()

def test_create_request_template_not_found(request_service, mock_template_service):
    # Arrange
    mock_template_service.get_template.side_effect = TemplateNotFoundError("test-template")

    # Act & Assert
    with pytest.raises(TemplateNotFoundError):
        request_service.create_request("test-template", 2)

def test_get_request_status_success(request_service, mock_request_repository):
    # Arrange
    request = Request.create_acquire_request(
        template_id="test-template",
        num_machines=2,
        aws_handler="EC2Fleet"
    )
    mock_request_repository.find_by_id.return_value = request

    # Act
    result = request_service.get_request_status(str(request.request_id))

    # Assert
    assert result.request_id == str(request.request_id)
    assert result.status == request.status.value

def test_create_return_request_success(request_service, mock_machine_service, mock_request_repository, sample_machine):
    # Arrange
    mock_machine_service.get_machine.return_value = sample_machine
    mock_request_repository.save.return_value = None

    # Act
    result = request_service.create_return_request(["i-123"])

    # Assert
    assert result.request_type == "return"
    assert len(result.machines) == 1
    mock_request_repository.save.assert_called_once()

def test_create_return_request_all(request_service, mock_machine_service, mock_request_repository, sample_machine):
    # Arrange
    mock_machine_service.get_active_machines.return_value = [sample_machine]
    mock_request_repository.save.return_value = None

    # Act
    result = request_service.create_return_request_all()

    # Assert
    assert result.request_type == "return"
    assert len(result.machines) == 1
    mock_machine_service.get_active_machines.assert_called_once()
    mock_request_repository.save.assert_called_once()

def test_get_active_requests(request_service, mock_request_repository):
    # Arrange
    requests = [
        Request.create_acquire_request("test-template", 2, "EC2Fleet"),
        Request.create_acquire_request("test-template", 3, "SpotFleet")
    ]
    mock_request_repository.find_active_requests.return_value = requests

    # Act
    result = request_service.get_active_requests()

    # Assert
    assert len(result) == 2
    assert all(r.status == "pending" for r in result)

def test_get_return_requests(request_service, mock_request_repository, sample_machine):
    # Arrange
    requests = [
        Request.create_return_request([sample_machine])
    ]
    mock_request_repository.find_return_requests.return_value = requests

    # Act
    result = request_service.get_return_requests()

    # Assert
    assert len(result) == 1
    assert all(r.request_type == "return" for r in result)

def test_get_request_status_not_found(request_service, mock_request_repository):
    # Arrange
    mock_request_repository.find_by_id.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Request req-nonexistent not found"):
        request_service.get_request_status("req-nonexistent")

def test_get_request_status_with_long_flag(request_service, mock_request_repository):
    # Arrange
    request = Request.create_acquire_request(
        template_id="test-template",
        num_machines=2,
        aws_handler="EC2Fleet"
    )
    mock_request_repository.find_by_id.return_value = request

    # Act
    result = request_service.get_request_status(str(request.request_id), long=True)

    # Assert
    assert result.request_id == str(request.request_id)
    assert result.template_id == "test-template"
    assert result.aws_handler == "EC2Fleet"
    assert result.num_requested == 2

def test_create_return_request_no_machines(request_service, mock_machine_service):
    # Arrange
    mock_machine_service.get_machine.side_effect = ValueError("Machine not found")

    # Act & Assert
    with pytest.raises(ValueError):
        request_service.create_return_request(["i-nonexistent"])

def test_create_return_request_all_no_machines(request_service, mock_machine_service):
    # Arrange
    mock_machine_service.get_active_machines.return_value = []

    # Act
    result = request_service.create_return_request_all()

    # Assert
    assert result.num_requested == 0
    assert len(result.machines) == 0
