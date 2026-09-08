"""Models for enrollment and fraud detection"""

import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, DateTime, Float, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.client import Base


class EnrolledFace(Base):
    """Model for tracking enrolled faces and fraud detection"""
    
    __tablename__ = "enrolled_faces"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    milvus_id = Column(String(50), unique=True, nullable=False, index=True)
    nik = Column(String(50), nullable=False, index=True)
    
    # CIF Information
    cif_name = Column(String(200), nullable=True)
    cif_code = Column(String(50), nullable=True)
    
    # Sentra Information
    sentra_id = Column(String(20), nullable=True, index=True)
    sentra_name = Column(String(200), nullable=True)
    
    # MMS Information
    mms_code = Column(String(50), nullable=True)
    mms_name = Column(String(200), nullable=True)
    
    # Credit Officer Assignment
    co_assignment_nik = Column(String(50), nullable=True)
    co_assignment_code = Column(String(50), nullable=True)
    co_assignment_name = Column(String(200), nullable=True)
    
    # Credit Officer Enrollment
    co_enrol_nik = Column(String(50), nullable=True)
    co_enrol_code = Column(String(50), nullable=True)
    co_enrol_name = Column(String(200), nullable=True)
    
    # Image and timing
    image_url = Column(String(500), nullable=True)
    enroll_date_time = Column(DateTime, nullable=True)
    
    fraud_status = Column(String(20), nullable=False, default="clean", index=True)
    check_status = Column(String(20), nullable=False, default="pending", index=True)
    
    processing_by = Column(String(100), nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    processing_attempts = Column(Integer, nullable=False, default=0)
    
    last_checked_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)
    
    enrolled_at = Column(DateTime, nullable=False, default=func.now())
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<EnrolledFace(id={self.id}, milvus_id='{self.milvus_id}')>"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "milvus_id": self.milvus_id,
            "nik": self.nik,
            "cif_name": self.cif_name,
            "cif_code": self.cif_code,
            "sentra_id": self.sentra_id,
            "sentra_name": self.sentra_name,
            "mms_code": self.mms_code,
            "mms_name": self.mms_name,
            "co_assignment_nik": self.co_assignment_nik,
            "co_assignment_code": self.co_assignment_code,
            "co_assignment_name": self.co_assignment_name,
            "co_enrol_nik": self.co_enrol_nik,
            "co_enrol_code": self.co_enrol_code,
            "co_enrol_name": self.co_enrol_name,
            "image_url": self.image_url,
            "enroll_date_time": self.enroll_date_time.isoformat() if self.enroll_date_time else None,
            "fraud_status": self.fraud_status,
            "check_status": self.check_status
        }


class FraudCase(Base):
    """Model for tracking fraud cases (duplicate face detection)"""
    
    __tablename__ = "fraud_cases"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    primary_enrollment_id = Column(BigInteger, ForeignKey("enrolled_faces.id"), nullable=False, index=True)
    duplicate_enrollment_id = Column(BigInteger, ForeignKey("enrolled_faces.id"), nullable=False, index=True)
    distance = Column(Float, nullable=False)
    detected_at = Column(DateTime, nullable=False, default=func.now())
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    primary_enrollment = relationship("EnrolledFace", foreign_keys=[primary_enrollment_id])
    duplicate_enrollment = relationship("EnrolledFace", foreign_keys=[duplicate_enrollment_id])
    
    def __repr__(self):
        return f"<FraudCase(id={self.id}, distance={self.distance:.2f})>"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "primary_enrollment_id": self.primary_enrollment_id,
            "duplicate_enrollment_id": self.duplicate_enrollment_id,
            "distance": self.distance,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None
        }


# Indexes for enrollment models
sa.Index('idx_enrolled_faces_check_processing', EnrolledFace.check_status, EnrolledFace.processing_started_at)
sa.Index('idx_fraud_cases_pair', FraudCase.primary_enrollment_id, FraudCase.duplicate_enrollment_id)