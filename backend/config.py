"""
Core configuration for the ETL API backend.
Handles environment variables, database configuration, and app settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App Settings
    app_name: str = "ETL Pipeline API"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # API Settings
    api_prefix: str = "/api/v1"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    
    # File Upload Settings
    max_upload_size: int = 50 * 1024 * 1024  # 50MB
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
    allowed_extensions: list = ["csv", "xlsx", "xls"]
    
    # Database Settings
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./etl_pipeline.db")
    
    # Processing Settings
    max_workers: int = int(os.getenv("MAX_WORKERS", "4"))
    processing_timeout: int = int(os.getenv("PROCESSING_TIMEOUT", "3600"))
    
    # Security Settings
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS Settings
    cors_origins: list = ["http://localhost:3000", "http://localhost:8000", "http://localhost"]
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        case_sensitive = False

# Initialize global settings
settings = Settings()

# Create upload directory if it doesn't exist
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
