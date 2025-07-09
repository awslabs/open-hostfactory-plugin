"""Single machine repository implementation using storage strategy composition."""
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.domain.machine.repository import MachineRepository as MachineRepositoryInterface
from src.domain.machine.aggregate import Machine
from src.domain.machine.value_objects import MachineId, MachineStatus
from src.domain.base.value_objects import InstanceId
from src.infrastructure.persistence.base.strategy import BaseStorageStrategy
from src.infrastructure.logging.logger import get_logger
from src.infrastructure.error.decorators import handle_infrastructure_exceptions


class MachineSerializer:
    """Handles Machine aggregate serialization/deserialization."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def to_dict(self, machine: Machine) -> Dict[str, Any]:
        """Convert Machine aggregate to dictionary."""
        try:
            return {
                'machine_id': str(machine.machine_id.value),
                'instance_id': str(machine.instance_id.value) if machine.instance_id else None,
                'template_id': machine.template_id,
                'request_id': machine.request_id,
                'status': machine.status.value,
                'instance_type': machine.instance_type.value if machine.instance_type else None,
                'availability_zone': machine.availability_zone,
                'private_ip': str(machine.private_ip.value) if machine.private_ip else None,
                'public_ip': str(machine.public_ip.value) if machine.public_ip else None,
                'launch_time': machine.launch_time.isoformat() if machine.launch_time else None,
                'termination_time': machine.termination_time.isoformat() if machine.termination_time else None,
                'tags': dict(machine.tags.value) if machine.tags else {},
                'metadata': machine.metadata or {},
                'created_at': machine.created_at.isoformat(),
                'updated_at': machine.updated_at.isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to serialize machine {machine.machine_id}: {e}")
            raise
    
    def from_dict(self, data: Dict[str, Any]) -> Machine:
        """Convert dictionary to Machine aggregate."""
        try:
            # Parse datetime fields
            launch_time = datetime.fromisoformat(data['launch_time']) if data.get('launch_time') else None
            termination_time = datetime.fromisoformat(data['termination_time']) if data.get('termination_time') else None
            created_at = datetime.fromisoformat(data['created_at'])
            updated_at = datetime.fromisoformat(data['updated_at'])
            
            # Create machine using factory method
            machine = Machine.create_from_data(
                machine_id=MachineId(data['machine_id']),
                instance_id=InstanceId(data['instance_id']) if data.get('instance_id') else None,
                template_id=data['template_id'],
                request_id=data['request_id'],
                status=MachineStatus(data['status']),
                instance_type=data.get('instance_type'),
                availability_zone=data.get('availability_zone'),
                private_ip=data.get('private_ip'),
                public_ip=data.get('public_ip'),
                launch_time=launch_time,
                termination_time=termination_time,
                tags=data.get('tags', {}),
                metadata=data.get('metadata', {}),
                created_at=created_at,
                updated_at=updated_at
            )
            
            return machine
            
        except Exception as e:
            self.logger.error(f"Failed to deserialize machine data: {e}")
            raise


class MachineRepositoryImpl(MachineRepositoryInterface):
    """Single machine repository implementation using storage strategy composition."""
    
    def __init__(self, storage_strategy: BaseStorageStrategy):
        """Initialize repository with storage strategy."""
        self.storage_strategy = storage_strategy
        self.serializer = MachineSerializer()
        self.logger = get_logger(__name__)
    
    @handle_infrastructure_exceptions(context="machine_repository_save")
    def save(self, machine: Machine) -> List[Any]:
        """Save machine using storage strategy and return extracted events."""
        try:
            # Save the machine
            machine_data = self.serializer.to_dict(machine)
            self.storage_strategy.save(str(machine.machine_id.value), machine_data)
            
            # Extract events from the aggregate
            events = machine.get_domain_events()
            machine.clear_domain_events()
            
            self.logger.debug(f"Saved machine {machine.machine_id} and extracted {len(events)} events")
            return events
            
        except Exception as e:
            self.logger.error(f"Failed to save machine {machine.machine_id}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="machine_repository_get_by_id")
    def get_by_id(self, machine_id: MachineId) -> Optional[Machine]:
        """Get machine by ID using storage strategy."""
        try:
            data = self.storage_strategy.find_by_id(str(machine_id.value))
            if data:
                return self.serializer.from_dict(data)
            return None
        except Exception as e:
            self.logger.error(f"Failed to get machine {machine_id}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="machine_repository_find_by_id")
    def find_by_id(self, machine_id: MachineId) -> Optional[Machine]:
        """Find machine by ID (alias for get_by_id)."""
        return self.get_by_id(machine_id)
    
    @handle_infrastructure_exceptions(context="machine_repository_find_by_instance_id")
    def find_by_instance_id(self, instance_id: InstanceId) -> Optional[Machine]:
        """Find machine by instance ID."""
        try:
            criteria = {"instance_id": str(instance_id.value)}
            data_list = self.storage_strategy.find_by_criteria(criteria)
            if data_list:
                return self.serializer.from_dict(data_list[0])
            return None
        except Exception as e:
            self.logger.error(f"Failed to find machine by instance_id {instance_id}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="machine_repository_find_by_template_id")
    def find_by_template_id(self, template_id: str) -> List[Machine]:
        """Find machines by template ID."""
        try:
            criteria = {"template_id": template_id}
            data_list = self.storage_strategy.find_by_criteria(criteria)
            return [self.serializer.from_dict(data) for data in data_list]
        except Exception as e:
            self.logger.error(f"Failed to find machines by template_id {template_id}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="machine_repository_find_by_status")
    def find_by_status(self, status: MachineStatus) -> List[Machine]:
        """Find machines by status."""
        try:
            criteria = {"status": status.value}
            data_list = self.storage_strategy.find_by_criteria(criteria)
            return [self.serializer.from_dict(data) for data in data_list]
        except Exception as e:
            self.logger.error(f"Failed to find machines by status {status}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="machine_repository_find_by_request_id")
    def find_by_request_id(self, request_id: str) -> List[Machine]:
        """Find machines by request ID."""
        try:
            criteria = {"request_id": request_id}
            data_list = self.storage_strategy.find_by_criteria(criteria)
            return [self.serializer.from_dict(data) for data in data_list]
        except Exception as e:
            self.logger.error(f"Failed to find machines by request_id {request_id}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="machine_repository_find_active_machines")
    def find_active_machines(self) -> List[Machine]:
        """Find all active (non-terminated) machines."""
        try:
            from src.domain.machine.value_objects import MachineStatus
            active_statuses = [MachineStatus.PENDING, MachineStatus.RUNNING, MachineStatus.LAUNCHING]
            all_machines = []
            
            for status in active_statuses:
                machines = self.find_by_status(status)
                all_machines.extend(machines)
            
            return all_machines
        except Exception as e:
            self.logger.error(f"Failed to find active machines: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="machine_repository_find_all")
    def find_all(self) -> List[Machine]:
        """Find all machines."""
        try:
            all_data = self.storage_strategy.find_all()
            return [self.serializer.from_dict(data) for data in all_data.values()]
        except Exception as e:
            self.logger.error(f"Failed to find all machines: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="machine_repository_delete")
    def delete(self, machine_id: MachineId) -> None:
        """Delete machine by ID."""
        try:
            self.storage_strategy.delete(str(machine_id.value))
            self.logger.debug(f"Deleted machine {machine_id}")
        except Exception as e:
            self.logger.error(f"Failed to delete machine {machine_id}: {e}")
            raise
    
    @handle_infrastructure_exceptions(context="machine_repository_exists")
    def exists(self, machine_id: MachineId) -> bool:
        """Check if machine exists."""
        try:
            return self.storage_strategy.exists(str(machine_id.value))
        except Exception as e:
            self.logger.error(f"Failed to check if machine {machine_id} exists: {e}")
            raise
