#!/usr/bin/env python3
"""
API Key Management CLI

This script provides a command-line interface for managing API keys in Redis.
It supports adding, removing, rotating, and listing API keys.

Usage:
    python manage_api_keys.py list
    python manage_api_keys.py add "new-api-key-12345"
    python manage_api_keys.py remove "old-api-key-12345"
    python manage_api_keys.py rotate "key1,key2,key3"
    python manage_api_keys.py init
"""

import sys
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import authentication functions
from app.auth import (
    add_api_key,
    remove_api_key,
    rotate_api_keys,
    get_api_key_count,
    initialize_api_keys_from_env,
    redis_client
)

def list_keys():
    """List all API keys currently stored in Redis."""
    try:
        keys = redis_client.lrange("api_keys", 0, -1)
        count = len(keys)
        print(f"Found {count} API key(s) in Redis:")
        for i, key in enumerate(keys, 1):
            # Show only first 10 characters for security
            print(f"  {i}. {key[:10]}...")
        return True
    except Exception as e:
        print(f"Error listing API keys: {e}")
        return False

def add_key(api_key: str):
    """Add a new API key to Redis."""
    if not api_key or len(api_key.strip()) < 10:
        print("Error: API key must be at least 10 characters long")
        return False
    
    api_key = api_key.strip()
    if add_api_key(api_key):
        print(f"Successfully added API key: {api_key[:10]}...")
        return True
    else:
        print("Failed to add API key")
        return False

def remove_key(api_key: str):
    """Remove an API key from Redis."""
    if not api_key:
        print("Error: API key cannot be empty")
        return False
    
    api_key = api_key.strip()
    if remove_api_key(api_key):
        print(f"Successfully removed API key: {api_key[:10]}...")
        return True
    else:
        print("Failed to remove API key (key may not exist)")
        return False

def rotate_keys(keys_str: str):
    """Rotate all API keys with new ones."""
    if not keys_str:
        print("Error: Keys string cannot be empty")
        return False
    
    # Parse comma-separated keys
    new_keys = [key.strip() for key in keys_str.split(",") if key.strip()]
    
    if not new_keys:
        print("Error: No valid keys provided")
        return False
    
    # Validate key lengths
    for key in new_keys:
        if len(key) < 10:
            print(f"Error: API key '{key[:10]}...' must be at least 10 characters long")
            return False
    
    if rotate_api_keys(new_keys):
        print(f"Successfully rotated API keys. New count: {len(new_keys)}")
        return True
    else:
        print("Failed to rotate API keys")
        return False

def init_keys():
    """Initialize API keys from environment variables."""
    if initialize_api_keys_from_env():
        count = get_api_key_count()
        print(f"Successfully initialized API keys from environment. Count: {count}")
        return True
    else:
        print("Failed to initialize API keys from environment")
        return False

def main():
    parser = argparse.ArgumentParser(description="Manage API keys in Redis")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # List command
    subparsers.add_parser("list", help="List all API keys")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new API key")
    add_parser.add_argument("key", help="The API key to add")
    
    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove an API key")
    remove_parser.add_argument("key", help="The API key to remove")
    
    # Rotate command
    rotate_parser = subparsers.add_parser("rotate", help="Rotate all API keys")
    rotate_parser.add_argument("keys", help="Comma-separated list of new API keys")
    
    # Init command
    subparsers.add_parser("init", help="Initialize API keys from environment")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute the appropriate command
    try:
        if args.command == "list":
            success = list_keys()
        elif args.command == "add":
            success = add_key(args.key)
        elif args.command == "remove":
            success = remove_key(args.key)
        elif args.command == "rotate":
            success = rotate_keys(args.keys)
        elif args.command == "init":
            success = init_keys()
        else:
            print(f"Unknown command: {args.command}")
            return 1
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
