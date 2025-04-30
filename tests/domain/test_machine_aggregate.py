import pytest
from datetime import datetime
from src.domain.machine.machine_aggregate import Machine
from src.domain.machine.value_objects import MachineId, MachineStatus, PriceType
from src.domain.request.value_objects import RequestId
from src.domain.core.common_types import IPAddress
from src.domain.machine.exceptions import InvalidMachineStateError

@pytest.fixture
def valid_machine_data():
    return {
        "machine_id": "i-1234567890abcdef0",
        "request_id": "req-1234567890",
        "name": "test-machine.internal",
        "status": MachineStatus.RUNNING,
        "instance_type": "t2.micro",
        "private_ip": "10.0.0.100",
        "public_ip": "54.123.45.67",
        "aws_handler": "EC2Fleet",
        "resource_id": "fleet-1234567890",
        "price_type": PriceType.ON_DEMAND,
        "cloud_host_id": "h-12345",
        "tags": {"Name": "test", "Environment": "dev"}
    }

def test_machine_creation(valid_machine_data):
    # Arrange & Act
    machine = Machine(
        machine_id=MachineId(valid_machine_data["machine_id"]),
        request_id=RequestId(valid_machine_data["request_id"]),
        name=valid_machine_data["name"],
        status=valid_machine_data["status"],
        instance_type=valid_machine_data["instance_type"],
        private_ip=IPAddress(valid_machine_data["private_ip"]),
        aws_handler=valid_machine_data["aws_handler"],
        resource_id=valid_machine_data["resource_id"],
        public_ip=IPAddress(valid_machine_data["public_ip"]),
        price_type=valid_machine_data["price_type"],
        cloud_host_id=valid_machine_data["cloud_host_id"]
    )

    # Assert
    assert str(machine.machine_id) == valid_machine_data["machine_id"]
    assert str(machine.request_id) == valid_machine_data["request_id"]
    assert machine.name == valid_machine_data["name"]
    assert machine.status == MachineStatus.RUNNING
    assert machine.instance_type == valid_machine_data["instance_type"]
    assert str(machine.private_ip) == valid_machine_data["private_ip"]
    assert str(machine.public_ip) == valid_machine_data["public_ip"]
    assert machine.aws_handler == valid_machine_data["aws_handler"]
    assert machine.resource_id == valid_machine_data["resource_id"]
    assert machine.price_type == valid_machine_data["price_type"]
    assert machine.cloud_host_id == valid_machine_data["cloud_host_id"]
    assert machine.is_running is True

def test_machine_status_transition(valid_machine_data):
    # Arrange
    machine = Machine(
        machine_id=MachineId(valid_machine_data["machine_id"]),
        request_id=RequestId(valid_machine_data["request_id"]),
        name=valid_machine_data["name"],
        status=MachineStatus.PENDING,  # Start with PENDING
        instance_type=valid_machine_data["instance_type"],
        private_ip=IPAddress(valid_machine_data["private_ip"]),
        aws_handler=valid_machine_data["aws_handler"],
        resource_id=valid_machine_data["resource_id"]
    )

    # Act & Assert - Valid transitions
    machine.update_status(MachineStatus.RUNNING)
    assert machine.status == MachineStatus.RUNNING
    assert machine.running_time is not None

    machine.update_status(MachineStatus.STOPPING)
    assert machine.status == MachineStatus.STOPPING

    machine.update_status(MachineStatus.STOPPED)
    assert machine.status == MachineStatus.STOPPED
    assert machine.stopped_time is not None

def test_invalid_status_transition(valid_machine_data):
    # Arrange
    machine = Machine(
        machine_id=MachineId(valid_machine_data["machine_id"]),
        request_id=RequestId(valid_machine_data["request_id"]),
        name=valid_machine_data["name"],
        status=MachineStatus.RUNNING,
        instance_type=valid_machine_data["instance_type"],
        private_ip=IPAddress(valid_machine_data["private_ip"]),
        aws_handler=valid_machine_data["aws_handler"],
        resource_id=valid_machine_data["resource_id"]
    )

    # Act & Assert - Invalid transition
    with pytest.raises(InvalidMachineStateError):
        machine.update_status(MachineStatus.PENDING)

def test_machine_return(valid_machine_data):
    # Arrange
    machine = Machine(
        machine_id=MachineId(valid_machine_data["machine_id"]),
        request_id=RequestId(valid_machine_data["request_id"]),
        name=valid_machine_data["name"],
        status=MachineStatus.RUNNING,
        instance_type=valid_machine_data["instance_type"],
        private_ip=IPAddress(valid_machine_data["private_ip"]),
        aws_handler=valid_machine_data["aws_handler"],
        resource_id=valid_machine_data["resource_id"]
    )

    # Act
    return_id = "ret-test"
    machine.mark_as_returned(return_id)

    # Assert
    assert machine.status == MachineStatus.RETURNED
    assert machine.return_id == return_id
    assert machine.returned_time is not None
    assert machine.is_returned is True

