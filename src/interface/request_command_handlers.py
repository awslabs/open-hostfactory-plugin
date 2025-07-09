"""Request-related command handlers for the interface layer."""
from typing import Dict, Any, Optional

from src.application.base.command_handler import CLICommandHandler
from src.application.request.dto import RequestStatusResponse


class GetRequestStatusCLIHandler(CLICommandHandler):
    """Handler for getRequestStatus command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle getRequestStatus command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Request status information
            
        Raises:
            ValueError: If request ID is not provided
        """
        input_data = self.process_input(command)
        
        # Determine request_id from either input data or command line
        request_id = None
        if input_data and 'requests' in input_data:
            requests = input_data['requests']
            if isinstance(requests, list) and requests:
                request_id = requests[0].get('requestId')
            elif isinstance(requests, dict):
                request_id = requests.get('requestId')  # nosec B113 - This is a dictionary access, not an HTTP request
        elif hasattr(command, 'request_id') and command.request_id:
            request_id = command.request_id
            
        if not request_id:
            self.logger.error("Request ID is required")
            raise ValueError("Request ID is required")
            
        # Execute via CQRS QueryBus
        self.logger.debug(f"Getting request status for {request_id}")
        
        # Get request with machine information based on long flag using CQRS
        from src.application.request.queries import GetRequestStatusQuery
        query = GetRequestStatusQuery(
            request_id=request_id,
            include_machines=command.long if hasattr(command, 'long') else False
        )
        request_dto = self._query_bus.dispatch(query)
        
        # Convert DTO to response format
        if request_dto:
            request_dict = request_dto.model_dump() if hasattr(request_dto, 'model_dump') else request_dto
        else:
            # If it's already a DTO, convert to dict
            request_dict = request_dto.to_dict() if hasattr(request_dto, 'to_dict') else {}
            
        # Create response using RequestStatusResponse
        response = RequestStatusResponse(
            requests=[request_dict],
            status="complete",
            message="Status retrieved successfully."
        )
        
        result = response.to_dict()
        self.logger.debug(f"Request status result: {result}")
        return result


class RequestMachinesCLIHandler(CLICommandHandler):
    """Handler for requestMachines command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle requestMachines command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Request creation result
        """
        input_data = self.process_input(command)
        
        if not input_data:
            self.logger.error("Input data is required for requestMachines")
            raise ValueError("Input data is required for requestMachines")
            
        # Extract template_id and machine_count from input
        template_id = input_data.get('templateId')
        machine_count = input_data.get('machineCount', 1)
        
        if not template_id:
            self.logger.error("Template ID is required")
            raise ValueError("Template ID is required")
            
        # Execute via CQRS CommandBus
        self.logger.debug(f"Requesting {machine_count} machines with template {template_id}")
        
        # Import dry-run context checker
        from src.infrastructure.mocking.dry_run_context import is_dry_run_active
        
        from src.application.dto.commands import CreateRequestCommand
        cmd = CreateRequestCommand(
            template_id=template_id,
            machine_count=machine_count,
            timeout=input_data.get('timeout', 3600),
            tags=input_data.get('tags', {}),
            metadata=input_data.get('metadata', {}),
            dry_run=is_dry_run_active()  # Propagate global dry-run context
        )
        request_id = self._command_bus.dispatch(cmd)
        
        result = {
            "requestId": request_id,
            "message": "Request created successfully",
            "templateId": template_id,
            "machineCount": machine_count
        }
        
        self.logger.debug(f"Request machines result: {result}")
        return result


class GetReturnRequestsCLIHandler(CLICommandHandler):
    """Handler for getReturnRequests command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle getReturnRequests command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Return requests information
        """
        # Execute via CQRS QueryBus
        self.logger.debug("Getting return requests")
        
        from src.application.request.queries import ListRequestsQuery
        query = ListRequestsQuery(
            status="return_requested",
            limit=100
        )
        return_requests = self._query_bus.dispatch(query)
        
        # Convert to response format
        requests_list = []
        if return_requests:
            for req in return_requests:
                if hasattr(req, 'to_dict'):
                    requests_list.append(req.to_dict())
                elif hasattr(req, 'model_dump'):
                    requests_list.append(req.model_dump())
                else:
                    requests_list.append(req)
        
        result = {
            "returnRequests": requests_list,
            "count": len(requests_list),
            "message": "Return requests retrieved successfully"
        }
        
        self.logger.debug(f"Return requests result: {result}")
        return result


class RequestReturnMachinesCLIHandler(CLICommandHandler):
    """Handler for requestReturnMachines command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle requestReturnMachines command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Return request creation result
        """
        input_data = self.process_input(command)
        
        # Handle different input formats
        machine_ids = []
        if input_data:
            if 'machines' in input_data:
                machines = input_data['machines']
                if isinstance(machines, list):
                    machine_ids = [m.get('machineId') if isinstance(m, dict) else str(m) for m in machines]
                elif isinstance(machines, dict):
                    machine_ids = [machines.get('machineId')]
            elif 'machineIds' in input_data:
                machine_ids = input_data['machineIds']
        
        # Execute via CQRS CommandBus
        self.logger.debug(f"Requesting return of machines: {machine_ids}")
        
        # Import dry-run context checker
        from src.infrastructure.mocking.dry_run_context import is_dry_run_active
        
        from src.application.dto.commands import CreateReturnRequestCommand
        cmd = CreateReturnRequestCommand(
            machine_ids=machine_ids,
            timeout=input_data.get('timeout', 3600) if input_data else 3600,
            force_return=input_data.get('forceReturn', False) if input_data else False,
            metadata=input_data.get('metadata', {}) if input_data else {},
            dry_run=is_dry_run_active()  # Propagate global dry-run context
        )
        request_id = self._command_bus.dispatch(cmd)
        
        result = {
            "requestId": request_id,
            "message": "Return request created successfully",
            "machineCount": len(machine_ids)
        }
        
        self.logger.debug(f"Request return machines result: {result}")
        return result
