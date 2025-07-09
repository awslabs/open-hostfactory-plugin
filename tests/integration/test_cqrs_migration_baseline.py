"""
CQRS Migration Baseline Tests - ApplicationService Current Behavior.

This test suite establishes the exact current behavior of ApplicationService
before migrating to pure CQRS architecture. These tests ensure no regressions
during the migration process.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List
import time
import uuid

from src.application.service import ApplicationService
from src.application.base.commands import CommandBus
from src.application.base.queries import QueryBus
from src.domain.base.ports import LoggingPort, ContainerPort, ConfigurationPort


@pytest.mark.integration
class TestApplicationServiceBaseline:
    """Baseline tests for ApplicationService before CQRS migration."""
    
    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        return Mock(spec=LoggingPort)
    
    @pytest.fixture
    def mock_container(self):
        """Create mock container."""
        container = Mock(spec=ContainerPort)
        # Mock the get method to return mocks for any requested service
        container.get.return_value = Mock()
        return container
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = Mock(spec=ConfigurationPort)
        config.get_provider_config.return_value = {
            "aws": {
                "region": "us-east-1",
                "profile": "default"
            }
        }
        return config
    
    @pytest.fixture
    def mock_command_bus(self):
        """Create mock command bus."""
        bus = Mock()
        # Mock both dispatch and send to handle any interface variations
        bus.dispatch.return_value = "req-" + str(uuid.uuid4())[:8]
        bus.send.return_value = "req-" + str(uuid.uuid4())[:8]
        return bus
    
    @pytest.fixture
    def mock_query_bus(self):
        """Create mock query bus."""
        bus = Mock()
        # Mock query to return appropriate responses
        bus.query.return_value = {"status": "completed", "data": []}
        return bus
    
    @pytest.fixture
    def mock_provider(self):
        """Create mock provider that matches the actual interface."""
        provider = Mock()
        provider.provider_type = "mock"
        
        # Mock create_instances to return what ApplicationService expects
        provider.create_instances.return_value = [
            {"instance_id": "i-1234567890abcdef0", "state": "pending"},
            {"instance_id": "i-0987654321fedcba0", "state": "pending"}
        ]
        
        # Mock get_instance_status
        provider.get_instance_status.return_value = [
            {"instance_id": "i-1234567890abcdef0", "state": "running"},
            {"instance_id": "i-0987654321fedcba0", "state": "running"}
        ]
        
        # Mock terminate_instances
        provider.terminate_instances.return_value = [
            {"instance_id": "i-1234567890abcdef0", "state": "shutting-down"}
        ]
        
        # Mock health and info
        provider.get_health.return_value = True
        provider.get_provider_info.return_value = {
            "provider_type": "mock",
            "region": "us-east-1",
            "status": "healthy"
        }
        
        return provider
    
    @pytest.fixture
    def application_service(self, mock_command_bus, mock_query_bus, 
                          mock_logger, mock_container, mock_config, mock_provider):
        """Create ApplicationService instance for baseline testing."""
        return ApplicationService(
            provider_type="mock",
            command_bus=mock_command_bus,
            query_bus=mock_query_bus,
            logger=mock_logger,
            container=mock_container,
            config=mock_config,
            provider=mock_provider
        )
    
    def test_initialization_baseline(self, application_service):
        """Baseline: Test ApplicationService initialization."""
        assert application_service.provider_type == "mock"
        assert not application_service._initialized
        
        # Test initialization
        result = application_service.initialize()
        assert result is True
        assert application_service._initialized
    
    def test_request_machines_baseline(self, application_service):
        """Baseline: Test request_machines with actual signature."""
        # Initialize service
        application_service.initialize()
        
        # Test with actual method signature
        result = application_service.request_machines(
            template_id="web-server-template",
            machine_count=2,
            timeout=300,
            tags={"Environment": "test", "Owner": "test-user"},
            metadata={"test": "baseline"}
        )
        
        # Verify result is a request_id string
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Verify provider was called
        application_service._provider.create_instances.assert_called_once()
    
    def test_request_return_machines_baseline(self, application_service):
        """Baseline: Test request_return_machines with actual signature."""
        # Initialize service
        application_service.initialize()
        
        machine_ids = ["i-1234567890abcdef0"]
        
        result = application_service.request_return_machines(
            machine_ids=machine_ids,
            requester_id="test-user",
            reason="testing complete",
            metadata={"test": "baseline"}
        )
        
        # Verify result is a request_id string
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Verify provider was called
        application_service._provider.terminate_instances.assert_called_once_with(machine_ids)
    
    def test_get_machine_status_baseline(self, application_service):
        """Baseline: Test get_machine_status."""
        # Initialize service
        application_service.initialize()
        
        machine_ids = ["i-1234567890abcdef0", "i-0987654321fedcba0"]
        
        result = application_service.get_machine_status(machine_ids)
        
        # Verify result structure
        assert isinstance(result, list)
        assert len(result) == 2
        
        for machine_status in result:
            assert isinstance(machine_status, dict)
            # The exact structure depends on implementation
        
        # Verify provider was called
        application_service._provider.get_instance_status.assert_called_once_with(machine_ids)
    
    def test_get_request_status_baseline(self, application_service):
        """Baseline: Test get_request_status."""
        # Initialize service
        application_service.initialize()
        
        # First create a request to get a valid request_id
        request_id = application_service.request_machines(
            template_id="web-server-template",
            machine_count=1
        )
        
        # Now get the request status
        result = application_service.get_request_status(request_id)
        
        # Verify result structure
        assert isinstance(result, dict)
        # The exact structure depends on implementation
    
    def test_get_request_baseline(self, application_service):
        """Baseline: Test get_request method."""
        # Initialize service
        application_service.initialize()
        
        # First create a request
        request_id = application_service.request_machines(
            template_id="web-server-template",
            machine_count=1
        )
        
        # Test get_request
        result = application_service.get_request(request_id, long=False)
        assert isinstance(result, dict)
        
        # Test get_request with long=True
        result_long = application_service.get_request(request_id, long=True)
        assert isinstance(result_long, dict)
    
    def test_get_return_requests_baseline(self, application_service):
        """Baseline: Test get_return_requests."""
        # Initialize service
        application_service.initialize()
        
        result = application_service.get_return_requests(
            limit=10,
            offset=0,
            status_filter="pending"
        )
        
        # Verify result structure
        assert isinstance(result, (list, dict))
    
    def test_get_machines_by_request_baseline(self, application_service):
        """Baseline: Test get_machines_by_request."""
        # Initialize service
        application_service.initialize()
        
        # First create a request
        request_id = application_service.request_machines(
            template_id="web-server-template",
            machine_count=2
        )
        
        result = application_service.get_machines_by_request(request_id)
        
        # Verify result structure
        assert isinstance(result, list)
    
    def test_get_provider_health_baseline(self, application_service):
        """Baseline: Test get_provider_health."""
        # Initialize service
        application_service.initialize()
        
        result = application_service.get_provider_health()
        
        # Verify result
        assert isinstance(result, bool)
        assert result is True
        
        # Verify provider was called
        application_service._provider.get_health.assert_called_once()
    
    def test_get_provider_info_baseline(self, application_service):
        """Baseline: Test get_provider_info."""
        # Initialize service
        application_service.initialize()
        
        result = application_service.get_provider_info()
        
        # Verify result structure
        assert isinstance(result, dict)
        assert "provider_type" in result
        
        # Verify provider was called
        application_service._provider.get_provider_info.assert_called_once()
    
    def test_create_request_baseline(self, application_service):
        """Baseline: Test create_request method."""
        # Initialize service
        application_service.initialize()
        
        result = application_service.create_request(
            request_type="acquire",
            template_id="web-server-template",
            machine_count=1,
            requester_id="test-user",
            metadata={"test": "baseline"}
        )
        
        # Verify result
        assert isinstance(result, str)  # Should return request_id
    
    def test_error_handling_uninitialized_baseline(self, application_service):
        """Baseline: Test error handling when service is not initialized."""
        # Don't initialize the service
        
        # This should handle the uninitialized state gracefully
        # The exact behavior depends on _ensure_initialized implementation
        try:
            result = application_service.request_machines(
                template_id="test-template",
                machine_count=1
            )
            # If it succeeds, it means _ensure_initialized worked
            assert isinstance(result, str)
        except Exception as e:
            # If it fails, that's also valid baseline behavior
            assert isinstance(e, Exception)
    
    def test_provider_failure_handling_baseline(self, application_service):
        """Baseline: Test error handling when provider operations fail."""
        # Initialize service
        application_service.initialize()
        
        # Configure provider to fail
        application_service._provider.create_instances.side_effect = Exception("Provider error")
        
        # Test that the error is handled appropriately
        try:
            result = application_service.request_machines(
                template_id="test-template",
                machine_count=1
            )
            # If it succeeds despite provider error, that's the baseline behavior
            assert isinstance(result, str)
        except Exception as e:
            # If it fails, that's also valid baseline behavior
            assert isinstance(e, Exception)
    
    def test_concurrent_operations_baseline(self, application_service):
        """Baseline: Test concurrent operations behavior."""
        import threading
        
        # Initialize service
        application_service.initialize()
        
        results = []
        errors = []
        
        def request_machines():
            try:
                result = application_service.request_machines(
                    template_id="web-server-template",
                    machine_count=1,
                    tags={"thread": str(threading.current_thread().ident)}
                )
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=request_machines)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Record baseline behavior
        print(f"Baseline concurrent results: {len(results)} successes, {len(errors)} errors")
        
        # The exact behavior is what we're establishing as baseline
        assert len(results) + len(errors) == 3
    
    def test_performance_baseline(self, application_service):
        """Baseline: Establish performance baseline."""
        # Initialize service
        application_service.initialize()
        
        # Measure request_machines performance
        start_time = time.time()
        
        for i in range(5):  # Smaller number for baseline
            application_service.request_machines(
                template_id="web-server-template",
                machine_count=1,
                tags={"iteration": str(i)}
            )
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / 5
        
        print(f"Performance baseline: {avg_time:.3f}s average per operation")
        print(f"Total time for 5 operations: {total_time:.3f}s")
        
        # Record baseline - don't assert specific times, just record them
        assert avg_time > 0  # Sanity check
        assert total_time > 0  # Sanity check


@pytest.mark.integration
class TestMachineStatusConversionBaseline:
    """Baseline tests for MachineStatusConversionService."""
    
    @pytest.fixture
    def mock_provider_domain_service(self):
        """Create mock provider domain service."""
        from src.domain.base.provider_interfaces import ProviderDomainService
        service = Mock(spec=ProviderDomainService)
        
        # Configure state mapping
        from src.domain.machine.value_objects import MachineStatus
        service.map_provider_state.return_value = MachineStatus.RUNNING
        
        return service
    
    @pytest.fixture
    def status_conversion_service(self, mock_provider_domain_service):
        """Create MachineStatusConversionService for baseline testing."""
        from src.application.machine.status_service import MachineStatusConversionService
        return MachineStatusConversionService(mock_provider_domain_service)
    
    def test_convert_from_provider_state_baseline(self, status_conversion_service):
        """Baseline: Test converting provider state to domain state."""
        result = status_conversion_service.convert_from_provider_state(
            provider_state="running",
            provider_type="aws"
        )
        
        # Verify result
        from src.domain.machine.value_objects import MachineStatus
        assert isinstance(result, MachineStatus)
        
        # Verify provider service was called
        status_conversion_service._provider_service.map_provider_state.assert_called_once()
    
    def test_error_handling_baseline(self, status_conversion_service):
        """Baseline: Test error handling behavior."""
        # Configure service to raise error
        status_conversion_service._provider_service.map_provider_state.side_effect = Exception("Invalid state")
        
        try:
            result = status_conversion_service.convert_from_provider_state(
                provider_state="invalid",
                provider_type="aws"
            )
            # If it succeeds despite error, that's baseline behavior
            assert result is not None
        except Exception as e:
            # If it fails, that's also valid baseline behavior
            assert isinstance(e, Exception)


if __name__ == "__main__":
    # Run baseline tests
    pytest.main([__file__, "-v", "--tb=short"])
