from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import time
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import endpoints
from app.endpoints import upload, compose, jobs, health
from app.auth import initialize_api_keys_from_env

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format=os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Video Composition API",
    description="A powerful API for composing videos from multiple media sources",
    version="1.0.0",
    debug=os.getenv("DEBUG", "False").lower() == "true"
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
if cors_origins == [""]:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=os.getenv("CORS_CREDENTIALS", "true").lower() == "true",
    allow_methods=os.getenv("CORS_METHODS", "GET,POST,PUT,DELETE,OPTIONS").split(","),
    allow_headers=os.getenv("CORS_HEADERS", "*").split(",") if os.getenv("CORS_HEADERS") != "*" else ["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("Starting Video Composition API...")
    
    # Initialize API keys from environment if Redis is empty
    if initialize_api_keys_from_env():
        logger.info("API keys initialized successfully")
    else:
        logger.error("Failed to initialize API keys")

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(upload.router, prefix="/api/v1", tags=["upload"])
app.include_router(compose.router, prefix="/api/v1", tags=["compose"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Video Composition API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"
    
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
