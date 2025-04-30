import pytest
from datetime import datetime
from unittest.mock import Mock, call
from src.application.machine.service import MachineApplicationService
from src.domain.machine.machine_aggregate import Machine
from src.domain.machine.value_objects import MachineId, MachineStatus, PriceType
from src.domain.request.value_objects import RequestId
from src.domain.core.common_types import IPAddress

@pytest.fixture
def mock_machine_repository():
    return Mock()

@pytest.fixture
def machine_service(mock_machine_repository):
    return MachineApplicationService(machine_repository=mock_machine_repository)

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
        resource_id="fleet-123",
        public_ip=IPAddress("54.123.45.67"),
        price_type=PriceType.ON_DEMAND
    )

def test_get_machine_success(machine_service, mock_machine_repository, sample_machine):
    # Arrange
    mock_machine_repository.find_by_id.return_value = sample_machine

    # Act
    result = machine_service.get_machine("i-123")

    # Assert
    assert result.machine_id == str(sample_machine.machine_id)
    assert result.status == sample_machine.status.value
    mock_machine_repository.find_by_id.assert_called_once_with(MachineId("i-123"))

def test_get_machine_not_found(machine_service, mock_machine_repository):
    # Arrange
    mock_machine_repository.find_by_id.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Machine i-nonexistent not found"):
        machine_service.get_machine("i-nonexistent")

def test_get_machines_by_request(machine_service, mock_machine_repository, sample_machine):
    # Arrange
    mock_machine_repository.find_by_request_id.return_value = [sample_machine]

    # Act
    result = machine_service.get_machines_by_request("req-123")

    # Assert
    assert len(result) == 1
    assert result[0].machine_id == str(sample_machine.machine_id)
    mock_machine_repository.find_by_request_id.assert_called_once_with("req-123")

def test_get_active_machines(machine_service, mock_machine_repository, sample_machine):
    # Arrange
    mock_machine_repository.find_by_status.return_value = [sample_machine]

    # Act
    result = machine_service.get_active_machines()

    # Assert
    assert len(result) == 1
    assert result[0].machine_id == str(sample_machine.machine_id)
    mock_machine_repository.find_by_status.assert_called_once_with(MachineStatus.RUNNING)

def test_update_machine_status(machine_service, mock_machine_repository, sample_machine):
    # Arrange
    mock_machine_repository.find_by_id.return_value = sample_machine

    # Act
    result = machine_service.update_machine_status(
        "i-123",
        MachineStatus.STOPPED,
        "Machine stopped by user"
    )

    # Assert
    assert result.status == "stopped"
    assert result.message == "Machine stopped by user"
    mock_machine_repository.save.assert_called_once()

def test_update_machine_status_not_found(machine_service, mock_machine_repository):
    # Arrange
    mock_machine_repository.find_by_id.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Machine i-nonexistent not found"):
        machine_service.update_machine_status(
            "i-nonexistent",
            MachineStatus.STOPPED
        )

def test_format_machine_response_short(machine_service, sample_machine):
    # Act
    result = machine_service.format_machine_response(sample_machine, long=False)

    # Assert
    assert result["machineId"] == str(sample_machine.machine_id)
    assert result["status"] == "running"
    assert "instanceType" not in result
    assert "awsHandler" not in result

def test_format_machine_response_long(machine_service, sample_machine):
    # Act
    result = machine_service.format_machine_response(sample_machine, long=True)

    # Assert
    assert result["machineId"] == str(sample_machine.machine_id)
    assert result["status"] == "running"
    assert result["instanceType"] == "t2.micro"
    assert result["awsHandler"] == "EC2Fleet"
    assert result["resourceId"] == "fleet-123"

def test_update_machine_status_with_events(machine_service, mock_machine_repository, sample_machine):
    # Arrange
    mock_machine_repository.find_by_id.return_value = sample_machine

    # Act
    result = machine_service.update_machine_status(
        "i-123",
        MachineStatus.STOPPED,
        "Machine stopped by user"
    )

    # Assert
    assert result.status == "stopped"
    assert len(sample_machine.events) == 1
    event = sample_machine.events[0]
    assert event.old_state == "running"
    assert event.new_state == "stopped"
    assert event.details["reason"] == "Machine stopped by user"

def test_get_machines_by_request_empty(machine_service, mock_machine_repository):
    # Arrange
    mock_machine_repository.find_by_request_id.return_value = []

    # Act
    result = machine_service.get_machines_by_request("req-123")

    # Assert
    assert len(result) == 0
    mock_machine_repository.find_by_request_id.assert_called_once_with("req-123")

def test_get_active_machines_empty(machine_service, mock_machine_repository):
    # Arrange
    mock_machine_repository.find_by_status.return_value = []

    # Act
    result = machine_service.get_active_machines()

    # Assert
    assert len(result) == 0
    mock_machine_repository.find_by_status.assert_called_once_with(MachineStatus.RUNNING)
