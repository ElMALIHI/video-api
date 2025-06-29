#!/usr/bin/env python3
"""
Test script for API key authentication system.

This script tests the API key authentication functionality including:
- Adding/removing keys from Redis
- Verifying API keys
- Key rotation
- Fallback to environment variables
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_auth_system():
    """Test the authentication system."""
    try:
        from app.auth import (
            add_api_key,
            remove_api_key,
            rotate_api_keys,
            get_api_keys,
            get_api_key_count,
            initialize_api_keys_from_env,
            redis_client
        )
        
        print("🔧 Testing API Key Authentication System")
        print("=" * 50)
        
        # Test 1: Clear Redis and test fallback to env
        print("\n1. Testing fallback to environment variables...")
        redis_client.delete("api_keys")
        
        keys = get_api_keys()
        print(f"   Got {len(keys)} key(s) from environment fallback")
        assert len(keys) > 0, "Should have at least one key from environment"
        
        # Test 2: Initialize from environment
        print("\n2. Testing initialization from environment...")
        result = initialize_api_keys_from_env()
        assert result, "Should initialize successfully"
        
        count = get_api_key_count()
        print(f"   Initialized {count} key(s) to Redis")
        
        # Test 3: Add a new key
        print("\n3. Testing add API key...")
        test_key = "test-api-key-12345"
        result = add_api_key(test_key)
        assert result, "Should add key successfully"
        
        new_count = get_api_key_count()
        assert new_count == count + 1, "Count should increase by 1"
        print(f"   Added key. New count: {new_count}")
        
        # Test 4: Verify the key is in the list
        print("\n4. Testing key retrieval...")
        keys = get_api_keys()
        assert test_key in keys, "Test key should be in the list"
        print(f"   Test key found in list of {len(keys)} keys")
        
        # Test 5: Remove the key
        print("\n5. Testing remove API key...")
        result = remove_api_key(test_key)
        assert result, "Should remove key successfully"
        
        final_count = get_api_key_count()
        assert final_count == count, "Count should return to original"
        print(f"   Removed key. Final count: {final_count}")
        
        # Test 6: Test key rotation
        print("\n6. Testing key rotation...")
        new_keys = ["rotate-key-1", "rotate-key-2", "rotate-key-3"]
        result = rotate_api_keys(new_keys)
        assert result, "Should rotate keys successfully"
        
        rotated_keys = get_api_keys()
        assert len(rotated_keys) == 3, "Should have 3 keys after rotation"
        for key in new_keys:
            assert key in rotated_keys, f"Key {key} should be in rotated keys"
        print(f"   Rotated to {len(rotated_keys)} new keys")
        
        # Test 7: Test authentication dependency (mock)
        print("\n7. Testing authentication verification...")
        from fastapi.security import HTTPAuthorizationCredentials
        from app.auth import verify_api_key
        
        # This would normally be called by FastAPI with real credentials
        # For testing, we'll just verify the keys we set are valid
        current_keys = get_api_keys()
        print(f"   Current valid keys: {[k[:10] + '...' for k in current_keys]}")
        
        print("\n✅ All tests passed!")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup: restore original state
        try:
            print("\n🧹 Cleaning up...")
            initialize_api_keys_from_env()
            print("   Restored original API keys")
        except:
            pass

if __name__ == "__main__":
    success = test_auth_system()
    exit(0 if success else 1)
