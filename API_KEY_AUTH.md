# API Key Authentication System

This document describes the API key authentication system implemented for the Video Composition API.

## Overview

The authentication system provides secure API key-based authentication with the following features:

- **Redis-backed storage** with environment variable fallback
- **Multiple API keys** support for different clients/applications
- **Key rotation** without application restart
- **Automatic fallback** to environment variables when Redis is unavailable
- **401 JSON responses** for authentication failures
- **FastAPI dependency injection** for easy integration

## Architecture

### Components

1. **`app/auth.py`** - Core authentication module
2. **`manage_api_keys.py`** - CLI management tool
3. **`test_auth.py`** - Testing utilities
4. **Redis** - Primary storage for API keys
5. **Environment variables** - Fallback storage

### Authentication Flow

```
Request with Authorization Header
          ↓
    verify_api_key() dependency
          ↓
    Extract Bearer token
          ↓
    Check against Redis keys
          ↓
    Fallback to env if Redis fails
          ↓
    Return 401 if invalid or 200 if valid
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# API Key Authentication
API_KEYS=your-api-key-1,your-api-key-2,your-api-key-3

# Redis Configuration (for key storage)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
```

### Redis Setup

The system uses Redis to store API keys for dynamic management. If Redis is unavailable, the system falls back to environment variables.

## Usage

### FastAPI Integration

The authentication system provides FastAPI dependencies:

```python
from app.auth import verify_api_key, get_current_user

@app.get("/protected-endpoint")
async def protected_endpoint(user: AuthenticatedUser = Depends(get_current_user)):
    return {"message": f"Hello, {user.user_id}"}

@app.get("/optional-auth-endpoint")
async def optional_auth(user: Optional[AuthenticatedUser] = Depends(get_current_user_optional)):
    if user:
        return {"message": f"Authenticated as {user.user_id}"}
    else:
        return {"message": "Anonymous access"}
```

### Client Usage

Include the API key in the Authorization header:

```bash
curl -H "Authorization: Bearer your-api-key-here" \
     http://localhost:8000/api/v1/protected-endpoint
```

### Error Responses

Invalid or missing API keys return a 401 response:

```json
{
  "detail": "Invalid API key"
}
```

## Management

### CLI Management Tool

Use the `manage_api_keys.py` script to manage API keys:

```bash
# List all API keys
python manage_api_keys.py list

# Add a new API key
python manage_api_keys.py add "new-api-key-12345"

# Remove an API key
python manage_api_keys.py remove "old-api-key-12345"

# Rotate all keys (replace with new set)
python manage_api_keys.py rotate "key1,key2,key3"

# Initialize Redis from environment variables
python manage_api_keys.py init
```

### Programmatic Management

You can also manage keys programmatically:

```python
from app.auth import add_api_key, remove_api_key, rotate_api_keys

# Add a key
add_api_key("new-key-12345")

# Remove a key
remove_api_key("old-key-12345")

# Rotate all keys
rotate_api_keys(["key1", "key2", "key3"])
```

## Key Rotation

The system supports key rotation without application restart:

1. **Add new keys** while keeping old ones active
2. **Update clients** to use new keys
3. **Remove old keys** once all clients are updated

Example rotation workflow:

```bash
# 1. Add new keys alongside existing ones
python manage_api_keys.py add "new-key-v2-12345"

# 2. Update clients to use new keys
# ... update client configurations ...

# 3. Remove old keys
python manage_api_keys.py remove "old-key-v1-12345"
```

## Security Considerations

### Best Practices

1. **Generate strong keys** - Use cryptographically secure random strings
2. **Rotate keys regularly** - Implement a key rotation schedule
3. **Monitor usage** - Log authentication attempts and failures
4. **Secure Redis** - Use Redis AUTH and network security
5. **Environment protection** - Secure access to environment variables

### Key Generation

Generate secure API keys using:

```python
import secrets
import string

def generate_api_key(length=32):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# Generate a new key
new_key = generate_api_key()
print(f"New API key: {new_key}")
```

### Logging

The system logs authentication events:

- Successful authentications (DEBUG level)
- Failed authentication attempts (WARNING level)
- Key management operations (INFO level)
- Redis connection issues (ERROR level)

## Testing

Run the test suite to verify the authentication system:

```bash
python test_auth.py
```

This tests:
- Redis connectivity and fallback behavior
- Key addition, removal, and rotation
- Authentication verification
- Error handling

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check Redis server is running
   - Verify Redis configuration in environment
   - System will fallback to environment variables

2. **No API Keys Found**
   - Set `API_KEYS` environment variable
   - Run `python manage_api_keys.py init` to initialize Redis

3. **Authentication Failing**
   - Verify API key format and spelling
   - Check if key exists: `python manage_api_keys.py list`
   - Review application logs for details

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
export LOG_LEVEL=DEBUG
python -m uvicorn app.main:app
```

## Migration from Environment-Only

If migrating from environment variable-only authentication:

1. **Install Redis** and configure connection
2. **Run initialization** to populate Redis with existing keys:
   ```bash
   python manage_api_keys.py init
   ```
3. **Verify** keys are loaded correctly:
   ```bash
   python manage_api_keys.py list
   ```

The system maintains backward compatibility and will continue working with environment variables if Redis is unavailable.
