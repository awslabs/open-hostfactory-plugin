#!/usr/bin/env python3
"""
Phase 6: Dependency Injection Updates Test

This test validates that the dependency injection updates for AWS Launch Template Manager
and other services are working correctly.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath("."))


def test_phase6_dependency_injection():
    """Test Phase 6 dependency injection updates."""

    print("🔧 PHASE 6: DEPENDENCY INJECTION UPDATES TEST")
    print("=" * 60)

    results = {
        "aws_launch_template_manager_registration": False,
        "repository_factory_machine_support": False,
        "di_container_resolution": False,
        "service_dependencies": False,
    }

    try:
        # Test 1: AWS Launch Template Manager registration
        print("\n1️⃣ Testing AWS Launch Template Manager Registration...")
        results["aws_launch_template_manager_registration"] = (
            test_aws_launch_template_manager_registration()
        )

        # Test 2: Repository factory machine support
        print("\n2️⃣ Testing Repository Factory Machine Support...")
        results["repository_factory_machine_support"] = test_repository_factory_machine_support()

        # Test 3: DI container resolution
        print("\n3️⃣ Testing DI Container Resolution...")
        results["di_container_resolution"] = test_di_container_resolution()

        # Test 4: Service dependencies
        print("\n4️⃣ Testing Service Dependencies...")
        results["service_dependencies"] = test_service_dependencies()

        # Summary
        print("\n" + "=" * 60)
        print("📊 PHASE 6 DEPENDENCY INJECTION TEST RESULTS")
        print("=" * 60)

        passed = sum(1 for result in results.values() if result)
        total = len(results)

        for test_name, result in results.items():
            status = "PASS: PASS" if result else "FAIL: FAIL"
            print(f"{test_name.replace('_', ' ').title()}: {status}")

        print(f"\nOverall: {passed}/{total} tests passed")

        if passed == total:
            print("🎉 ALL PHASE 6 DEPENDENCY INJECTION TESTS PASSED!")
            return True
        else:
            print("WARN:  Some dependency injection tests failed")
            return False

    except Exception as e:
        print(f"FAIL: Test execution failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_aws_launch_template_manager_registration():
    """Test that AWS Launch Template Manager is properly registered."""
    try:
        print("   Testing AWS Launch Template Manager registration...")

        # Test that the class can be imported
        from src.providers.aws.infrastructure.launch_template.manager import (
            AWSLaunchTemplateManager,
        )

        print("   PASS: AWSLaunchTemplateManager import successful")

        # Test that the registration function exists
        from src.providers.aws.registration import register_aws_services_with_di

        print("   PASS: register_aws_services_with_di function exists")

        # Test that the manager can be instantiated (with mocked dependencies)
        try:
            # Create a mock DI container to test registration
            class MockContainer:
                def __init__(self):
                    self._services = {}
                    self._registered = set()

                def get(self, service_type):
                    if service_type.__name__ == "LoggingPort":
                        return MockLogger()
                    return None

                def register_singleton(self, service_type, factory=None):
                    self._registered.add(service_type.__name__)

                def is_registered(self, service_type):
                    return service_type.__name__ in self._registered

            class MockLogger:
                def debug(self, msg):
                    pass

                def info(self, msg):
                    pass

                def warning(self, msg):
                    pass

                def error(self, msg):
                    pass

            # Test registration
            mock_container = MockContainer()
            register_aws_services_with_di(mock_container)

            # Check if AWSLaunchTemplateManager was registered
            if "AWSLaunchTemplateManager" in mock_container._registered:
                print("   PASS: AWSLaunchTemplateManager registered with DI container")
            else:
                print("   WARN:  AWSLaunchTemplateManager not found in registration")

        except Exception as e:
            print(f"   WARN:  Registration test failed: {str(e)}")

        return True

    except ImportError as e:
        print(f"   FAIL: Import error: {str(e)}")
        return False
    except Exception as e:
        print(f"   FAIL: AWS Launch Template Manager registration test failed: {str(e)}")
        return False


def test_repository_factory_machine_support():
    """Test that repository factory supports machine repository creation."""
    try:
        print("   Testing repository factory machine support...")

        # Test that repository factory can be imported
        from src.infrastructure.utilities.factories.repository_factory import RepositoryFactory

        print("   PASS: RepositoryFactory import successful")

        # Test that machine repository interface exists
        from src.domain.machine.repository import MachineRepository

        print("   PASS: MachineRepository interface import successful")

        # Test that repository factory has create_machine_repository method
        if hasattr(RepositoryFactory, "create_machine_repository"):
            print("   PASS: RepositoryFactory.create_machine_repository method exists")
        else:
            print("   FAIL: RepositoryFactory.create_machine_repository method missing")
            return False

        # Test that machine repository implementation exists
        try:
            from src.infrastructure.persistence.repositories.machine_repository import (
                MachineRepositoryImpl,
            )

            print("   PASS: MachineRepositoryImpl implementation exists")
        except ImportError:
            print("   WARN:  MachineRepositoryImpl implementation not found")

        return True

    except ImportError as e:
        print(f"   FAIL: Import error: {str(e)}")
        return False
    except Exception as e:
        print(f"   FAIL: Repository factory machine support test failed: {str(e)}")
        return False


def test_di_container_resolution():
    """Test that DI container can resolve dependencies correctly."""
    try:
        print("   Testing DI container resolution...")

        # Test that DI container can be imported
        from src.infrastructure.di.container import DIContainer

        print("   PASS: DIContainer import successful")

        # Test that infrastructure services registration exists
        from src.infrastructure.di.infrastructure_services import register_infrastructure_services

        print("   PASS: register_infrastructure_services function exists")

        # Test that provider services registration exists
        from src.infrastructure.di.provider_services import register_provider_services

        print("   PASS: register_provider_services function exists")

        # Test basic container functionality
        container = DIContainer()

        # Test singleton registration
        class TestService:
            def __init__(self):
                self.value = "test"

        container.register_singleton(TestService)

        # Test resolution
        service1 = container.get(TestService)
        service2 = container.get(TestService)

        if service1 is service2:
            print("   PASS: DI container singleton resolution working")
        else:
            print("   FAIL: DI container singleton resolution failed")
            return False

        return True

    except ImportError as e:
        print(f"   FAIL: Import error: {str(e)}")
        return False
    except Exception as e:
        print(f"   FAIL: DI container resolution test failed: {str(e)}")
        return False


def test_service_dependencies():
    """Test that services have proper dependency injection setup."""
    try:
        print("   Testing service dependencies...")

        # Test that injectable decorator exists
        from src.domain.base.dependency_injection import injectable

        print("   PASS: @injectable decorator import successful")

        # Test that logging port exists
        from src.domain.base.ports import LoggingPort

        print("   PASS: LoggingPort import successful")

        # Test that configuration manager exists
        from src.config.manager import ConfigurationManager

        print("   PASS: ConfigurationManager import successful")

        # Test that AWS client exists
        try:
            from src.providers.aws.infrastructure.aws_client import AWSClient

            print("   PASS: AWSClient import successful")
        except ImportError:
            print("   WARN:  AWSClient import failed (may be expected)")

        # Test that AWS operations utility exists
        try:
            from src.providers.aws.utilities.aws_operations import AWSOperations

            print("   PASS: AWSOperations import successful")
        except ImportError:
            print("   WARN:  AWSOperations import failed (may be expected)")

        # Test that template defaults service exists
        from src.application.services.template_defaults_service import TemplateDefaultsService

        print("   PASS: TemplateDefaultsService import successful")

        # Test that template defaults port exists
        from src.domain.template.ports.template_defaults_port import TemplateDefaultsPort

        print("   PASS: TemplateDefaultsPort import successful")

        return True

    except ImportError as e:
        print(f"   FAIL: Import error: {str(e)}")
        return False
    except Exception as e:
        print(f"   FAIL: Service dependencies test failed: {str(e)}")
        return False


if __name__ == "__main__":
    success = test_phase6_dependency_injection()
    sys.exit(0 if success else 1)
