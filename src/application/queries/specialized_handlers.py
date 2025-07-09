"""Specialized query handlers for application services."""
from __future__ import annotations
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.application.interfaces.command_query import QueryHandler
from src.infrastructure.ports.resource_provisioning_port import ResourceProvisioningPort
from src.domain.base.dependency_injection import injectable
from src.application.dto.queries import (
    GetActiveMachineCountQuery,
    GetRequestSummaryQuery,
    GetMachineHealthQuery
)
from src.application.dto.responses import (
    RequestSummaryDTO,
    MachineHealthDTO
)

# Exception handling infrastructure
from src.domain.machine.value_objects import MachineStatus
from src.domain.base.exceptions import EntityNotFoundError
from src.domain.base.ports import LoggingPort, ContainerPort
from src.infrastructure.utilities.factories.repository_factory import UnitOfWork
from src.domain.base import UnitOfWorkFactory

@injectable
class GetActiveMachineCountHandler(QueryHandler[GetActiveMachineCountQuery, int]):
    """Handler for getting count of active machines."""

    def __init__(self, 
                 logger: LoggingPort,
                 container: ContainerPort,
                 uow: Optional[UnitOfWork] = None) -> None:
        self.uow = uow
        self.logger = logger
        self._container = container
        self.uow_factory = self._container.get(UnitOfWorkFactory) if uow is None else None

    
    def handle(self, query: GetActiveMachineCountQuery) -> int:
        """Handle get active machine count query."""
        # Get unit of work if not provided in constructor
        uow = self.uow or self.uow_factory.create_unit_of_work()
        
        with uow:
            active_machines = uow.machines.find_active_machines()
            count = len(active_machines)
            
            self.logger.debug(
                f"Found {count} active machines",
                extra={'active_machine_count': count}
            )
            
            return count

@injectable
class GetRequestSummaryHandler(QueryHandler[GetRequestSummaryQuery, RequestSummaryDTO]):
    """Handler for getting request summary."""

    def __init__(self, 
                 logger: LoggingPort,
                 container: ContainerPort,
                 uow: Optional[UnitOfWork] = None, 
                 instance_manager=None) -> None:
        self.uow = uow
        self.instance_manager = instance_manager
        self.logger = logger
        self._container = container
        self.uow_factory = self._container.get(UnitOfWorkFactory) if uow is None else None

    
    def handle(self, query: GetRequestSummaryQuery) -> RequestSummaryDTO:
        """Handle get request summary query."""
        # Validate request_id is not None
        if query.request_id is None:
            raise ValueError("Request ID cannot be None. This typically happens when a request fails to be created properly.")
            
        # Get unit of work if not provided in constructor
        uow = self.uow or self.uow_factory.create_unit_of_work()
        
        with uow:
            # Get request
            request = uow.requests.find_by_id(query.request_id)
            if not request:
                raise EntityNotFoundError("Request", query.request_id)
            
            # Get machines for this request
            machines = uow.machines.find_by_request(request.request_id)
            
            # Synchronize machine statuses with provider (generates events if status changed)
            updated_machines = self._synchronize_machine_statuses(machines, uow)
            
            # Count machines by status (use updated machines)
            machine_statuses: Dict[str, int] = {}
            for machine in updated_machines:
                status = machine.status.value
                if status in machine_statuses:
                    machine_statuses[status] += 1
                else:
                    machine_statuses[status] = 1
            
            # Calculate duration if request is complete
            duration = None
            if request.status.is_terminal and request.updated_at:
                duration = (request.updated_at - request.created_at).total_seconds()
            
            return RequestSummaryDTO(
                request_id=str(request.request_id),
                status=request.status.value,
                total_machines=len(updated_machines),
                machine_statuses=machine_statuses,
                created_at=request.created_at,
                updated_at=request.updated_at,
                duration=duration
            )
    
    def _synchronize_machine_statuses(self, machines: List[Any], uow: UnitOfWork) -> List[Any]:
        """
        Synchronize machine statuses with provider and generate events for changes.
        This is where machine business events are generated during status checking.
        """
        if not self.instance_manager:
            return machines
            
        updated_machines = []
        machines_to_save = []
        
        try:
            instance_ids = [str(machine.instance_id) for machine in machines]
            status_response = self.instance_manager.get_instance_status(instance_ids)
            
            for machine in machines:
                provider_instance = next((inst for inst in status_response.instances 
                                   if inst.instance_id == str(machine.instance_id)), None)
                if provider_instance:
                    domain_status = self._map_instance_state_to_machine_status(provider_instance.state)
                    if machine.status != domain_status:
                        updated_machine = machine.update_status(domain_status, f"Provider sync: {provider_instance.state}")
                        machines_to_save.append(updated_machine)
                        updated_machines.append(updated_machine)
                    else:
                        updated_machines.append(machine)
                else:
                    updated_machines.append(machine)
            
            if machines_to_save:
                uow.machines.save_batch(machines_to_save)
                
        except Exception as e:
            self.logger.warning(f"Failed to sync machine statuses: {e}")
            updated_machines = machines
        
        return updated_machines
    
    def _map_instance_state_to_machine_status(self, instance_state: str) -> 'MachineStatus':
        """Map provider instance state string to MachineStatus enum.
        
        Args:
            instance_state: Provider instance state as string (e.g., 'running', 'stopped')
            
        Returns:
            MachineStatus enum value
        """
        from src.domain.machine.value_objects import MachineStatus
        
        try:
            # Direct string-to-enum conversion (MachineStatus values match provider states)
            return MachineStatus(instance_state.lower())
        except ValueError:
            # Handle unknown states gracefully
            return MachineStatus.UNKNOWN

