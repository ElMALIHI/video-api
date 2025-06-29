from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
import os
import logging
import redis

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()

# Redis configuration
def get_redis_client():
    """Get Redis client with proper error handling."""
    try:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            return redis.from_url(redis_url, decode_responses=True)
        else:
            return redis.StrictRedis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                password=os.getenv("REDIS_PASSWORD", None),
                decode_responses=True
            )
    except Exception as e:
        logger.error(f"Failed to create Redis client: {e}")
        return None

def get_api_keys() -> List[str]:
    """
    Get the list of valid API keys from Redis or environment variables.
    
    Returns:
        List[str]: List of valid API keys
    """
    try:
        redis_client = get_redis_client()
        if not redis_client:
            logger.warning("Redis client unavailable. Falling back to environment variable.")
            return load_keys_from_env()
        
        api_keys = redis_client.lrange("api_keys", 0, -1)
        if not api_keys:
            logger.warning("No API keys found in Redis. Falling back to environment variable.")
            return load_keys_from_env()
        logger.info(f"Loaded {len(api_keys)} API key(s) from Redis")
        return api_keys
    except redis.RedisError as e:
        logger.error(f"Redis error: {e}. Falling back to environment variable.")
        return load_keys_from_env()
    except Exception as e:
        logger.error(f"Unexpected error getting API keys: {e}. Falling back to environment variable.")
        return load_keys_from_env()

def load_keys_from_env() -> List[str]:
    """
    Load API keys from environment variables.
    
    Returns:
        List[str]: List of valid API keys
    """
    api_keys_str = os.getenv("API_KEYS", "")
    if not api_keys_str:
        default_key = "dev-api-key-12345"
        logger.warning(f"No API_KEYS environment variable set. Using default key: {default_key}")
        return [default_key]
    api_keys = [key.strip() for key in api_keys_str.split(",") if key.strip()]
    if not api_keys:
        raise ValueError("API_KEYS environment variable is empty or invalid")
    logger.info(f"Loaded {len(api_keys)} API key(s) from environment")
    return api_keys

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Verify the provided API key.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        str: The validated API key
        
    Raises:
        HTTPException: If the API key is invalid
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = credentials.credentials
    valid_keys = get_api_keys()
    
    if token not in valid_keys:
        logger.warning(f"Invalid API key attempted: {token[:10]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    logger.debug(f"Valid API key authenticated: {token[:10]}...")
    return token

# Optional authentication for some endpoints
def verify_api_key_optional(request: Request) -> Optional[str]:
    """
    Verify the provided API key, but don't require it (for optional auth endpoints).
    
    Args:
        request: FastAPI request object
        
    Returns:
        Optional[str]: The validated API key if provided and valid, None otherwise
    """
    try:
        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
        
        # Parse Bearer token
        if not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ", 1)[1] if len(auth_header.split(" ", 1)) > 1 else None
        if not token:
            return None
        
        # Verify token
        valid_keys = get_api_keys()
        if token in valid_keys:
            logger.debug(f"Valid API key authenticated (optional): {token[:10]}...")
            return token
        else:
            logger.debug(f"Invalid API key attempted (optional): {token[:10]}...")
            return None
    except Exception as e:
        logger.debug(f"Error in optional API key verification: {e}")
        return None

class AuthenticatedUser:
    """
    Simple class to represent an authenticated user (API key holder).
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        # In a real system, you might have more user info here
        self.user_id = f"user_{hash(api_key) % 10000}"
    
    def __str__(self):
        return f"AuthenticatedUser(user_id={self.user_id}, api_key={self.api_key[:10]}...)"

def get_current_user(api_key: str = Depends(verify_api_key)) -> AuthenticatedUser:
    """
    Get the current authenticated user from the API key.
    
    Args:
        api_key: Validated API key
        
    Returns:
        AuthenticatedUser: The authenticated user object
    """
    return AuthenticatedUser(api_key)

def get_current_user_optional(api_key: Optional[str] = Depends(verify_api_key_optional)) -> Optional[AuthenticatedUser]:
    """
    Get the current authenticated user if authentication is provided.
    
    Args:
        api_key: Optional validated API key
        
    Returns:
        Optional[AuthenticatedUser]: The authenticated user object if valid auth provided
    """
    if api_key:
        return AuthenticatedUser(api_key)
    return None

# API Key Management Functions for Redis
def add_api_key(api_key: str) -> bool:
    """
    Add a new API key to Redis.
    
    Args:
        api_key: The API key to add
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        redis_client = get_redis_client()
        if not redis_client:
            logger.error("Redis client unavailable. Cannot add API key.")
            return False
        
        redis_client.lpush("api_keys", api_key)
        logger.info(f"Added API key: {api_key[:10]}...")
        return True
    except redis.RedisError as e:
        logger.error(f"Failed to add API key to Redis: {e}")
        return False

def remove_api_key(api_key: str) -> bool:
    """
    Remove an API key from Redis.
    
    Args:
        api_key: The API key to remove
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        redis_client = get_redis_client()
        if not redis_client:
            logger.error("Redis client unavailable. Cannot remove API key.")
            return False
        
        result = redis_client.lrem("api_keys", 0, api_key)
        if result > 0:
            logger.info(f"Removed API key: {api_key[:10]}...")
            return True
        else:
            logger.warning(f"API key not found for removal: {api_key[:10]}...")
            return False
    except redis.RedisError as e:
        logger.error(f"Failed to remove API key from Redis: {e}")
        return False

def rotate_api_keys(new_keys: List[str]) -> bool:
    """
    Replace all API keys in Redis with new ones (key rotation).
    
    Args:
        new_keys: List of new API keys
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        redis_client = get_redis_client()
        if not redis_client:
            logger.error("Redis client unavailable. Cannot rotate API keys.")
            return False
        
        # Delete existing keys and add new ones atomically
        with redis_client.pipeline() as pipe:
            pipe.delete("api_keys")
            for key in new_keys:
                pipe.lpush("api_keys", key)
            pipe.execute()
        logger.info(f"Rotated API keys. New count: {len(new_keys)}")
        return True
    except redis.RedisError as e:
        logger.error(f"Failed to rotate API keys in Redis: {e}")
        return False

def get_api_key_count() -> int:
    """
    Get the count of API keys stored in Redis.
    
    Returns:
        int: Number of API keys, -1 if Redis error
    """
    try:
        redis_client = get_redis_client()
        if not redis_client:
            logger.error("Redis client unavailable. Cannot get API key count.")
            return -1
        
        return redis_client.llen("api_keys")
    except redis.RedisError as e:
        logger.error(f"Failed to get API key count from Redis: {e}")
        return -1

def initialize_api_keys_from_env() -> bool:
    """
    Initialize Redis with API keys from environment if Redis is empty.
    This is useful for first-time setup or fallback scenarios.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        redis_client = get_redis_client()
        if not redis_client:
            logger.warning("Redis client unavailable. Skipping Redis initialization.")
            return True  # Not a failure, just no Redis
        
        if redis_client.llen("api_keys") == 0:
            env_keys = load_keys_from_env()
            return rotate_api_keys(env_keys)
        return True
    except redis.RedisError as e:
        logger.error(f"Failed to initialize API keys from env: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error initializing API keys from env: {e}")
        return False
