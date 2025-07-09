"""Unit tests for configuration management CLI handlers."""
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from src.interface.command_handlers import (
    GetProviderConfigCLIHandler,
    ValidateProviderConfigCLIHandler,
    ReloadProviderConfigCLIHandler,
    MigrateProviderConfigCLIHandler
)


class TestGetProviderConfigCLIHandler:
    """Test GetProviderConfigCLIHandler functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_query_bus = Mock()
        self.mock_command_bus = Mock()
        self.handler = GetProviderConfigCLIHandler(
            query_bus=self.mock_query_bus,
            command_bus=self.mock_command_bus
        )
    
    def test_handle_success(self):
        """Test successful provider config retrieval."""
        # Setup
        mock_command = Mock()
        expected_result = {
            "status": "success",
            "provider_info": {
                "mode": "single",
                "provider_names": ["aws-primary"]
            }
        }
        
        self.mock_query_bus.dispatch.return_value = expected_result
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result == expected_result
        self.mock_query_bus.dispatch.assert_called_once()
        
        # Verify query type
        call_args = self.mock_query_bus.dispatch.call_args[0]
        query = call_args[0]
        assert query.__class__.__name__ == "GetProviderConfigQuery"
    
    def test_handle_exception(self):
        """Test handling of exceptions during config retrieval."""
        # Setup
        mock_command = Mock()
        self.mock_query_bus.dispatch.side_effect = Exception("Query failed")
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result["error"] == "Failed to get provider configuration: Query failed"
        assert result["status"] == "error"


class TestValidateProviderConfigCLIHandler:
    """Test ValidateProviderConfigCLIHandler functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_query_bus = Mock()
        self.mock_command_bus = Mock()
        self.handler = ValidateProviderConfigCLIHandler(
            query_bus=self.mock_query_bus,
            command_bus=self.mock_command_bus
        )
    
    def test_handle_valid_config(self):
        """Test validation of valid provider configuration."""
        # Setup
        mock_command = Mock()
        expected_result = {
            "status": "success",
            "validation_result": {
                "valid": True,
                "errors": [],
                "warnings": []
            }
        }
        
        self.mock_query_bus.dispatch.return_value = expected_result
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result == expected_result
        self.mock_query_bus.dispatch.assert_called_once()
        
        # Verify query type
        call_args = self.mock_query_bus.dispatch.call_args[0]
        query = call_args[0]
        assert query.__class__.__name__ == "ValidateProviderConfigQuery"
    
    def test_handle_invalid_config(self):
        """Test validation of invalid provider configuration."""
        # Setup
        mock_command = Mock()
        expected_result = {
            "status": "success",
            "validation_result": {
                "valid": False,
                "errors": ["Provider configuration invalid"],
                "warnings": ["Consider updating configuration"]
            }
        }
        
        self.mock_query_bus.dispatch.return_value = expected_result
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result == expected_result
        assert result["validation_result"]["valid"] is False
        assert len(result["validation_result"]["errors"]) > 0
    
    def test_handle_exception(self):
        """Test handling of exceptions during validation."""
        # Setup
        mock_command = Mock()
        self.mock_query_bus.dispatch.side_effect = Exception("Validation failed")
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result["valid"] is False
        assert "Configuration validation failed" in result["error"]
        assert result["status"] == "error"


