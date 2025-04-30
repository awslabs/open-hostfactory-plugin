# src/domain/machine/machine_repository.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from src.domain.machine.machine_aggregate import Machine
from src.domain.machine.value_objects import MachineId, MachineStatus
from src.domain.machine.exceptions import MachineNotFoundError
from src.domain.request.value_objects import RequestId

class MachineRepository(ABC):
    """Repository interface for machine persistence."""
    
    @abstractmethod
    def save(self, machine: Machine) -> None:
        """Save a new machine or update an existing one."""
        pass

    @abstractmethod
    def find_by_id(self, machine_id: MachineId) -> Optional[Machine]:
        """Find a machine by its ID."""
        pass

    @abstractmethod
    def find_by_request_id(self, request_id: RequestId) -> List[Machine]:
        """Find all machines associated with a request."""
        pass

    @abstractmethod
    def find_by_status(self, status: MachineStatus) -> List[Machine]:
        """Find all machines with a specific status."""
        pass

    @abstractmethod
    def find_active_machines(self) -> List[Machine]:
        """Find all active (running) machines."""
        pass

    @abstractmethod
    def find_machines_for_return(self) -> List[Machine]:
        """Find machines that are marked for return."""
        pass

    @abstractmethod
    def delete(self, machine_id: MachineId) -> None:
        """Delete a machine."""
        pass

    @abstractmethod
    def exists(self, machine_id: MachineId) -> bool:
        """Check if a machine exists."""
        pass

    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[Machine]:
        """Find machines matching specified criteria."""
        pass

    def cleanup_terminated_machines(self, age_hours: int = 24) -> None:
        """Clean up old terminated machines."""
        pass

class JSONMachineRepository(MachineRepository):
    """JSON file implementation of machine repository."""
    
    def __init__(self, db_handler):
        """Initialize with database handler."""
        self._db = db_handler

    def save(self, machine: Machine) -> None:
        """Save or update a machine."""
        self._db.add_or_update_machine(machine)

    def find_by_id(self, machine_id: MachineId) -> Optional[Machine]:
        """Find a machine by its ID."""
        machine_data = self._db.get_machine(str(machine_id))
        return Machine.from_dict(machine_data) if machine_data else None

    def find_by_request_id(self, request_id: RequestId) -> List[Machine]:
        """Find all machines associated with a request."""
        machines_data = self._db.get_machines_by_request_id(str(request_id))
        return [Machine.from_dict(data) for data in machines_data]

    def find_by_status(self, status: MachineStatus) -> List[Machine]:
        """Find all machines with a specific status."""
        machines_data = self._db.get_machines_by_status(status.value)
        return [Machine.from_dict(data) for data in machines_data]

    def find_active_machines(self) -> List[Machine]:
        """Find all active (running) machines."""
        return self.find_by_status(MachineStatus.RUNNING)

    def find_unhealthy_machines(self) -> List[Machine]:
        """Find machines with failed health checks."""
        all_machines = self.find_by_status(MachineStatus.RUNNING)
        return [
            machine for machine in all_machines
            if not machine.is_healthy
        ]

    def find_machines_for_return(self) -> List[Machine]:
        """Find machines that are marked for return."""
        return self.find_by_criteria({"status": MachineStatus.RETURNED.value})

    def delete(self, machine_id: MachineId) -> None:
        """Delete a machine."""
        self._db.delete_machine(str(machine_id))

    def exists(self, machine_id: MachineId) -> bool:
        """Check if a machine exists."""
        return self._db.get_machine(str(machine_id)) is not None

    def clean_terminated_machines(self, max_age_hours: int = 24) -> None:
        """Clean up old terminated machines."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        terminated_machines = self.find_by_status(MachineStatus.TERMINATED)
        
        for machine in terminated_machines:
            if machine.terminated_time and machine.terminated_time < cutoff_time:
                self.delete(machine.machine_id)