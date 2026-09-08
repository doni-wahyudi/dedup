"""Models for bulk import operations"""

import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, JSON, BigInteger
from sqlalchemy.sql import func

from app.database.client import Base


class BulkImportJob(Base):
    """Model for tracking bulk import jobs"""
    
    __tablename__ = "bulk_import_jobs"
    
    # Primary fields
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(String(36), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    
    # Job configuration
    csv_file_path = Column(Text, nullable=False)
    images_directory = Column(Text, nullable=False)
    batch_size = Column(Integer, nullable=False, default=100)
    
    # Progress tracking
    total_estimated = Column(Integer, nullable=True)
    current_row = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    percentage = Column(Float, nullable=False, default=0.0)
    processing_rate = Column(String(50), nullable=True)
    
    # Timing
    created_at = Column(DateTime, nullable=False, default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    estimated_completion = Column(DateTime, nullable=True)
    
    # Results
    success_rate = Column(Float, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Checkpoint data
    last_checkpoint_row = Column(Integer, nullable=False, default=0)
    checkpoint_data = Column(JSON, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    
    def __repr__(self):
        return f"<BulkImportJob(job_id='{self.job_id}', status='{self.status}', progress={self.percentage}%)>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "csv_file_path": self.csv_file_path,
            "images_directory": self.images_directory,
            "batch_size": self.batch_size,
            "progress": {
                "total_estimated": self.total_estimated,
                "current_row": self.current_row,
                "success_count": self.success_count,
                "error_count": self.error_count,
                "percentage": self.percentage,
                "processing_rate": self.processing_rate,
                "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None
            },
            "timing": {
                "created_at": self.created_at.isoformat(),
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "duration_seconds": self.duration_seconds
            },
            "results": {
                "success_rate": self.success_rate,
                "error_message": self.error_message
            },
            "checkpoint": {
                "last_row": self.last_checkpoint_row,
                "data": self.checkpoint_data
            }
        }


class BulkImportError(Base):
    """Model for tracking individual record errors during bulk import"""
    
    __tablename__ = "bulk_import_errors"
    
    # Primary fields
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(String(36), nullable=False, index=True)
    
    # Error details
    row_number = Column(Integer, nullable=False)
    field_name = Column(String(100), nullable=True)
    error_category = Column(String(50), nullable=False, index=True)  # For easy filtering
    error_message = Column(Text, nullable=False)
    retryable = Column(Boolean, nullable=False, default=True)
    
    # Timing
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Additional context
    file_path = Column(Text, nullable=True)
    additional_context = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<BulkImportError(job_id='{self.job_id}', row={self.row_number}, error='{self.error_message[:50]}')>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "row_number": self.row_number,
            "field_name": self.field_name,
            "error_category": self.error_category,
            "error_message": self.error_message,
            "retryable": self.retryable,
            "timestamp": self.created_at.isoformat(),
            "file_path": self.file_path,
            "context": self.additional_context
        }


class BulkImportStats(Base):
    """Model for storing bulk import statistics and metrics"""
    
    __tablename__ = "bulk_import_stats"
    
    # Primary fields
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(String(36), nullable=False, index=True)
    
    # Basic stats
    total_records = Column(Integer, nullable=False, default=0)
    processed_records = Column(Integer, nullable=False, default=0)
    successful_records = Column(Integer, nullable=False, default=0)
    failed_records = Column(Integer, nullable=False, default=0)
    
    # Performance metrics
    processing_time_seconds = Column(Float, nullable=True)
    average_processing_rate = Column(Float, nullable=True)  # records per second
    peak_memory_usage_mb = Column(Float, nullable=True)
    
    # Quality metrics  
    face_detection_success_rate = Column(Float, nullable=True)
    image_processing_success_rate = Column(Float, nullable=True)
    upload_success_rate = Column(Float, nullable=True)
    
    # Error breakdown
    no_face_detected_count = Column(Integer, nullable=False, default=0)
    multiple_faces_count = Column(Integer, nullable=False, default=0)
    invalid_image_count = Column(Integer, nullable=False, default=0)
    file_not_found_count = Column(Integer, nullable=False, default=0)
    upload_failed_count = Column(Integer, nullable=False, default=0)
    database_error_count = Column(Integer, nullable=False, default=0)
    
    # Timing
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    def __repr__(self):
        return f"<BulkImportStats(job_id='{self.job_id}', success_rate={self.face_detection_success_rate or 0}%)>"


# Indexes for bulk import models
sa.Index('idx_bulk_import_jobs_status_created', BulkImportJob.status, BulkImportJob.created_at)
sa.Index('idx_bulk_import_errors_job_created', BulkImportError.job_id, BulkImportError.created_at)
sa.Index('idx_bulk_import_stats_job', BulkImportStats.job_id, BulkImportStats.created_at)