class TestReloadProviderConfigCLIHandler:
    """Test ReloadProviderConfigCLIHandler functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_query_bus = Mock()
        self.mock_command_bus = Mock()
        self.handler = ReloadProviderConfigCLIHandler(
            query_bus=self.mock_query_bus,
            command_bus=self.mock_command_bus
        )
    
    def test_handle_success_with_path(self):
        """Test successful config reload with specific path."""
        # Setup
        mock_command = Mock()
        mock_command.config_path = "/path/to/config.json"
        mock_command.file = None  # No file input
        mock_command.data = None  # No data input
        
        expected_result = {
            "status": "success",
            "message": "Provider configuration reloaded successfully",
            "config_path": "/path/to/config.json"
        }
        
        self.mock_command_bus.dispatch.return_value = expected_result
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result == expected_result
        self.mock_command_bus.dispatch.assert_called_once()
        
        # Verify command type and parameters
        call_args = self.mock_command_bus.dispatch.call_args[0]
        command = call_args[0]
        assert command.__class__.__name__ == "ReloadProviderConfigCommand"
        assert command.config_path == "/path/to/config.json"
    
    def test_handle_success_default_path(self):
        """Test successful config reload with default path."""
        # Setup
        mock_command = Mock()
        mock_command.config_path = None
        mock_command.file = None  # No file input
        mock_command.data = None  # No data input
        
        expected_result = {
            "status": "success",
            "message": "Provider configuration reloaded successfully",
            "config_path": None
        }
        
        self.mock_command_bus.dispatch.return_value = expected_result
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result == expected_result
        
        # Verify command parameters
        call_args = self.mock_command_bus.dispatch.call_args[0]
        command = call_args[0]
        assert command.config_path is None
    
    def test_handle_with_input_data(self):
        """Test config reload with input data."""
        # Setup
        mock_command = Mock()
        mock_command.data = '{"config_path": "/custom/path.json"}'
        mock_command.file = None  # No file input
        
        expected_result = {
            "status": "success",
            "config_path": "/custom/path.json"
        }
        
        self.mock_command_bus.dispatch.return_value = expected_result
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result == expected_result
    
    def test_handle_exception(self):
        """Test handling of exceptions during reload."""
        # Setup
        mock_command = Mock()
        mock_command.config_path = "/invalid/path.json"
        mock_command.file = None  # No file input
        mock_command.data = None  # No data input
        self.mock_command_bus.dispatch.side_effect = Exception("Reload failed")
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result["success"] is False
        assert "Configuration reload failed" in result["error"]
        assert result["status"] == "error"


class TestMigrateProviderConfigCLIHandler:
    """Test MigrateProviderConfigCLIHandler functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_query_bus = Mock()
        self.mock_command_bus = Mock()
        self.handler = MigrateProviderConfigCLIHandler(
            query_bus=self.mock_query_bus,
            command_bus=self.mock_command_bus
        )
    
    def test_handle_success_default_options(self):
        """Test successful config migration with default options."""
        # Setup
        mock_command = Mock()
        mock_command.save_to_file = False
        mock_command.backup_original = True
        mock_command.file = None  # No file input
        mock_command.data = None  # No data input
        
        expected_result = {
            "status": "success",
            "message": "Provider configuration migration completed",
            "migration_summary": {
                "migration_type": "legacy_aws_to_unified",
                "providers_before": 1,
                "providers_after": 1
            }
        }
        
        self.mock_command_bus.dispatch.return_value = expected_result
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result == expected_result
        self.mock_command_bus.dispatch.assert_called_once()
        
        # Verify command type and parameters
        call_args = self.mock_command_bus.dispatch.call_args[0]
        command = call_args[0]
        assert command.__class__.__name__ == "MigrateProviderConfigCommand"
        assert command.save_to_file is False
        assert command.backup_original is True
    
    def test_handle_with_input_data(self):
        """Test config migration with input data."""
        # Setup
        mock_command = Mock()
        mock_command.data = '{"save_to_file": true, "backup_original": false}'
        mock_command.file = None  # No file input
        
        expected_result = {
            "status": "success",
            "migration_summary": {
                "migration_type": "legacy_aws_to_unified"
            }
        }
        
        self.mock_command_bus.dispatch.return_value = expected_result
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result == expected_result
        
        # Verify command parameters from input data
        call_args = self.mock_command_bus.dispatch.call_args[0]
        command = call_args[0]
        assert command.save_to_file is True
        assert command.backup_original is False
    
    def test_handle_exception(self):
        """Test handling of exceptions during migration."""
        # Setup
        mock_command = Mock()
        mock_command.save_to_file = True
        mock_command.file = None  # No file input
        mock_command.data = None  # No data input
        self.mock_command_bus.dispatch.side_effect = Exception("Migration failed")
        
        # Execute
        result = self.handler.handle(mock_command)
        
        # Verify
        assert result["success"] is False
        assert "Configuration migration failed" in result["error"]
        assert result["status"] == "error"
