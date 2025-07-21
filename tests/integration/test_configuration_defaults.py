#!/usr/bin/env python3
"""
Test for Configuration Defaults Integration
Tests that templates get proper defaults from configuration when fields are missing.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_template_defaults_integration():
    """Test that template repository applies configuration defaults correctly."""
    print("=== Configuration Defaults Integration Test ===")

    try:
        from src.application.services.template_defaults_service import (
            TemplateDefaultsService,
        )
        from src.config.manager import ConfigurationManager
        from src.infrastructure.logging.logger import get_logger
        from src.infrastructure.persistence.repositories.template_repository import (
            TemplateSerializer,
        )

        # Create configuration manager and defaults service
        config_manager = ConfigurationManager()
        logger = get_logger(__name__)
        defaults_service = TemplateDefaultsService(config_manager, logger)

        # Create serializer with defaults service
        serializer = TemplateSerializer(defaults_service=defaults_service)

        # Test data with MISSING required fields (should get defaults)
        minimal_template_data = {
            "template_id": "test-minimal-template",
            "image_id": "ami-123456",
            # subnet_ids is MISSING - should get defaults
            # security_group_ids is MISSING - should get defaults
            # instance_type is MISSING - should get defaults
        }

        print("✅ Testing template with missing required fields...")
        print(f"   - Input data: {list(minimal_template_data.keys())}")

        # This should NOT fail because defaults will be applied
        template = serializer.from_dict(minimal_template_data)

        print("✅ Template created successfully with defaults applied")
        print(f"   - Template ID: {template.template_id}")
        print(f"   - Subnet IDs: {template.subnet_ids}")
        print(f"   - Security Groups: {template.security_group_ids}")
        print(f"   - Instance Type: {template.instance_type}")
        print(f"   - Provider API: {template.provider_api}")

        # Verify defaults were applied
        assert template.subnet_ids, "subnet_ids should have defaults applied"
        assert template.security_group_ids, "security_group_ids should have defaults applied"
        assert template.instance_type, "instance_type should have defaults applied"

        print("✅ Configuration defaults successfully applied to missing fields")

        return True

    except Exception as e:
        print(f"❌ Configuration defaults integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_template_defaults_precedence():
    """Test that template values override defaults (proper precedence)."""
    print("\n=== Template Defaults Precedence Test ===")

    try:
        from src.application.services.template_defaults_service import (
            TemplateDefaultsService,
        )
        from src.config.manager import ConfigurationManager
        from src.infrastructure.logging.logger import get_logger
        from src.infrastructure.persistence.repositories.template_repository import (
            TemplateSerializer,
        )

        # Create configuration manager and defaults service
        config_manager = ConfigurationManager()
        logger = get_logger(__name__)
        defaults_service = TemplateDefaultsService(config_manager, logger)

        # Create serializer with defaults service
        serializer = TemplateSerializer(defaults_service=defaults_service)

        # Test data with EXPLICIT values (should override defaults)
        explicit_template_data = {
            "template_id": "test-explicit-template",
            "image_id": "ami-123456",
            "subnet_ids": ["subnet-explicit-123"],  # Explicit value
            "security_group_ids": ["sg-explicit-456"],  # Explicit value
            "instance_type": "t3.large",  # Explicit value (different from default)
        }

        print("✅ Testing template with explicit values...")
        print(f"   - Input subnet_ids: {explicit_template_data['subnet_ids']}")
        print(f"   - Input security_group_ids: {explicit_template_data['security_group_ids']}")
        print(f"   - Input instance_type: {explicit_template_data['instance_type']}")

        template = serializer.from_dict(explicit_template_data)

        print("✅ Template created successfully with explicit values preserved")
        print(f"   - Final subnet_ids: {template.subnet_ids}")
        print(f"   - Final security_group_ids: {template.security_group_ids}")
        print(f"   - Final instance_type: {template.instance_type}")

        # Verify explicit values were preserved (not overridden by defaults)
        assert template.subnet_ids == [
            "subnet-explicit-123"
        ], "Explicit subnet_ids should be preserved"
        assert template.security_group_ids == [
            "sg-explicit-456"
        ], "Explicit security_group_ids should be preserved"
        assert template.instance_type == "t3.large", "Explicit instance_type should be preserved"

        print("✅ Template values correctly override defaults (proper precedence)")

        return True

    except Exception as e:
        print(f"❌ Template defaults precedence test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_defaults_service_directly():
    """Test the TemplateDefaultsService directly."""
    print("\n=== Direct TemplateDefaultsService Test ===")

    try:
        from src.application.services.template_defaults_service import (
            TemplateDefaultsService,
        )
        from src.config.manager import ConfigurationManager
        from src.infrastructure.logging.logger import get_logger

        # Create service
        config_manager = ConfigurationManager()
        logger = get_logger(__name__)
        defaults_service = TemplateDefaultsService(config_manager, logger)

        # Test minimal template data
        minimal_data = {"template_id": "test-direct", "image_id": "ami-123456"}

        print("✅ Testing TemplateDefaultsService directly...")
        print(f"   - Input data: {list(minimal_data.keys())}")

        # Apply defaults
        enriched_data = defaults_service.resolve_template_defaults(
            minimal_data, provider_instance_name="aws-default"
        )

        print("✅ Defaults applied successfully")
        print(f"   - Output data keys: {list(enriched_data.keys())}")
        print(f"   - subnet_ids: {enriched_data.get('subnet_ids')}")
        print(f"   - security_group_ids: {enriched_data.get('security_group_ids')}")
        print(f"   - instance_type: {enriched_data.get('instance_type')}")
        print(f"   - provider_api: {enriched_data.get('provider_api')}")

        # Verify some defaults were applied
        assert len(enriched_data) > len(minimal_data), "Defaults should add more fields"

        print("✅ TemplateDefaultsService working correctly")

        return True

    except Exception as e:
        print(f"❌ Direct TemplateDefaultsService test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Running Configuration Defaults Integration Tests...")

    test1_passed = test_template_defaults_integration()
    test2_passed = test_template_defaults_precedence()
    test3_passed = test_defaults_service_directly()

    if test1_passed and test2_passed and test3_passed:
        print("\n🎉 ALL CONFIGURATION DEFAULTS INTEGRATION TESTS PASSED")
        print("✅ Configuration defaults are properly applied to missing fields")
        print("✅ Template values correctly override defaults")
        print("✅ TemplateDefaultsService working correctly")
        print("✅ Repository integration with defaults service working")
        sys.exit(0)
    else:
        print("\n❌ SOME CONFIGURATION DEFAULTS TESTS FAILED")
        sys.exit(1)
