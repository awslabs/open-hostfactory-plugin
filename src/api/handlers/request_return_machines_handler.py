"""Enhanced API handler for returning machines."""
from typing import Dict, Any, Optional, List, TYPE_CHECKING
import uuid

from src.infrastructure.handlers.base.api_handler import BaseAPIHandler
from src.application.dto.commands import CreateReturnRequestCommand
from src.application.dto.responses import RequestReturnMachinesResponse, CleanupResourcesResponse
from src.domain.machine.exceptions import MachineNotFoundError
from src.monitoring.metrics import MetricsCollector

# Exception handling infrastructure
from src.infrastructure.error.decorators import handle_interface_exceptions

class RequestReturnMachinesRESTHandler(BaseAPIHandler):
    """Enhanced API handler for returning machines - Pure CQRS Implementation."""

    def __init__(self, 
                 query_bus: 'QueryBus',
                 command_bus: 'CommandBus',
                 metrics: Optional[MetricsCollector] = None):
        """
        Initialize handler with pure CQRS dependencies.
        
        Args:
            query_bus: Query bus for CQRS queries
            command_bus: Command bus for CQRS commands
            metrics: Optional metrics collector
        """
        # Initialize without service dependency
        super().__init__(None, metrics)
        self._query_bus = query_bus
        self._command_bus = command_bus
        
    def handle(self,
               input_data: Optional[Dict[str, Any]] = None,
               all_flag: bool = False,
               long: bool = False,
               clean: bool = False,
               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Request machines to be returned.

        Args:
            input_data: Optional input data containing machine IDs
            all_flag: Whether to return all machines
            long: Not used for this endpoint but included for interface consistency
            clean: Whether to clean up all resources
            context: Request context information

        Returns:
            Dict containing return request status
        """
        # Apply middleware in standardized order
        return self.apply_middleware(self._handle, service_name="request_service")(
            input_data=input_data,
            all_flag=all_flag,
            long=long,
            clean=clean,
            context=context
        )
        
    @handle_interface_exceptions(context="request_return_machines_api", interface_type="api")
    def _handle(self,
                input_data: Optional[Dict[str, Any]] = None,
                all_flag: bool = False,
                long: bool = False,
                clean: bool = False,
                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Internal implementation of handle method.
        
        Args:
            input_data: Optional input data containing machine IDs
            all_flag: Whether to return all machines
            long: Not used for this endpoint but included for interface consistency
            clean: Whether to clean up all resources
            context: Request context information
            
        Returns:
            Dict containing return request status
        """
        context = context or {}
        correlation_id = context.get('correlation_id', str(uuid.uuid4()))
        start_time = self.metrics.start_timer() if self.metrics else None

        try:
            # Clean up all resources
            if clean:
                self.logger.info(
                    "Cleaning up all resources",
                    extra={
                        'correlation_id': correlation_id
                    }
                )
                
                # Create response DTO
                response = CleanupResourcesResponse(
                    metadata={
                        "correlation_id": correlation_id
                    }
                )
                
                # Convert to dict for API response
                return response.to_dict()

            if all_flag:
                # Create metadata for request
                metadata = {
                    'source_ip': context.get('client_ip'),
                    'user_agent': context.get('user_agent'),
                    'created_by': context.get('user_id'),
                    'correlation_id': correlation_id,
                    'all_machines': True
                }
                
                # Create return request for all machines using CQRS command
                command = CreateReturnRequestCommand(
                    machine_ids=[],  # Empty list indicates all machines
                )
                request_id = self._command_bus.execute(command)
                
                self.logger.info(
                    f"Created return request for all machines with ID: {request_id}",
                    extra={
                        'request_id': request_id,
                        'correlation_id': correlation_id
                    }
                )
                
                # Create response DTO
                response = RequestReturnMachinesResponse(
                    request_id=request_id,
                    message="Return request created for all machines",
                    metadata={
                        "correlation_id": correlation_id,
                        "timestamp": context.get('timestamp')
                    }
                )
                
                # Convert to dict for API response
                return response.to_dict()
            else:
                # Validate input
                if not input_data or 'machines' not in input_data:
                    raise ValueError("Input must include 'machines' key")

                machine_ids = self._extract_machine_ids(input_data['machines'])
                if not machine_ids:
                    # Create response DTO
                    response = RequestReturnMachinesResponse(
                        request_id=None,
                        message="No machines to return",
                        metadata={
                            "correlation_id": correlation_id,
                            "machine_count": 0
                        }
                    )
                    
                    # Convert to dict for API response
                    return response.to_dict()

                # Log request
                self.logger.info(
                    "Returning machines",
                    extra={
                        'correlation_id': correlation_id,
                        'machine_count': len(machine_ids),
                        'machine_ids': machine_ids,
                        'client_ip': context.get('client_ip')
                    }
                )

                # Create metadata for request
                metadata = {
                    'source_ip': context.get('client_ip'),
                    'user_agent': context.get('user_agent'),
                    'created_by': context.get('user_id'),
                    'correlation_id': correlation_id
                }
                
                # Create return request using CQRS command
                command = CreateReturnRequestCommand(
                    machine_ids=machine_ids,
                    metadata=metadata
                )
                request_id = self._command_bus.execute(command)
                
                # Record metrics
                if self.metrics:
                    self.metrics.record_success(
                        'request_return_machines',
                        start_time,
                        {
                            'machine_count': len(machine_ids),
                            'correlation_id': correlation_id,
                            'request_id': request_id
                        }
                    )

                # Create response DTO
                response = RequestReturnMachinesResponse(
                    request_id=request_id,
                    message="Delete VM success.",
                    metadata={
                        "correlation_id": correlation_id,
                        "machine_count": len(machine_ids),
                        "timestamp": context.get('timestamp')
                    }
                )
                
                # Convert to dict for API response
                return response.to_dict()

        except ValueError as e:
            # Let the error handling middleware handle this
            raise e

        except MachineNotFoundError as e:
            # Let the error handling middleware handle this
            raise e

        except Exception as e:
            # Let the error handling middleware handle this
            raise e

    def _extract_machine_ids(self, machines_data: List[Dict[str, Any]]) -> List[str]:
        """
        Extract and validate machine IDs from input data.
        
        Args:
            machines_data: List of machine data dictionaries
            
        Returns:
            List of machine IDs
            
        Raises:
            ValueError: If machine data is invalid
        """
        machine_ids = []
        for machine in machines_data:
            if not isinstance(machine, dict):
                raise ValueError("Each machine entry must be a dictionary")
            
            machine_id = machine.get('machineId')
            if not machine_id:
                continue
                
            if not isinstance(machine_id, str):
                raise ValueError(f"Invalid machine ID format: {machine_id}")
                
            machine_ids.append(machine_id)
            
        return machine_ids

if TYPE_CHECKING:
    from src.infrastructure.di.buses import QueryBus, CommandBus
