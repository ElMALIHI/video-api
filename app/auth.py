from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
import os
import logging

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()

def get_api_keys() -> List[str]:
    """
    Get the list of valid API keys from environment variables.
    
    Returns:
        List[str]: List of valid API keys
    """
    api_keys_str = os.getenv("API_KEYS", "")
    if not api_keys_str:
        # For development, return a default key
        default_key = "dev-api-key-12345"
        logger.warning(f"No API_KEYS environment variable set. Using default key: {default_key}")
        return [default_key]
    
    # Split by comma and strip whitespace
    api_keys = [key.strip() for key in api_keys_str.split(",") if key.strip()]
    
    if not api_keys:
        raise ValueError("API_KEYS environment variable is empty or invalid")
    
    logger.info(f"Loaded {len(api_keys)} API key(s)")
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
def verify_api_key_optional(credentials: Optional[HTTPAuthorizationCredentials] = Security(security, auto_error=False)) -> Optional[str]:
    """
    Verify the provided API key, but don't require it (for optional auth endpoints).
    
    Args:
        credentials: HTTP authorization credentials (optional)
        
    Returns:
        Optional[str]: The validated API key if provided and valid, None otherwise
    """
    if not credentials:
        return None
    
    try:
        return verify_api_key(credentials)
    except HTTPException:
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
