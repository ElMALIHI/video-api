from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./jobs.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()


class Job(Base):
    """Job model for tracking job processing status and data."""
    
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    api_key = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, processing, completed, failed
    progress = Column(Float, default=0.0)  # Progress percentage (0.0 to 100.0)
    input_json = Column(Text, nullable=True)  # JSON string of input data
    output_path = Column(String(500), nullable=True)  # Path to output file/result
    error = Column(Text, nullable=True)  # Error message if job failed
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)  # When job processing started
    completed_at = Column(DateTime, nullable=True)  # When job finished (success or failure)


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """
    Database dependency that provides a database session.
    
    This function is designed to be used as a dependency in FastAPI
    or similar frameworks that support dependency injection.
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize database tables when module is imported
create_tables()
