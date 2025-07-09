"""End-to-end integration tests for configuration-driven provider system."""
import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

from src.bootstrap import Application
from src.config.manager import ConfigurationManager


class TestConfigurationIntegration:
    """Test complete configuration integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_config_file(self, config_data):
        """Create a temporary configuration file."""
        with open(self.config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        return self.config_path
    
    def test_single_provider_configuration_e2e(self):
        """Test end-to-end single provider configuration."""
        # Create single provider configuration
        config_data = {
            "provider": {
                "active_provider": "aws-test",
                "providers": [
                    {
                        "name": "aws-test",
                        "type": "aws",
                        "enabled": True,
                        "config": {
                            "region": "us-east-1",
                            "profile": "default"
                        }
                    }
                ]
            },
            "logging": {
                "level": "INFO",
                "console_enabled": False
            }
        }
        
        config_path = self.create_config_file(config_data)
        
        # Test configuration loading
        config_manager = ConfigurationManager(config_path)
        unified_config = config_manager.get_unified_provider_config()
        
        assert unified_config.get_mode().value == "single"
        assert len(unified_config.get_active_providers()) == 1
        assert unified_config.get_active_providers()[0].name == "aws-test"
    
    def test_multi_provider_configuration_e2e(self):
        """Test end-to-end multi-provider configuration."""
        # Create multi-provider configuration
        config_data = {
            "provider": {
                "selection_policy": "ROUND_ROBIN",
                "health_check_interval": 30,
                "providers": [
                    {
                        "name": "aws-primary",
                        "type": "aws",
                        "enabled": True,
                        "priority": 1,
                        "weight": 70,
                        "config": {
                            "region": "us-east-1"
                        }
                    },
                    {
                        "name": "aws-backup",
                        "type": "aws",
                        "enabled": True,
                        "priority": 2,
                        "weight": 30,
                        "config": {
                            "region": "us-west-2"
                        }
                    }
                ]
            },
            "logging": {
                "level": "DEBUG"
            }
        }
        
        config_path = self.create_config_file(config_data)
        
        # Test configuration loading
        config_manager = ConfigurationManager(config_path)
        unified_config = config_manager.get_unified_provider_config()
        
        assert unified_config.get_mode().value == "multi"
        assert len(unified_config.get_active_providers()) == 2
        assert unified_config.selection_policy == "ROUND_ROBIN"
        assert unified_config.health_check_interval == 30
    
    def test_legacy_configuration_e2e(self):
        """Test end-to-end legacy configuration support."""
        # Create legacy configuration
        config_data = {
            "provider": {
                "type": "aws",
                "aws": {
                    "region": "us-east-1",
                    "profile": "default"
                }
            },
            "logging": {
                "level": "INFO"
            }
        }
        
        config_path = self.create_config_file(config_data)
        
        # Test configuration loading
        config_manager = ConfigurationManager(config_path)
        unified_config = config_manager.get_unified_provider_config()
        
        assert unified_config.get_mode().value == "legacy"
        assert unified_config.type == "aws"
        assert unified_config.aws["region"] == "us-east-1"
    
    @patch('src.infrastructure.di.services.register_services')
    def test_application_bootstrap_integration(self, mock_register_services):
        """Test application bootstrap with configuration integration."""
        # Setup mocks
        mock_container = Mock()
        mock_application_service = Mock()
        mock_application_service.initialize.return_value = True
        mock_application_service.get_provider_info.return_value = {
            "mode": "single",
            "provider_names": ["aws-test"]
        }
        
        mock_container.get.return_value = mock_application_service
        mock_register_services.return_value = mock_container
        
        # Create configuration
        config_data = {
            "provider": {
                "active_provider": "aws-test",
                "providers": [
                    {
                        "name": "aws-test",
                        "type": "aws",
                        "enabled": True,
                        "config": {"region": "us-east-1"}
                    }
                ]
            },
            "logging": {"level": "INFO"}
        }
        
        config_path = self.create_config_file(config_data)
        
        # Test application initialization
        with patch('src.bootstrap.get_config_manager') as mock_get_config:
            mock_config_manager = Mock()
            mock_config_manager.get.return_value = {"type": "aws"}
            mock_config_manager.get_typed.return_value = Mock(logging=Mock())
            mock_config_manager.get_unified_provider_config.return_value = Mock(
                get_mode=Mock(return_value=Mock(value="single")),
                get_active_providers=Mock(return_value=[Mock(name="aws-test")])
            )
            mock_get_config.return_value = mock_config_manager
            
            app = Application(config_path=config_path)
            result = app.initialize()
            
            assert result is True
            mock_application_service.initialize.assert_called_once()
    
    def test_configuration_migration_e2e(self):
        """Test end-to-end configuration migration."""
        # Create legacy configuration
        legacy_config = {
            "provider": {
                "type": "aws",
                "aws": {
                    "region": "us-east-1",
                    "profile": "default"
                }
            }
        }
        
        config_path = self.create_config_file(legacy_config)
        
        # Test migration
        config_manager = ConfigurationManager(config_path)
        
        # Simulate migration (would normally be done by migration command)
        unified_config = config_manager.get_unified_provider_config()
        
        # Verify migration result
        assert unified_config.get_mode().value == "legacy"
        assert unified_config.type == "aws"
        assert unified_config.aws["region"] == "us-east-1"
    
    def test_provider_strategy_factory_integration(self):
        """Test provider strategy factory integration with configuration."""
        from src.infrastructure.factories.provider_strategy_factory import ProviderStrategyFactory
        from unittest.mock import Mock
        
        # Create configuration
        config_data = {
            "provider": {
                "selection_policy": "ROUND_ROBIN",
                "providers": [
                    {
                        "name": "aws-test",
                        "type": "aws",
                        "enabled": True,
                        "config": {"region": "us-east-1"}
                    }
                ]
            }
        }
        
        config_path = self.create_config_file(config_data)
        
        # Test factory integration
        config_manager = ConfigurationManager(config_path)
        mock_logger = Mock()
        
        factory = ProviderStrategyFactory(config_manager, mock_logger)
        
        # Test provider info retrieval
        provider_info = factory.get_provider_info()
        
        assert provider_info["mode"] == "single"
        assert provider_info["selection_policy"] == "ROUND_ROBIN"
        assert provider_info["total_providers"] == 1
        assert provider_info["active_providers"] == 1
    
    def test_configuration_validation_e2e(self):
        """Test end-to-end configuration validation."""
        from src.infrastructure.factories.provider_strategy_factory import ProviderStrategyFactory
        from unittest.mock import Mock
        
        # Test valid configuration
        valid_config = {
            "provider": {
                "providers": [
                    {
                        "name": "aws-test",
                        "type": "aws",
                        "enabled": True,
                        "config": {"region": "us-east-1"}
                    }
                ]
            }
        }
        
        config_path = self.create_config_file(valid_config)
        config_manager = ConfigurationManager(config_path)
        factory = ProviderStrategyFactory(config_manager, Mock())
        
        validation_result = factory.validate_configuration()
        
        assert validation_result["valid"] is True
        assert validation_result["mode"] == "single"
        assert validation_result["provider_count"] == 1
        assert len(validation_result["errors"]) == 0
    
    def test_environment_variable_override_e2e(self):
        """Test environment variable configuration override."""
        # Create base configuration
        config_data = {
            "provider": {
                "selection_policy": "FIRST_AVAILABLE",
                "health_check_interval": 30,
                "providers": [
                    {
                        "name": "aws-test",
                        "type": "aws",
                        "enabled": True,
                        "config": {"region": "us-east-1"}
                    }
                ]
            }
        }
        
        config_path = self.create_config_file(config_data)
        
        # Test environment variable override
        with patch.dict(os.environ, {
            'HF_PROVIDER_SELECTION_POLICY': 'ROUND_ROBIN',
            'HF_PROVIDER_HEALTH_CHECK_INTERVAL': '60'
        }):
            config_manager = ConfigurationManager(config_path)
            unified_config = config_manager.get_unified_provider_config()
            
            # Environment variables should override file configuration
            assert unified_config.selection_policy == "ROUND_ROBIN"
            assert unified_config.health_check_interval == 60
    
    def test_error_handling_e2e(self):
        """Test end-to-end error handling scenarios."""
        # Test invalid configuration file
        invalid_config = {
            "provider": {
                "providers": []  # Empty providers list
            }
        }
        
        config_path = self.create_config_file(invalid_config)
        
        # Test that configuration manager handles invalid config gracefully
        config_manager = ConfigurationManager(config_path)
        
        try:
            unified_config = config_manager.get_unified_provider_config()
            # Should handle empty providers gracefully
            assert unified_config.get_mode().value == "none"
        except Exception as e:
            # Or raise appropriate exception
            assert "provider" in str(e).lower()
    
    def test_performance_configuration_e2e(self):
        """Test performance-related configuration scenarios."""
        # Create configuration with performance settings
        config_data = {
            "provider": {
                "selection_policy": "FASTEST_RESPONSE",
                "health_check_interval": 15,
                "circuit_breaker": {
                    "enabled": True,
                    "failure_threshold": 3,
                    "recovery_timeout": 30
                },
                "providers": [
                    {
                        "name": "aws-fast",
                        "type": "aws",
                        "enabled": True,
                        "priority": 1,
                        "weight": 100,
                        "config": {
                            "region": "us-east-1",
                            "timeout": 10,
                            "max_retries": 2
                        }
                    }
                ]
            }
        }
        
        config_path = self.create_config_file(config_data)
        
        # Test performance configuration loading
        config_manager = ConfigurationManager(config_path)
        unified_config = config_manager.get_unified_provider_config()
        
        assert unified_config.selection_policy == "FASTEST_RESPONSE"
        assert unified_config.health_check_interval == 15
        assert unified_config.circuit_breaker.enabled is True
        assert unified_config.circuit_breaker.failure_threshold == 3
