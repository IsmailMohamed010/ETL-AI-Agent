"""
Database models using SQLAlchemy ORM.
Stores processing jobs and results.
"""

from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import settings
import uuid

Base = declarative_base()

class ProcessingJob(Base):
    """Model for processing jobs."""
    __tablename__ = "processing_jobs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    job_type = Column(String(50))  # file, database, web
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Input data
    input_data = Column(JSON, nullable=True)
    
    # Results
    extracted_records = Column(Integer, default=0)
    output_file_path = Column(String(500), nullable=True)
    result_data = Column(JSON, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    
    # Processing details
    file_name = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)
    processing_time = Column(Integer, nullable=True)  # in seconds

class UploadedFile(Base):
    """Model for uploaded files."""
    __tablename__ = "uploaded_files"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36))
    file_name = Column(String(255))
    file_path = Column(String(500))
    file_type = Column(String(10))
    file_size = Column(Integer)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="pending")

class ExtractionResult(Base):
    """Model for storing extraction results."""
    __tablename__ = "extraction_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36))
    data = Column(JSON)
    detected_relationships = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ─────────────────────────────────────────────────────────────────────────────
# Database Setup
# ─────────────────────────────────────────────────────────────────────────────

def get_database_engine():
    """Create database engine."""
    return create_engine(
        settings.database_url,
        echo=settings.debug,
        connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
    )

def get_session_local():
    """Create session factory."""
    engine = get_database_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
def init_db():
    """Initialize database tables."""
    engine = get_database_engine()
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency for getting database session."""
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