def test_machine_status_properties(valid_machine_data):
    # Arrange
    machine = Machine(
        machine_id=MachineId(valid_machine_data["machine_id"]),
        request_id=RequestId(valid_machine_data["request_id"]),
        name=valid_machine_data["name"],
        status=MachineStatus.RUNNING,
        instance_type=valid_machine_data["instance_type"],
        private_ip=IPAddress(valid_machine_data["private_ip"]),
        aws_handler=valid_machine_data["aws_handler"],
        resource_id=valid_machine_data["resource_id"]
    )

    # Assert - Running
    assert machine.is_running is True
    assert machine.is_failed is False
    assert machine.is_returned is False

    # Update to failed state
    machine.update_status(MachineStatus.TERMINATED)
    assert machine.is_running is False
    assert machine.is_failed is True
    assert machine.is_returned is False

def test_machine_events(valid_machine_data):
    # Arrange
    machine = Machine(
        machine_id=MachineId(valid_machine_data["machine_id"]),
        request_id=RequestId(valid_machine_data["request_id"]),
        name=valid_machine_data["name"],
        status=MachineStatus.PENDING,
        instance_type=valid_machine_data["instance_type"],
        private_ip=IPAddress(valid_machine_data["private_ip"]),
        aws_handler=valid_machine_data["aws_handler"],
        resource_id=valid_machine_data["resource_id"]
    )

    # Act
    machine.update_status(MachineStatus.RUNNING, "Machine is now running")

    # Assert
    events = machine.events
    assert len(events) == 1
    assert events[0].old_state == "pending"
    assert events[0].new_state == "running"
    assert events[0].resource_id == valid_machine_data["machine_id"]
    assert events[0].resource_type == "Machine"

def test_machine_to_dict(valid_machine_data):
    # Arrange
    machine = Machine(
        machine_id=MachineId(valid_machine_data["machine_id"]),
        request_id=RequestId(valid_machine_data["request_id"]),
        name=valid_machine_data["name"],
        status=valid_machine_data["status"],
        instance_type=valid_machine_data["instance_type"],
        private_ip=IPAddress(valid_machine_data["private_ip"]),
        aws_handler=valid_machine_data["aws_handler"],
        resource_id=valid_machine_data["resource_id"],
        public_ip=IPAddress(valid_machine_data["public_ip"]),
        price_type=valid_machine_data["price_type"],
        cloud_host_id=valid_machine_data["cloud_host_id"]
    )

    # Act
    result = machine.to_dict()

    # Assert
    assert result["machineId"] == valid_machine_data["machine_id"]
    assert result["requestId"] == valid_machine_data["request_id"]
    assert result["name"] == valid_machine_data["name"]
    assert result["status"] == "running"
    assert result["instanceType"] == valid_machine_data["instance_type"]
    assert result["privateIpAddress"] == valid_machine_data["private_ip"]
    assert result["publicIpAddress"] == valid_machine_data["public_ip"]
    assert result["awsHandler"] == valid_machine_data["aws_handler"]
    assert result["resourceId"] == valid_machine_data["resource_id"]
    assert result["priceType"] == "on-demand"
    assert result["cloudHostId"] == valid_machine_data["cloud_host_id"]

def test_machine_from_dict(valid_machine_data):
    # Arrange
    machine_dict = {
        "machineId": valid_machine_data["machine_id"],
        "requestId": valid_machine_data["request_id"],
        "name": valid_machine_data["name"],
        "status": "running",
        "instanceType": valid_machine_data["instance_type"],
        "privateIpAddress": valid_machine_data["private_ip"],
        "publicIpAddress": valid_machine_data["public_ip"],
        "awsHandler": valid_machine_data["aws_handler"],
        "resourceId": valid_machine_data["resource_id"],
        "priceType": "on-demand",
        "cloudHostId": valid_machine_data["cloud_host_id"],
        "launchTime": datetime.utcnow().isoformat()
    }

    # Act
    machine = Machine.from_dict(machine_dict)

    # Assert
    assert str(machine.machine_id) == valid_machine_data["machine_id"]
    assert str(machine.request_id) == valid_machine_data["request_id"]
    assert machine.name == valid_machine_data["name"]
    assert machine.status == MachineStatus.RUNNING
    assert machine.instance_type == valid_machine_data["instance_type"]
    assert str(machine.private_ip) == valid_machine_data["private_ip"]
    assert str(machine.public_ip) == valid_machine_data["public_ip"]
    assert machine.aws_handler == valid_machine_data["aws_handler"]
    assert machine.resource_id == valid_machine_data["resource_id"]
    assert machine.price_type == PriceType.ON_DEMAND
    assert machine.cloud_host_id == valid_machine_data["cloud_host_id"]
