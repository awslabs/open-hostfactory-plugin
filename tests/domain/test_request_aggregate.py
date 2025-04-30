import pytest
from datetime import datetime
from src.domain.request.request_aggregate import Request
from src.domain.request.value_objects import RequestId, RequestType, RequestStatus
from src.domain.machine.machine_aggregate import Machine
from src.domain.machine.value_objects import MachineId, MachineStatus, PriceType
from src.domain.template.value_objects import TemplateId
from src.domain.core.common_types import IPAddress, Tags
from src.domain.request.exceptions import InvalidRequestStateError, MachineAllocationError

@pytest.fixture
def valid_machine():
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

@pytest.fixture
def valid_request():
    return Request.create_acquire_request(
        template_id="test-template",
        num_machines=2,
        aws_handler="EC2Fleet"
    )

def test_create_acquire_request():
    # Act
    request = Request.create_acquire_request(
        template_id="test-template",
        num_machines=2,
        aws_handler="EC2Fleet"
    )

    # Assert
    assert request.request_id is not None
    assert request.request_type == RequestType.ACQUIRE
    assert str(request.template_id) == "test-template"
    assert request.num_requested == 2
    assert request.aws_handler == "EC2Fleet"
    assert request.status == RequestStatus.PENDING
    assert len(request.machines) == 0
    assert len(request.events) == 1  # Creation event

def test_create_return_request(valid_machine):
    # Arrange
    machines = [valid_machine]

    # Act
    request = Request.create_return_request(machines)

    # Assert
    assert request.request_id is not None
    assert request.request_type == RequestType.RETURN
    assert request.template_id is None
    assert request.num_requested == 1
    assert request.aws_handler == "return"
    assert len(request.machines) == 1
    assert len(request.events) == 1  # Creation event

def test_update_request_status(valid_request):
    # Act
    valid_request.update_status(RequestStatus.RUNNING, "Request is now running")

    # Assert
    assert valid_request.status == RequestStatus.RUNNING
    assert valid_request.message == "Request is now running"
    assert valid_request.last_status_check is not None
    assert valid_request.first_status_check is not None
    assert len(valid_request.events) == 1  # State change event (creation event was cleared)

def test_invalid_status_transition(valid_request):
    # Act & Assert
    with pytest.raises(InvalidRequestStateError):
        valid_request.update_status(RequestStatus.COMPLETE)

def test_add_machine(valid_request, valid_machine):
    # Act
    valid_request.add_machine(valid_machine)

    # Assert
    assert len(valid_request.machines) == 1
    assert valid_request.machines[0].machine_id == valid_machine.machine_id

def test_add_machine_exceeds_limit(valid_request, valid_machine):
    # Arrange
    request = Request.create_acquire_request(
        template_id="test-template",
        num_machines=1,
        aws_handler="EC2Fleet"
    )
    request.add_machine(valid_machine)

    # Act & Assert
    with pytest.raises(MachineAllocationError):
        request.add_machine(valid_machine)

def test_request_completion_status(valid_request, valid_machine):
    # Arrange
    request = Request.create_acquire_request(
        template_id="test-template",
        num_machines=1,
        aws_handler="EC2Fleet"
    )

    # Act
    request.add_machine(valid_machine)

    # Assert
    assert request.status == RequestStatus.COMPLETE
    assert request.message == "All machines provisioned successfully"

def test_request_completion_with_failed_machines(valid_request, valid_machine):
    # Arrange
    failed_machine = Machine(
        machine_id=MachineId("i-456"),
        request_id=RequestId("req-123"),
        name="failed-machine",
        status=MachineStatus.FAILED,
        instance_type="t2.micro",
        private_ip=IPAddress("10.0.0.2"),
        aws_handler="EC2Fleet",
        resource_id="fleet-123"
    )

    # Act
    valid_request.add_machine(valid_machine)
    valid_request.add_machine(failed_machine)

    # Assert
    assert valid_request.status == RequestStatus.COMPLETE_WITH_ERROR
    assert "failed" in valid_request.message.lower()

def test_request_serialization(valid_request):
    # Act
    result = valid_request.to_dict()

    # Assert
    assert result["requestId"] == str(valid_request.request_id)
    assert result["requestType"] == RequestType.ACQUIRE.value
    assert result["templateId"] == str(valid_request.template_id)
    assert result["numRequested"] == 2
    assert result["awsHandler"] == "EC2Fleet"
    assert result["status"] == RequestStatus.PENDING.value
    assert "createdAt" in result
    assert "machines" in result

def test_request_from_dict():
    # Arrange
    request_dict = {
        "requestId": "req-123",
        "requestType": "acquire",
        "templateId": "test-template",
        "numRequested": 2,
        "awsHandler": "EC2Fleet",
        "status": "pending",
        "message": "",
        "machines": [],
        "createdAt": datetime.utcnow().isoformat(),
        "tags": {}
    }

    # Act
    request = Request.from_dict(request_dict)

    # Assert
    assert str(request.request_id) == "req-123"
    assert request.request_type == RequestType.ACQUIRE
    assert str(request.template_id) == "test-template"
    assert request.num_requested == 2
    assert request.aws_handler == "EC2Fleet"
    assert request.status == RequestStatus.PENDING

def test_request_events(valid_request):
    # Act
    valid_request.update_status(RequestStatus.RUNNING, "Running now")
    events = valid_request.events

    # Assert
    assert len(events) == 1
    assert events[0].old_state == "pending"
    assert events[0].new_state == "running"
    assert events[0].resource_type == "Request"

def test_request_tags():
    # Arrange
    tags = {"Environment": "test", "Project": "demo"}
    
    # Act
    request = Request.create_acquire_request(
        template_id="test-template",
        num_machines=1,
        aws_handler="EC2Fleet",
        tags=Tags(tags)
    )

    # Assert
    assert request.tags.items == tags

def test_request_launch_template_info(valid_request):
    # Act
    valid_request.set_launch_template_info("lt-123", "1")

    # Assert
    assert valid_request.launch_template_id == "lt-123"
    assert valid_request.launch_template_version == "1"

def test_request_clear_events(valid_request):
    # Arrange
    valid_request.update_status(RequestStatus.RUNNING)
    assert len(valid_request.events) > 0

    # Act
    valid_request.clear_events()

    # Assert
    assert len(valid_request.events) == 0
