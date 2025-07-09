"""Unit tests for AMI resolution functionality.

NOTE: This test file is disabled because the AMI resolution modules
have been moved to backup/ as they are no longer part of the active
architecture. The functionality has been replaced by the new template
format service integration.

If AMI resolution is needed in the future, these tests can be re-enabled
and updated to work with the new architecture.
"""
import pytest

# Skip all tests in this file
pytestmark = pytest.mark.skip(reason="AMI resolution modules moved to backup - functionality replaced by template format service")

# Original test content preserved but disabled
"""
from unittest.mock import Mock, patch
from src.infrastructure.template.ami_cache import RuntimeAMICache
from src.infrastructure.template.caching_ami_resolver import CachingAMIResolver
from src.infrastructure.template.resolving_configuration_manager import ResolvingTemplateConfigurationManager
from src.config.schemas.app_schema import AMIResolutionConfig
from src.domain.base.exceptions import InfrastructureError
"""


class TestRuntimeAMICache:
    """Test RuntimeAMICache functionality."""
    
    def test_empty_cache(self):
        """Test empty cache behavior."""
        cache = RuntimeAMICache()
        
        assert cache.get("/aws/service/test") is None
        assert not cache.is_failed("/aws/service/test")
        
        stats = cache.get_stats()
        assert stats['cached_entries'] == 0
        assert stats['failed_entries'] == 0
        assert stats['total_entries'] == 0
    
    def test_cache_set_get(self):
        """Test cache set and get operations."""
        cache = RuntimeAMICache()
        
        ssm_param = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64"
        ami_id = "ami-12345678"
        
        cache.set(ssm_param, ami_id)
        assert cache.get(ssm_param) == ami_id
        
        stats = cache.get_stats()
        assert stats['cached_entries'] == 1
        assert stats['failed_entries'] == 0
    
    def test_failed_marking(self):
        """Test failure marking functionality."""
        cache = RuntimeAMICache()
        
        failed_param = "/aws/service/nonexistent"
        cache.mark_failed(failed_param)
        
        assert cache.is_failed(failed_param)
        assert cache.get(failed_param) is None
        
        stats = cache.get_stats()
        assert stats['cached_entries'] == 0
        assert stats['failed_entries'] == 1
    
    def test_clear_cache(self):
        """Test cache clearing."""
        cache = RuntimeAMICache()
        
        cache.set("/aws/service/test1", "ami-111")
        cache.set("/aws/service/test2", "ami-222")
        cache.mark_failed("/aws/service/failed")
        
        assert cache.get_stats()['total_entries'] == 3
        
        cache.clear()
        
        stats = cache.get_stats()
        assert stats['total_entries'] == 0
        assert cache.get("/aws/service/test1") is None
        assert not cache.is_failed("/aws/service/failed")


class TestCachingAMIResolver:
    """Test CachingAMIResolver functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_aws_client = Mock()
        self.config = AMIResolutionConfig(
            enabled=True,
            fallback_on_failure=True,
            cache_enabled=True
        )
        self.resolver = CachingAMIResolver(
            aws_client=self.mock_aws_client,
            config=self.config
        )
    
    def test_resolution_disabled(self):
        """Test behavior when resolution is disabled."""
        config = AMIResolutionConfig(enabled=False)
        resolver = CachingAMIResolver(self.mock_aws_client, config)
        
        ssm_param = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64"
        result = resolver.resolve_with_fallback(ssm_param)
        
        assert result == ssm_param
        assert not self.mock_aws_client.ssm_client.get_parameter.called
    
    def test_ami_id_passthrough(self):
        """Test that existing AMI IDs are passed through unchanged."""
        ami_id = "ami-12345678"
        result = self.resolver.resolve_with_fallback(ami_id)
        
        assert result == ami_id
        assert not self.mock_aws_client.ssm_client.get_parameter.called
    
    def test_successful_resolution(self):
        """Test successful SSM parameter resolution."""
        ssm_param = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64"
        resolved_ami = "ami-resolved123"
        
        self.mock_aws_client.ssm_client.get_parameter.return_value = {
            'Parameter': {'Value': resolved_ami}
        }
        
        result = self.resolver.resolve_with_fallback(ssm_param)
        
        assert result == resolved_ami
        self.mock_aws_client.ssm_client.get_parameter.assert_called_once_with(Name=ssm_param)
    
    def test_caching_behavior(self):
        """Test that successful resolutions are cached."""
        ssm_param = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64"
        resolved_ami = "ami-cached123"
        
        self.mock_aws_client.ssm_client.get_parameter.return_value = {
            'Parameter': {'Value': resolved_ami}
        }
        
        # First call should hit AWS
        result1 = self.resolver.resolve_with_fallback(ssm_param)
        assert result1 == resolved_ami
        assert self.mock_aws_client.ssm_client.get_parameter.call_count == 1
        
        # Second call should use cache
        result2 = self.resolver.resolve_with_fallback(ssm_param)
        assert result2 == resolved_ami
        assert self.mock_aws_client.ssm_client.get_parameter.call_count == 1  # No additional calls
    
    def test_failure_with_fallback(self):
        """Test failure handling with fallback enabled."""
        ssm_param = "/aws/service/nonexistent"
        
        self.mock_aws_client.ssm_client.get_parameter.side_effect = Exception("Parameter not found")
        
        result = self.resolver.resolve_with_fallback(ssm_param)
        
        assert result == ssm_param  # Should return original parameter
        self.mock_aws_client.ssm_client.get_parameter.assert_called_once_with(Name=ssm_param)


class TestResolvingTemplateConfigurationManager:
    """Test ResolvingTemplateConfigurationManager decorator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_base_manager = Mock()
        self.mock_ami_resolver = Mock()
        self.resolving_manager = ResolvingTemplateConfigurationManager(
            base_manager=self.mock_base_manager,
            ami_resolver=self.mock_ami_resolver
        )
    
    def test_get_template_by_id_with_resolution(self):
        """Test get_template_by_id with AMI resolution."""
        from src.domain.template.aggregate import Template
        
        # Mock template with SSM parameter
        mock_template = Mock(spec=Template)
        mock_template.template_id = "test-template"
        mock_template.image_id = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64"
        mock_template.update_image_id.return_value = mock_template
        
        self.mock_base_manager.get_template_by_id.return_value = mock_template
        self.mock_ami_resolver.resolve_with_fallback.return_value = "ami-resolved123"
        
        result = self.resolving_manager.get_template_by_id("test-template")
        
        # Verify base manager was called
        self.mock_base_manager.get_template_by_id.assert_called_once_with("test-template")
        
        # Verify AMI resolver was called
        self.mock_ami_resolver.resolve_with_fallback.assert_called_once_with(
            "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64"
        )
        
        # Verify template was updated
        mock_template.update_image_id.assert_called_once_with("ami-resolved123")
