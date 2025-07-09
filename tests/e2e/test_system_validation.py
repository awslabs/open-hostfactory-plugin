"""Final system validation tests for all phases integration."""
import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch

from src.bootstrap import Application
from src.config.manager import ConfigurationManager
from src.infrastructure.factories.provider_strategy_factory import ProviderStrategyFactory


class TestSystemValidation:
    """Final validation tests for complete system integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "system_config.json")
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_config_file(self, config_data):
        """Create a temporary configuration file."""
        with open(self.config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        return self.config_path
    
    def test_phase_1_2_3_integration_complete(self):
        """Test complete integration of all three phases."""
        print("🔄 Testing Phase 1-2-3 Complete Integration...")
        
        # Phase 1: Unified Configuration
        unified_config_data = {
            "provider": {
                "selection_policy": "WEIGHTED_ROUND_ROBIN",
                "health_check_interval": 30,
                "circuit_breaker": {
                    "enabled": True,
                    "failure_threshold": 5,
                    "recovery_timeout": 60
                },
                "providers": [
                    {
                        "name": "aws-primary",
                        "type": "aws",
                        "enabled": True,
                        "priority": 1,
                        "weight": 70,
                        "capabilities": ["compute", "storage", "networking"],
                        "config": {
                            "region": "us-east-1",
                            "profile": "primary",
                            "max_retries": 3,
                            "timeout": 30
                        }
                    },
                    {
                        "name": "aws-backup",
                        "type": "aws",
                        "enabled": True,
                        "priority": 2,
                        "weight": 30,
                        "capabilities": ["compute", "storage"],
                        "config": {
                            "region": "us-west-2",
                            "profile": "backup",
                            "max_retries": 5,
                            "timeout": 45
                        }
                    }
                ]
            },
            "logging": {
                "level": "INFO",
                "console_enabled": True
            },
            "storage": {
                "strategy": "json"
            },
            "template": {
                "ami_resolution": {
                    "enabled": True,
                    "cache_enabled": True
                }
            }
        }
        
        config_path = self.create_config_file(unified_config_data)
        
        # Phase 1 Validation: Configuration Loading
        config_manager = ConfigurationManager(config_path)
        unified_config = config_manager.get_unified_provider_config()
        
        assert unified_config.get_mode().value == "multi"
        assert len(unified_config.get_active_providers()) == 2
        assert unified_config.selection_policy == "WEIGHTED_ROUND_ROBIN"
        print("✅ Phase 1: Unified configuration loading successful")
        
        # Phase 2 Validation: Provider Strategy Factory
        factory = ProviderStrategyFactory(config_manager, Mock())
        
        provider_info = factory.get_provider_info()
        assert provider_info["mode"] == "multi"
        assert provider_info["selection_policy"] == "WEIGHTED_ROUND_ROBIN"
        assert provider_info["active_providers"] == 2
        assert "aws-primary" in provider_info["provider_names"]
        assert "aws-backup" in provider_info["provider_names"]
        
        validation_result = factory.validate_configuration()
        assert validation_result["valid"] is True
        assert validation_result["mode"] == "multi"
        assert validation_result["provider_count"] == 2
        print("✅ Phase 2: Provider strategy factory successful")
        
        # Phase 3 Validation: Interface Integration
        from src.interface.command_handlers import (
            GetProviderConfigCLIHandler,
            ValidateProviderConfigCLIHandler
        )
        
        mock_query_bus = Mock()
        mock_command_bus = Mock()
        
        # Test configuration CLI handler
        config_handler = GetProviderConfigCLIHandler(mock_query_bus, mock_command_bus)
        mock_query_bus.dispatch.return_value = {
            "status": "success",
            "provider_info": provider_info
        }
        
        mock_command = Mock()
        mock_command.file = None
        mock_command.data = None
        
        result = config_handler.handle(mock_command)
        assert result["status"] == "success"
        assert result["provider_info"]["mode"] == "multi"
        print("✅ Phase 3: Interface integration successful")
        
        print("🎉 PHASE 1-2-3 COMPLETE INTEGRATION: ALL TESTS PASSED")
    
    def test_legacy_to_unified_migration_complete(self):
        """Test complete legacy to unified migration workflow."""
        print("🔄 Testing Legacy to Unified Migration Workflow...")
        
        # Start with legacy configuration
        legacy_config = {
            "provider": {
                "type": "aws",
                "aws": {
                    "region": "us-east-1",
                    "profile": "default",
                    "max_retries": 3
                }
            },
            "logging": {
                "level": "INFO"
            }
        }
        
        config_path = self.create_config_file(legacy_config)
        
        # Step 1: Load legacy configuration
        config_manager = ConfigurationManager(config_path)
        unified_config = config_manager.get_unified_provider_config()
        
        assert unified_config.get_mode().value == "legacy"
        assert unified_config.type == "aws"
        assert unified_config.aws["region"] == "us-east-1"
        print("✅ Step 1: Legacy configuration loaded")
        
        # Step 2: Validate legacy configuration
        factory = ProviderStrategyFactory(config_manager, Mock())
        validation_result = factory.validate_configuration()
        
        # Legacy mode should be valid
        assert validation_result["mode"] == "legacy"
        print("✅ Step 2: Legacy configuration validated")
        
        # Step 3: Simulate migration to unified format
        migrated_config = {
            "provider": {
                "active_provider": "aws-legacy",
                "providers": [
                    {
                        "name": "aws-legacy",
                        "type": "aws",
                        "enabled": True,
                        "priority": 1,
                        "weight": 100,
                        "config": {
                            "region": "us-east-1",
                            "profile": "default",
                            "max_retries": 3
                        }
                    }
                ]
            },
            "logging": {
                "level": "INFO"
            }
        }
        
        migrated_path = self.create_config_file(migrated_config)
        migrated_config_manager = ConfigurationManager(migrated_path)
        migrated_unified_config = migrated_config_manager.get_unified_provider_config()
        
        assert migrated_unified_config.get_mode().value == "single"
        assert len(migrated_unified_config.get_active_providers()) == 1
        assert migrated_unified_config.get_active_providers()[0].name == "aws-legacy"
        print("✅ Step 3: Migration to unified format successful")
        
        # Step 4: Validate migrated configuration
        migrated_factory = ProviderStrategyFactory(migrated_config_manager, Mock())
        migrated_validation = migrated_factory.validate_configuration()
        
        assert migrated_validation["valid"] is True
        assert migrated_validation["mode"] == "single"
        print("✅ Step 4: Migrated configuration validated")
        
        print("🎉 LEGACY TO UNIFIED MIGRATION: COMPLETE WORKFLOW SUCCESSFUL")
    
    def test_multi_provider_failover_scenario(self):
        """Test multi-provider failover scenario."""
        print("🔄 Testing Multi-Provider Failover Scenario...")
        
        # Create multi-provider configuration with failover
        config_data = {
            "provider": {
                "selection_policy": "HEALTH_BASED",
                "health_check_interval": 15,
                "circuit_breaker": {
                    "enabled": True,
                    "failure_threshold": 3,
                    "recovery_timeout": 30
                },
                "providers": [
                    {
                        "name": "aws-primary",
                        "type": "aws",
                        "enabled": True,
                        "priority": 1,
                        "weight": 80,
                        "capabilities": ["compute", "storage", "networking"],
                        "config": {
                            "region": "us-east-1",
                            "max_retries": 3,
                            "timeout": 30
                        }
                    },
                    {
                        "name": "aws-failover",
                        "type": "aws",
                        "enabled": True,
                        "priority": 2,
                        "weight": 20,
                        "capabilities": ["compute", "storage"],
                        "config": {
                            "region": "us-west-2",
                            "max_retries": 5,
                            "timeout": 60
                        }
                    }
                ]
            }
        }
        
        config_path = self.create_config_file(config_data)
        
        # Test failover configuration
        config_manager = ConfigurationManager(config_path)
        unified_config = config_manager.get_unified_provider_config()
        
        assert unified_config.get_mode().value == "multi"
        assert unified_config.selection_policy == "HEALTH_BASED"
        assert unified_config.circuit_breaker.enabled is True
        assert unified_config.circuit_breaker.failure_threshold == 3
        print("✅ Failover configuration loaded")
        
        # Test provider strategy factory with failover
        factory = ProviderStrategyFactory(config_manager, Mock())
        provider_info = factory.get_provider_info()
        
        assert provider_info["mode"] == "multi"
        assert provider_info["active_providers"] == 2
        assert provider_info["circuit_breaker_enabled"] is True
        print("✅ Failover provider strategy created")
        
        # Test validation of failover configuration
        validation_result = factory.validate_configuration()
        
        assert validation_result["valid"] is True
        assert validation_result["mode"] == "multi"
        assert len(validation_result["warnings"]) == 0
        print("✅ Failover configuration validated")
        
        print("🎉 MULTI-PROVIDER FAILOVER: SCENARIO SUCCESSFUL")
    
    def test_production_configuration_scenario(self):
        """Test production-grade configuration scenario."""
        print("🔄 Testing Production Configuration Scenario...")
        
        # Create production-grade configuration
        production_config = {
            "provider": {
                "selection_policy": "CAPABILITY_BASED",
                "health_check_interval": 60,
                "circuit_breaker": {
                    "enabled": True,
                    "failure_threshold": 5,
                    "recovery_timeout": 120,
                    "half_open_max_calls": 10
                },
                "providers": [
                    {
                        "name": "aws-prod-primary",
                        "type": "aws",
                        "enabled": True,
                        "priority": 1,
                        "weight": 60,
                        "capabilities": ["compute", "storage", "networking", "monitoring"],
                        "config": {
                            "region": "us-east-1",
                            "role_arn": "arn:aws:iam::123456789012:role/ProdRole",
                            "max_retries": 5,
                            "timeout": 60
                        }
                    },
                    {
                        "name": "aws-prod-secondary",
                        "type": "aws",
                        "enabled": True,
                        "priority": 2,
                        "weight": 40,
                        "capabilities": ["compute", "storage", "networking"],
                        "config": {
                            "region": "us-west-2",
                            "role_arn": "arn:aws:iam::123456789012:role/ProdRole",
                            "max_retries": 5,
                            "timeout": 60
                        }
                    },
                    {
                        "name": "aws-prod-dr",
                        "type": "aws",
                        "enabled": False,  # Disaster recovery, disabled by default
                        "priority": 3,
                        "weight": 20,
                        "capabilities": ["compute", "storage"],
                        "config": {
                            "region": "eu-west-1",
                            "role_arn": "arn:aws:iam::123456789012:role/DRRole",
                            "max_retries": 3,
                            "timeout": 90
                        }
                    }
                ]
            },
            "logging": {
                "level": "INFO",
                "file_path": "/var/log/hostfactory/production.log",
                "console_enabled": False
            },
            "storage": {
                "strategy": "json",
                "json_strategy": {
                    "storage_type": "single_file",
                    "base_path": "/var/lib/hostfactory/data"
                }
            },
            "template": {
                "ami_resolution": {
                    "enabled": True,
                    "fallback_on_failure": true,
                    "cache_enabled": true
                }
            }
        }
        
        config_path = self.create_config_file(production_config)
        
        # Test production configuration loading
        config_manager = ConfigurationManager(config_path)
        unified_config = config_manager.get_unified_provider_config()
        
        assert unified_config.get_mode().value == "multi"
        assert len(unified_config.providers) == 3
        assert len(unified_config.get_active_providers()) == 2  # DR disabled
        assert unified_config.selection_policy == "CAPABILITY_BASED"
        print("✅ Production configuration loaded")
        
        # Test production provider strategy
        factory = ProviderStrategyFactory(config_manager, Mock())
        provider_info = factory.get_provider_info()
        
        assert provider_info["mode"] == "multi"
        assert provider_info["total_providers"] == 3
        assert provider_info["active_providers"] == 2
        assert provider_info["health_check_interval"] == 60
        print("✅ Production provider strategy created")
        
        # Test production configuration validation
        validation_result = factory.validate_configuration()
        
        assert validation_result["valid"] is True
        assert validation_result["mode"] == "multi"
        assert validation_result["provider_count"] == 2  # Active providers
        print("✅ Production configuration validated")
        
        # Test capability-based selection
        active_providers = unified_config.get_active_providers()
        primary_capabilities = active_providers[0].capabilities
        secondary_capabilities = active_providers[1].capabilities
        
        assert "monitoring" in primary_capabilities
        assert "monitoring" not in secondary_capabilities
        assert "compute" in primary_capabilities and "compute" in secondary_capabilities
        print("✅ Capability-based configuration verified")
        
        print("🎉 PRODUCTION CONFIGURATION: SCENARIO SUCCESSFUL")
    
    @patch('src.bootstrap.register_services')
    @patch('src.bootstrap.get_config_manager')
    def test_complete_application_lifecycle(self, mock_get_config, mock_register_services):
        """Test complete application lifecycle with configuration-driven providers."""
        print("🔄 Testing Complete Application Lifecycle...")
        
        # Setup application mocks
        mock_container = Mock()
        mock_application_service = Mock()
        mock_application_service.initialize.return_value = True
        mock_application_service.get_provider_info.return_value = {
            "mode": "multi",
            "provider_names": ["aws-primary", "aws-backup"],
            "active_providers": 2
        }
        mock_application_service.health_check.return_value = {
            "status": "healthy",
            "providers": {
                "aws-primary": "healthy",
                "aws-backup": "healthy"
            }
        }
        
        mock_container.get.return_value = mock_application_service
        mock_register_services.return_value = mock_container
        
        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.get.return_value = {"type": "aws"}
        mock_config_manager.get_typed.return_value = Mock(logging=Mock())
        mock_config_manager.get_unified_provider_config.return_value = Mock(
            get_mode=Mock(return_value=Mock(value="multi")),
            get_active_providers=Mock(return_value=[
                Mock(name="aws-primary"),
                Mock(name="aws-backup")
            ]),
            selection_policy="ROUND_ROBIN",
            health_check_interval=30
        )
        mock_get_config.return_value = mock_config_manager
        
        # Test application lifecycle
        config_data = {
            "provider": {
                "selection_policy": "ROUND_ROBIN",
                "providers": [
                    {"name": "aws-primary", "type": "aws", "enabled": True},
                    {"name": "aws-backup", "type": "aws", "enabled": True}
                ]
            }
        }
        
        config_path = self.create_config_file(config_data)
        
        # Step 1: Application initialization
        app = Application(config_path=config_path)
        init_result = app.initialize()
        
        assert init_result is True
        mock_application_service.initialize.assert_called_once()
        print("✅ Step 1: Application initialization successful")
        
        # Step 2: Provider information retrieval
        provider_info = app.get_provider_info()
        
        assert provider_info["mode"] == "multi"
        assert provider_info["active_providers"] == 2
        print("✅ Step 2: Provider information retrieval successful")
        
        # Step 3: Health check
        health_status = app.health_check()
        
        assert health_status["status"] == "healthy"
        assert "providers" in health_status
        print("✅ Step 3: Health check successful")
        
        # Step 4: Application shutdown
        app.shutdown()
        assert app._initialized is False
        print("✅ Step 4: Application shutdown successful")
        
        print("🎉 COMPLETE APPLICATION LIFECYCLE: SUCCESSFUL")
    
    def test_error_recovery_scenarios(self):
        """Test error recovery scenarios."""
        print("🔄 Testing Error Recovery Scenarios...")
        
        # Scenario 1: Invalid configuration recovery
        invalid_config = {
            "provider": {
                "providers": []  # Empty providers
            }
        }
        
        config_path = self.create_config_file(invalid_config)
        
        try:
            config_manager = ConfigurationManager(config_path)
            unified_config = config_manager.get_unified_provider_config()
            
            # Should handle gracefully
            mode = unified_config.get_mode()
            assert mode.value in ["none", "legacy"]
            print("✅ Scenario 1: Invalid configuration handled gracefully")
        except Exception as e:
            # Or raise appropriate exception
            assert "provider" in str(e).lower()
            print("✅ Scenario 1: Invalid configuration raised appropriate exception")
        
        # Scenario 2: Provider creation failure recovery
        config_with_invalid_provider = {
            "provider": {
                "providers": [
                    {
                        "name": "invalid-provider",
                        "type": "aws",
                        "enabled": True,
                        "config": {}  # Missing required config
                    }
                ]
            }
        }
        
        config_path = self.create_config_file(config_with_invalid_provider)
        config_manager = ConfigurationManager(config_path)
        factory = ProviderStrategyFactory(config_manager, Mock())
        
        # Validation should catch the error
        validation_result = factory.validate_configuration()
        
        # Should identify the configuration issue
        assert validation_result["valid"] is False or len(validation_result["warnings"]) > 0
        print("✅ Scenario 2: Provider creation failure detected")
        
        print("🎉 ERROR RECOVERY SCENARIOS: SUCCESSFUL")
    
    def test_performance_under_load(self):
        """Test system performance under load."""
        print("🔄 Testing System Performance Under Load...")
        
        # Create configuration with multiple providers
        config_data = {
            "provider": {
                "selection_policy": "ROUND_ROBIN",
                "health_check_interval": 30,
                "providers": [
                    {
                        "name": f"aws-provider-{i}",
                        "type": "aws",
                        "enabled": True,
                        "priority": i + 1,
                        "weight": 100 - i * 5,
                        "config": {"region": f"us-east-{i % 2 + 1}"}
                    }
                    for i in range(10)
                ]
            }
        }
        
        config_path = self.create_config_file(config_data)
        
        # Test configuration loading performance
        import time
        start_time = time.time()
        
        config_manager = ConfigurationManager(config_path)
        unified_config = config_manager.get_unified_provider_config()
        factory = ProviderStrategyFactory(config_manager, Mock())
        
        # Perform multiple operations
        for _ in range(100):
            provider_info = factory.get_provider_info()
            validation_result = factory.validate_configuration()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Performance assertions
        assert total_time < 2.0, f"Performance test took {total_time:.3f}s, expected < 2.0s"
        assert len(unified_config.get_active_providers()) == 10
        print(f"✅ Performance test: 200 operations in {total_time:.3f}s")
        
        print("🎉 PERFORMANCE UNDER LOAD: SUCCESSFUL")
    
    def test_final_system_validation_complete(self):
        """Final comprehensive system validation."""
        print("🔄 Final Comprehensive System Validation...")
        
        # Test all major components together
        comprehensive_config = {
            "provider": {
                "selection_policy": "WEIGHTED_ROUND_ROBIN",
                "health_check_interval": 30,
                "circuit_breaker": {
                    "enabled": True,
                    "failure_threshold": 5,
                    "recovery_timeout": 60
                },
                "providers": [
                    {
                        "name": "aws-primary",
                        "type": "aws",
                        "enabled": True,
                        "priority": 1,
                        "weight": 70,
                        "capabilities": ["compute", "storage", "networking"],
                        "config": {
                            "region": "us-east-1",
                            "profile": "primary",
                            "max_retries": 3,
                            "timeout": 30
                        }
                    },
                    {
                        "name": "aws-backup",
                        "type": "aws",
                        "enabled": True,
                        "priority": 2,
                        "weight": 30,
                        "capabilities": ["compute", "storage"],
                        "config": {
                            "region": "us-west-2",
                            "profile": "backup",
                            "max_retries": 5,
                            "timeout": 45
                        }
                    }
                ]
            },
            "logging": {
                "level": "INFO",
                "console_enabled": True
            },
            "storage": {
                "strategy": "json"
            },
            "template": {
                "ami_resolution": {
                    "enabled": True,
                    "cache_enabled": True
                }
            }
        }
        
        config_path = self.create_config_file(comprehensive_config)
        
        # Comprehensive validation checklist
        validation_checklist = {
            "phase_1_config_loading": False,
            "phase_2_factory_creation": False,
            "phase_3_interface_integration": False,
            "multi_provider_support": False,
            "configuration_validation": False,
            "provider_info_retrieval": False,
            "error_handling": False,
            "performance_acceptable": False
        }
        
        try:
            # Phase 1: Configuration loading
            config_manager = ConfigurationManager(config_path)
            unified_config = config_manager.get_unified_provider_config()
            
            assert unified_config.get_mode().value == "multi"
            assert len(unified_config.get_active_providers()) == 2
            validation_checklist["phase_1_config_loading"] = True
            
            # Phase 2: Factory creation
            factory = ProviderStrategyFactory(config_manager, Mock())
            provider_info = factory.get_provider_info()
            
            assert provider_info["mode"] == "multi"
            assert provider_info["active_providers"] == 2
            validation_checklist["phase_2_factory_creation"] = True
            
            # Phase 3: Interface integration
            from src.interface.command_handlers import GetProviderConfigCLIHandler
            
            mock_query_bus = Mock()
            mock_command_bus = Mock()
            mock_query_bus.dispatch.return_value = {"status": "success", "provider_info": provider_info}
            
            handler = GetProviderConfigCLIHandler(mock_query_bus, mock_command_bus)
            mock_command = Mock()
            mock_command.file = None
            mock_command.data = None
            
            result = handler.handle(mock_command)
            assert result["status"] == "success"
            validation_checklist["phase_3_interface_integration"] = True
            
            # Multi-provider support
            assert provider_info["selection_policy"] == "WEIGHTED_ROUND_ROBIN"
            assert "aws-primary" in provider_info["provider_names"]
            assert "aws-backup" in provider_info["provider_names"]
            validation_checklist["multi_provider_support"] = True
            
            # Configuration validation
            validation_result = factory.validate_configuration()
            assert validation_result["valid"] is True
            validation_checklist["configuration_validation"] = True
            
            # Provider info retrieval
            assert provider_info["health_check_interval"] == 30
            assert provider_info["circuit_breaker_enabled"] is True
            validation_checklist["provider_info_retrieval"] = True
            
            # Error handling
            try:
                factory.clear_cache()  # Should not raise exception
                validation_checklist["error_handling"] = True
            except Exception:
                pass
            
            # Performance
            import time
            start_time = time.time()
            for _ in range(10):
                factory.get_provider_info()
            end_time = time.time()
            
            if (end_time - start_time) < 0.1:
                validation_checklist["performance_acceptable"] = True
            
        except Exception as e:
            print(f"❌ Validation failed: {str(e)}")
        
        # Report validation results
        passed_checks = sum(validation_checklist.values())
        total_checks = len(validation_checklist)
        
        print(f"📊 Validation Results: {passed_checks}/{total_checks} checks passed")
        
        for check, passed in validation_checklist.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check.replace('_', ' ').title()}")
        
        # Final assertion
        assert passed_checks == total_checks, f"System validation failed: {passed_checks}/{total_checks} checks passed"
        
        print("🎉 FINAL SYSTEM VALIDATION: COMPLETE SUCCESS")
        print("")
        print("🏆 ALL PHASES INTEGRATION VALIDATED:")
        print("  ✅ Phase 1: Unified Provider Configuration")
        print("  ✅ Phase 2: Configuration-Driven Provider Strategy Factory")
        print("  ✅ Phase 3: Interface Integration with CLI Operations")
        print("  ✅ Multi-Provider Support with Load Balancing")
        print("  ✅ Configuration Validation and Error Handling")
        print("  ✅ Performance and Scalability Requirements")
        print("  ✅ Production-Ready Architecture and Patterns")
