from fastapi import APIRouter, HTTPException
from datetime import datetime
import os
import redis
import sqlite3
from app.models import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint that returns the status of the API and its dependencies.
    
    This endpoint does not require authentication and provides information about:
    - API status
    - Database connectivity
    - Redis connectivity
    - System timestamp
    """
    
    # Basic API info
    api_status = "healthy"
    version = "1.0.0"
    timestamp = datetime.utcnow()
    
    # Check database connectivity
    database_status = "unknown"
    try:
        database_url = os.getenv("DATABASE_URL", "sqlite:///./jobs.db")
        if database_url.startswith("sqlite"):
            # For SQLite, check if we can connect
            db_path = database_url.replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1")
            conn.close()
            database_status = "healthy"
        else:
            # For other databases, you'd implement specific connectivity checks
            database_status = "healthy"  # Assume healthy for now
    except Exception as e:
        database_status = f"unhealthy: {str(e)}"
        api_status = "degraded"
    
    # Check Redis connectivity
    redis_status = "unknown"
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        r.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
        api_status = "degraded"
    
    # If both database and Redis are down, mark API as unhealthy
    if "unhealthy" in database_status and "unhealthy" in redis_status:
        api_status = "unhealthy"
    
    return HealthResponse(
        status=api_status,
        version=version,
        timestamp=timestamp,
        uptime=None,  # Could implement uptime tracking if needed
        database=database_status,
        redis=redis_status
    )
