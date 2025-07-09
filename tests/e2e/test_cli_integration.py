"""End-to-end CLI integration tests for configuration-driven provider system."""
import pytest
import json
import tempfile
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch


class TestCLIIntegration:
    """Test complete CLI integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        self.project_root = Path(__file__).parent.parent.parent
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_config_file(self, config_data):
        """Create a temporary configuration file."""
        with open(self.config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        return self.config_path
    
    @patch('src.bootstrap.register_services')
    @patch('src.config.manager.get_config_manager')
    def test_get_provider_config_cli_e2e(self, mock_get_config, mock_register_services):
        """Test getProviderConfig CLI operation end-to-end."""
        # Setup mocks
        mock_container = Mock()
        mock_query_bus = Mock()
        mock_command_bus = Mock()
        
        expected_result = {
            "status": "success",
            "provider_info": {
                "mode": "single",
                "provider_names": ["aws-test"]
            }
        }
        
        mock_query_bus.dispatch.return_value = expected_result
        mock_container.get.side_effect = lambda cls: {
            'QueryBus': mock_query_bus,
            'CommandBus': mock_command_bus
        }.get(cls.__name__ if hasattr(cls, '__name__') else str(cls), Mock())
        
        mock_register_services.return_value = mock_container
        
        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get.return_value = {"type": "aws"}
        mock_config_manager.get_typed.return_value = Mock(logging=Mock())
        mock_get_config.return_value = mock_config_manager
        
        # Test CLI handler directly
        from src.interface.command_handlers import GetProviderConfigCLIHandler
        
        handler = GetProviderConfigCLIHandler(
            query_bus=mock_query_bus,
            command_bus=mock_command_bus
        )
        
        mock_command = Mock()
        mock_command.file = None
        mock_command.data = None
        
        result = handler.handle(mock_command)
        
        assert result == expected_result
        mock_query_bus.dispatch.assert_called_once()
    
    @patch('src.bootstrap.register_services')
    @patch('src.config.manager.get_config_manager')
    def test_validate_provider_config_cli_e2e(self, mock_get_config, mock_register_services):
        """Test validateProviderConfig CLI operation end-to-end."""
        # Setup mocks
        mock_container = Mock()
        mock_query_bus = Mock()
        mock_command_bus = Mock()
        
        expected_result = {
            "status": "success",
            "validation_result": {
                "valid": True,
                "errors": [],
                "warnings": [],
                "mode": "single"
            }
        }
        
        mock_query_bus.dispatch.return_value = expected_result
        mock_container.get.side_effect = lambda cls: {
            'QueryBus': mock_query_bus,
            'CommandBus': mock_command_bus
        }.get(cls.__name__ if hasattr(cls, '__name__') else str(cls), Mock())
        
        mock_register_services.return_value = mock_container
        
        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get.return_value = {"type": "aws"}
        mock_config_manager.get_typed.return_value = Mock(logging=Mock())
        mock_get_config.return_value = mock_config_manager
        
        # Test CLI handler
        from src.interface.command_handlers import ValidateProviderConfigCLIHandler
        
        handler = ValidateProviderConfigCLIHandler(
            query_bus=mock_query_bus,
            command_bus=mock_command_bus
        )
        
        mock_command = Mock()
        mock_command.file = None
        mock_command.data = None
        
        result = handler.handle(mock_command)
        
        assert result == expected_result
        assert result["validation_result"]["valid"] is True
        mock_query_bus.dispatch.assert_called_once()
    
    @patch('src.bootstrap.register_services')
    @patch('src.config.manager.get_config_manager')
    def test_reload_provider_config_cli_e2e(self, mock_get_config, mock_register_services):
        """Test reloadProviderConfig CLI operation end-to-end."""
        # Setup mocks
        mock_container = Mock()
        mock_query_bus = Mock()
        mock_command_bus = Mock()
        
        expected_result = {
            "status": "success",
            "message": "Provider configuration reloaded successfully",
            "config_path": self.config_path
        }
        
        mock_command_bus.dispatch.return_value = expected_result
        mock_container.get.side_effect = lambda cls: {
            'QueryBus': mock_query_bus,
            'CommandBus': mock_command_bus
        }.get(cls.__name__ if hasattr(cls, '__name__') else str(cls), Mock())
        
        mock_register_services.return_value = mock_container
        
        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get.return_value = {"type": "aws"}
        mock_config_manager.get_typed.return_value = Mock(logging=Mock())
        mock_get_config.return_value = mock_config_manager
        
        # Test CLI handler
        from src.interface.command_handlers import ReloadProviderConfigCLIHandler
        
        handler = ReloadProviderConfigCLIHandler(
            query_bus=mock_query_bus,
            command_bus=mock_command_bus
        )
        
        mock_command = Mock()
        mock_command.config_path = self.config_path
        mock_command.file = None
        mock_command.data = None
        
        result = handler.handle(mock_command)
        
        assert result == expected_result
        assert result["config_path"] == self.config_path
        mock_command_bus.dispatch.assert_called_once()
    
    @patch('src.bootstrap.register_services')
    @patch('src.config.manager.get_config_manager')
    def test_migrate_provider_config_cli_e2e(self, mock_get_config, mock_register_services):
        """Test migrateProviderConfig CLI operation end-to-end."""
        # Setup mocks
        mock_container = Mock()
        mock_query_bus = Mock()
        mock_command_bus = Mock()
        
        expected_result = {
            "status": "success",
            "message": "Provider configuration migration completed",
            "migration_summary": {
                "migration_type": "legacy_aws_to_unified",
                "providers_before": 1,
                "providers_after": 1
            }
        }
        
        mock_command_bus.dispatch.return_value = expected_result
        mock_container.get.side_effect = lambda cls: {
            'QueryBus': mock_query_bus,
            'CommandBus': mock_command_bus
        }.get(cls.__name__ if hasattr(cls, '__name__') else str(cls), Mock())
        
        mock_register_services.return_value = mock_container
        
        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get.return_value = {"type": "aws"}
        mock_config_manager.get_typed.return_value = Mock(logging=Mock())
        mock_get_config.return_value = mock_config_manager
        
        # Test CLI handler
        from src.interface.command_handlers import MigrateProviderConfigCLIHandler
        
        handler = MigrateProviderConfigCLIHandler(
            query_bus=mock_query_bus,
            command_bus=mock_command_bus
        )
        
        mock_command = Mock()
        mock_command.save_to_file = True
        mock_command.backup_original = True
        mock_command.file = None
        mock_command.data = None
        
        result = handler.handle(mock_command)
        
        assert result == expected_result
        assert result["migration_summary"]["migration_type"] == "legacy_aws_to_unified"
        mock_command_bus.dispatch.assert_called_once()
    
    @patch('src.bootstrap.register_services')
    @patch('src.config.manager.get_config_manager')
    def test_select_provider_strategy_cli_e2e(self, mock_get_config, mock_register_services):
        """Test selectProviderStrategy CLI operation end-to-end."""
        # Setup mocks
        mock_container = Mock()
        mock_query_bus = Mock()
        mock_command_bus = Mock()
        
        expected_result = {
            "selected_strategy": "aws-primary",
            "selection_reason": "Best match for required capabilities",
            "strategy_info": {
                "name": "aws-primary",
                "type": "aws",
                "health_status": "healthy"
            }
        }
        
        mock_command_bus.dispatch.return_value = expected_result
        mock_container.get.side_effect = lambda cls: {
            'QueryBus': mock_query_bus,
            'CommandBus': mock_command_bus
        }.get(cls.__name__ if hasattr(cls, '__name__') else str(cls), Mock())
        
        mock_register_services.return_value = mock_container
        
        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get.return_value = {"type": "aws"}
        mock_config_manager.get_typed.return_value = Mock(logging=Mock())
        mock_get_config.return_value = mock_config_manager
        
        # Test CLI handler
        from src.interface.command_handlers import SelectProviderStrategyCLIHandler
        
        handler = SelectProviderStrategyCLIHandler(
            query_bus=mock_query_bus,
            command_bus=mock_command_bus
        )
        
        mock_command = Mock()
        mock_command.file = None
        mock_command.data = json.dumps({
            "operation_type": "CREATE_INSTANCES",
            "required_capabilities": ["compute"],
            "min_success_rate": 0.95
        })
        
        result = handler.handle(mock_command)
        
        assert result == expected_result
        assert result["selected_strategy"] == "aws-primary"
        mock_command_bus.dispatch.assert_called_once()
    
    def test_cli_data_input_parsing_e2e(self):
        """Test CLI data input parsing end-to-end."""
        from src.interface.command_handlers import GetProviderConfigCLIHandler
        
        mock_query_bus = Mock()
        mock_command_bus = Mock()
        
        handler = GetProviderConfigCLIHandler(
            query_bus=mock_query_bus,
            command_bus=mock_command_bus
        )
        
        # Test JSON data parsing
        mock_command = Mock()
        mock_command.file = None
        mock_command.data = '{"include_sensitive": true}'
        
        input_data = handler.process_input(mock_command)
        
        assert input_data is not None
        assert input_data["include_sensitive"] is True
    
    def test_cli_file_input_parsing_e2e(self):
        """Test CLI file input parsing end-to-end."""
        from src.interface.command_handlers import ReloadProviderConfigCLIHandler
        
        # Create test input file
        input_data = {"config_path": "/test/path.json"}
        input_file = os.path.join(self.temp_dir, "input.json")
        
        with open(input_file, 'w') as f:
            json.dump(input_data, f)
        
        mock_query_bus = Mock()
        mock_command_bus = Mock()
        
        handler = ReloadProviderConfigCLIHandler(
            query_bus=mock_query_bus,
            command_bus=mock_command_bus
        )
        
        # Test file input parsing
        mock_command = Mock()
        mock_command.file = input_file
        mock_command.data = None
        
        parsed_data = handler.process_input(mock_command)
        
        assert parsed_data is not None
        assert parsed_data["config_path"] == "/test/path.json"
    
    def test_cli_error_handling_e2e(self):
        """Test CLI error handling scenarios end-to-end."""
        from src.interface.command_handlers import ValidateProviderConfigCLIHandler
        
        mock_query_bus = Mock()
        mock_command_bus = Mock()
        
        # Mock query bus to raise exception
        mock_query_bus.dispatch.side_effect = Exception("Validation failed")
        
        handler = ValidateProviderConfigCLIHandler(
            query_bus=mock_query_bus,
            command_bus=mock_command_bus
        )
        
        mock_command = Mock()
        mock_command.file = None
        mock_command.data = None
        
        result = handler.handle(mock_command)
        
        # Should return error response instead of raising exception
        assert result["valid"] is False
        assert "Configuration validation failed" in result["error"]
        assert result["status"] == "error"
    
    def test_cli_integration_with_provider_strategy_e2e(self):
        """Test CLI integration with provider strategy system end-to-end."""
        # Create multi-provider configuration
        config_data = {
            "provider": {
                "selection_policy": "ROUND_ROBIN",
                "providers": [
                    {
                        "name": "aws-primary",
                        "type": "aws",
                        "enabled": True,
                        "priority": 1,
                        "weight": 70,
                        "config": {"region": "us-east-1"}
                    },
                    {
                        "name": "aws-backup",
                        "type": "aws",
                        "enabled": True,
                        "priority": 2,
                        "weight": 30,
                        "config": {"region": "us-west-2"}
                    }
                ]
            }
        }
        
        config_path = self.create_config_file(config_data)
        
        # Test that CLI operations work with multi-provider configuration
        from src.config.manager import ConfigurationManager
        from src.infrastructure.factories.provider_strategy_factory import ProviderStrategyFactory
        
        config_manager = ConfigurationManager(config_path)
        factory = ProviderStrategyFactory(config_manager, Mock())
        
        # Test provider info retrieval
        provider_info = factory.get_provider_info()
        
        assert provider_info["mode"] == "multi"
        assert provider_info["selection_policy"] == "ROUND_ROBIN"
        assert provider_info["active_providers"] == 2
        assert "aws-primary" in provider_info["provider_names"]
        assert "aws-backup" in provider_info["provider_names"]
    
    def test_cli_template_operations_integration_e2e(self):
        """Test CLI template operations with provider strategy integration."""
        from src.interface.command_handlers import GetAvailableTemplatesCLIHandler
        
        mock_query_bus = Mock()
        mock_command_bus = Mock()
        
        expected_result = {
            "templates": [
                {
                    "template_id": "basic-template",
                    "provider_api": "aws-primary",
                    "available": True
                }
            ],
            "total_count": 1,
            "provider_info": {
                "mode": "multi",
                "active_providers": ["aws-primary", "aws-backup"]
            }
        }
        
        mock_query_bus.dispatch.return_value = expected_result
        
        handler = GetAvailableTemplatesCLIHandler(
            query_bus=mock_query_bus,
            command_bus=mock_command_bus
        )
        
        mock_command = Mock()
        mock_command.provider_api = "aws-primary"
        mock_command.file = None
        mock_command.data = None
        
        result = handler.handle(mock_command)
        
        assert result == expected_result
        assert result["provider_info"]["mode"] == "multi"
        assert len(result["provider_info"]["active_providers"]) == 2