@injectable
class GetMachineHealthHandler(QueryHandler[GetMachineHealthQuery, MachineHealthDTO]):
    """Handler for getting machine health status."""

    def __init__(self, 
                 logger: LoggingPort,
                 container: ContainerPort,
                 uow: Optional[UnitOfWork] = None,
                 resource_provisioning_port: Optional[ResourceProvisioningPort] = None) -> None:
        self.uow = uow
        self._resource_provisioning_port = resource_provisioning_port
        self.logger = logger
        self._container = container
        self.uow_factory = self._container.get(UnitOfWorkFactory) if uow is None else None
        
    @property
    def resource_provisioning_port(self) -> ResourceProvisioningPort:
        """
        Lazy initialization for resource provisioning port.
        
        Returns:
            ResourceProvisioningPort instance
        """
        if self._resource_provisioning_port is None:
            self._resource_provisioning_port = self._container.get(ResourceProvisioningPort)
        return self._resource_provisioning_port

    
    def handle(self, query: GetMachineHealthQuery) -> MachineHealthDTO:
        """Handle get machine health query."""
        # Get unit of work if not provided in constructor
        uow = self.uow or self.uow_factory.create_unit_of_work()
        
        with uow:
            # Get machine
            machine = uow.machines.find_by_id(query.machine_id)
            if not machine:
                raise EntityNotFoundError("Machine", query.machine_id)
            
            # Get health status using the resource provisioning port
            instance_id = machine.resource_id
            health_data = self.resource_provisioning_port.get_resource_health(instance_id)
            
            # Extract metrics
            metrics = []
            if 'metrics' in health_data:
                metrics = health_data['metrics']
            
            # Determine overall status
            overall_status = "unknown"
            if 'status' in health_data:
                if health_data['status'] == 'ok' or health_data['status'] == 'active':
                    overall_status = "healthy"
                elif health_data['status'] == 'impaired':
                    overall_status = "impaired"
                elif health_data['status'] == 'failed' or health_data['status'] == 'inactive':
                    overall_status = "unhealthy"
            
            return MachineHealthDTO(
                machine_id=str(machine.machine_id),
                overall_status=overall_status,
                system_status=health_data.get('system_status', 'unknown'),
                instance_status=health_data.get('status', 'unknown'),
                metrics=metrics,
                last_check=datetime.utcnow()
            )
