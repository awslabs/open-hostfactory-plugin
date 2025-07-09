"""System-related command handlers for the interface layer."""
from __future__ import annotations
from typing import Dict, Any

from src.application.base.command_handler import CLICommandHandler


class MigrateRepositoryCLIHandler(CLICommandHandler):
    """Handler for migrateRepository command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle migrateRepository command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Migration result
        """
        source_type = getattr(command, 'source_type', 'json')
        target_type = getattr(command, 'target_type', 'dynamodb')
        
        # Execute via CQRS CommandBus
        self.logger.debug(f"Migrating repository from {source_type} to {target_type}")
        
        from src.application.system.commands import MigrateRepositoryCommand
        cmd = MigrateRepositoryCommand(
            source_type=source_type,
            target_type=target_type
        )
        result = self._command_bus.dispatch(cmd)
        
        return {
            "message": f"Repository migration from {source_type} to {target_type} completed",
            "result": result
        }


class GetProviderHealthCLIHandler(CLICommandHandler):
    """Handler for getProviderHealth command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle getProviderHealth command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Provider health information
        """
        # Execute via CQRS QueryBus
        self.logger.debug("Getting provider health")
        
        from src.application.system.queries import GetSystemStatusQuery
        query = GetSystemStatusQuery()
        health_status = self._query_bus.dispatch(query)
        
        return {
            "health": health_status,
            "message": "Provider health retrieved successfully"
        }


class ListAvailableProvidersCLIHandler(CLICommandHandler):
    """Handler for listAvailableProviders command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle listAvailableProviders command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Available providers information
        """
        # Execute via CQRS QueryBus
        self.logger.debug("Listing available providers")
        
        # For now, return static list - can be enhanced with dynamic discovery
        providers = [
            {
                "name": "aws",
                "type": "cloud",
                "status": "active",
                "capabilities": ["ec2", "spot_fleet", "auto_scaling"]
            }
        ]
        
        return {
            "providers": providers,
            "count": len(providers),
            "message": "Available providers retrieved successfully"
        }


class GetProviderConfigCLIHandler(CLICommandHandler):
    """Handler for getProviderConfig command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle getProviderConfig command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Provider configuration information
        """
        provider_name = getattr(command, 'provider', 'aws')
        
        # Execute via CQRS QueryBus
        self.logger.debug(f"Getting provider config for {provider_name}")
        
        from src.application.system.queries import GetProviderConfigQuery
        query = GetProviderConfigQuery(provider_name=provider_name)
        config = self._query_bus.dispatch(query)
        
        return {
            "provider": provider_name,
            "config": config,
            "message": f"Provider config for {provider_name} retrieved successfully"
        }


class ValidateProviderConfigCLIHandler(CLICommandHandler):
    """Handler for validateProviderConfig command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle validateProviderConfig command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Validation result
        """
        input_data = self.process_input(command)
        provider_name = getattr(command, 'provider', 'aws')
        
        # Execute via CQRS CommandBus
        self.logger.debug(f"Validating provider config for {provider_name}")
        
        from src.application.system.commands import ValidateProviderConfigCommand
        cmd = ValidateProviderConfigCommand(
            provider_name=provider_name,
            config=input_data or {}
        )
        validation_result = self._command_bus.dispatch(cmd)
        
        return {
            "provider": provider_name,
            "valid": validation_result.get('valid', False),
            "errors": validation_result.get('errors', []),
            "message": f"Provider config validation for {provider_name} completed"
        }


class ReloadProviderConfigCLIHandler(CLICommandHandler):
    """Handler for reloadProviderConfig command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle reloadProviderConfig command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Reload result
        """
        provider_name = getattr(command, 'provider', 'aws')
        
        # Execute via CQRS CommandBus
        self.logger.debug(f"Reloading provider config for {provider_name}")
        
        from src.application.system.commands import ReloadProviderConfigCommand
        cmd = ReloadProviderConfigCommand(provider_name=provider_name)
        result = self._command_bus.dispatch(cmd)
        
        return {
            "provider": provider_name,
            "reloaded": result,
            "message": f"Provider config for {provider_name} reloaded successfully"
        }


class MigrateProviderConfigCLIHandler(CLICommandHandler):
    """Handler for migrateProviderConfig command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle migrateProviderConfig command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Migration result
        """
        source_provider = getattr(command, 'source_provider', 'aws')
        target_provider = getattr(command, 'target_provider', 'aws')
        
        # Execute via CQRS CommandBus
        self.logger.debug(f"Migrating provider config from {source_provider} to {target_provider}")
        
        from src.application.system.commands import MigrateProviderConfigCommand
        cmd = MigrateProviderConfigCommand(
            source_provider=source_provider,
            target_provider=target_provider
        )
        result = self._command_bus.dispatch(cmd)
        
        return {
            "source": source_provider,
            "target": target_provider,
            "migrated": result,
            "message": f"Provider config migration from {source_provider} to {target_provider} completed"
        }


class SelectProviderStrategyCLIHandler(CLICommandHandler):
    """Handler for selectProviderStrategy command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle selectProviderStrategy command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Strategy selection result
        """
        strategy_name = getattr(command, 'strategy', 'default')
        
        # Execute via CQRS CommandBus
        self.logger.debug(f"Selecting provider strategy: {strategy_name}")
        
        from src.application.system.commands import SelectProviderStrategyCommand
        cmd = SelectProviderStrategyCommand(strategy_name=strategy_name)
        result = self._command_bus.dispatch(cmd)
        
        return {
            "strategy": strategy_name,
            "selected": result,
            "message": f"Provider strategy {strategy_name} selected successfully"
        }


class ExecuteProviderOperationCLIHandler(CLICommandHandler):
    """Handler for executeProviderOperation command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle executeProviderOperation command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Operation execution result
        """
        input_data = self.process_input(command)
        operation_name = getattr(command, 'operation', 'status')
        
        # Execute via CQRS CommandBus
        self.logger.debug(f"Executing provider operation: {operation_name}")
        
        from src.application.system.commands import ExecuteProviderOperationCommand
        cmd = ExecuteProviderOperationCommand(
            operation_name=operation_name,
            parameters=input_data or {}
        )
        result = self._command_bus.dispatch(cmd)
        
        return {
            "operation": operation_name,
            "result": result,
            "message": f"Provider operation {operation_name} executed successfully"
        }


class GetProviderMetricsCLIHandler(CLICommandHandler):
    """Handler for getProviderMetrics command."""
    
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle getProviderMetrics command.
        
        Args:
            command: Command object or arguments
            
        Returns:
            Provider metrics information
        """
        provider_name = getattr(command, 'provider', 'aws')
        
        # Execute via CQRS QueryBus
        self.logger.debug(f"Getting provider metrics for {provider_name}")
        
        from src.application.system.queries import GetProviderMetricsQuery
        query = GetProviderMetricsQuery(provider_name=provider_name)
        metrics = self._query_bus.dispatch(query)
        
        return {
            "provider": provider_name,
            "metrics": metrics,
            "message": f"Provider metrics for {provider_name} retrieved successfully"
        }
