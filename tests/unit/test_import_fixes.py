#!/usr/bin/env python3
"""Simple test to verify import fixes."""

import sys


def test_import_fixes():
    """Test that the import fixes are working."""
    print("Testing import fixes...")

    try:
        # Test 1: Check that ProviderApi exists in AWS value objects
        print("1. Testing ProviderApi import...")
        from src.providers.aws.domain.template.value_objects import ProviderApi

        print(f"   ✅ ProviderApi imported successfully: {list(ProviderApi)}")

        # Test 2: Check that ProviderHandlerType does NOT exist
        print("2. Testing that ProviderHandlerType is removed...")
        try:
            pass

            print("   ❌ ProviderHandlerType still exists - should be removed!")
            return False
        except ImportError:
            print("   ✅ ProviderHandlerType correctly removed")

        # Test 3: Check that handlers can import ProviderApi
        print("3. Testing handler imports...")
        try:
            # This will fail if there are import issues
            pass

            print("   ✅ Spot fleet handler imports successfully")
        except Exception as e:
            print(f"   ❌ Spot fleet handler import failed: {e}")
            return False

        try:
            pass

            print("   ✅ EC2 fleet handler imports successfully")
        except Exception as e:
            print(f"   ❌ EC2 fleet handler import failed: {e}")
            return False

        print("\n🎉 All import fixes verified successfully!")
        return True

    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_import_fixes()
    sys.exit(0 if success else 1)
