"""
Main FastAPI application for ETL Pipeline Backend.

This is the entry point for the REST API server.
Run with: uvicorn main:app --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
import logging
from datetime import datetime
from pathlib import Path

from config import settings
from database import init_db
from schemas import HealthCheckResponse
from routes_extraction import router as extraction_router

# ─────────────────────────────────────────────────────────────────────────────
# Configure Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle Events
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # Startup
    logger.info("🚀 Starting ETL Pipeline API")
    init_db()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Upload directory: {settings.upload_dir}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down ETL Pipeline API")

# ─────────────────────────────────────────────────────────────────────────────
# Create FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    description="REST API for automated ETL data processing pipeline",
    version=settings.app_version,
    lifespan=lifespan,
)

# ─────────────────────────────────────────────────────────────────────────────
# CORS Middleware
# ─────────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Exception Handlers
# ─────────────────────────────────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": "HTTP_ERROR",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_code": "INTERNAL_ERROR",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

# ─────────────────────────────────────────────────────────────────────────────
# Health Check & Info Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint.
    
    **Returns:**
    - System status (healthy/unhealthy)
    - API version
    - Current timestamp
    
    **Example:**
    ```
    curl "http://localhost:8000/health"
    ```
    """
    return HealthCheckResponse(
        status="healthy",
        version=settings.app_version
    )

@app.get("/api/v1/info")
async def api_info():
    """
    Get API information and configuration.
    
    **Returns:**
    - API name and version
    - Available endpoints
    - Configuration details
    
    **Example:**
    ```
    curl "http://localhost:8000/api/v1/info"
    ```
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Automated ETL data processing pipeline",
        "api_prefix": settings.api_prefix,
        "supported_file_types": settings.allowed_extensions,
        "max_upload_size_mb": settings.max_upload_size / 1024 / 1024,
        "max_workers": settings.max_workers,
        "processing_timeout_seconds": settings.processing_timeout,
        "debug_mode": settings.debug,
    }

# ─────────────────────────────────────────────────────────────────────────────
# Include Routers
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(extraction_router, prefix=settings.api_prefix)

# ─────────────────────────────────────────────────────────────────────────────
# Root Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Welcome endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "info": "/api/v1/info"
    }

# ─────────────────────────────────────────────────────────────────────────────
# Custom OpenAPI Schema
# ─────────────────────────────────────────────────────────────────────────────

def custom_openapi():
    """Customize OpenAPI documentation."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.app_name,
        version=settings.app_version,
        description="REST API for automated ETL data processing. Upload files, process data, and extract insights.",
        routes=app.routes,
    )
    
    # Add servers
    openapi_schema["servers"] = [
        {"url": "http://localhost:8000", "description": "Development"},
        {"url": "https://api.example.com", "description": "Production"},
    ]
    
    # Add security schemes if needed
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# ─────────────────────────────────────────────────────────────────────────────
# Startup Event
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
