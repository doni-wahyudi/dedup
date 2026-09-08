from datetime import datetime
from typing import Optional, List, Generic, TypeVar

from pydantic import BaseModel, Field, ConfigDict

T = TypeVar('T')


class PaginationMetadata(BaseModel):
    """Pagination metadata"""
    
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_count: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response"""
    
    content: List[T] = Field(..., description="List of items")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")


class EnrolledFaceSchema(BaseModel):
    """Schema for enrolled face"""
    
    id: int = Field(..., description="Enrollment ID")
    milvus_id: str = Field(..., description="Milvus vector ID")
    nik: str = Field(..., description="Nomor Induk Kependudukan")
    cif_name: Optional[str] = Field(None, description="Customer Information File Name")
    cif_code: Optional[str] = Field(None, description="Customer Information File code")
    sentra_id: Optional[str] = Field(None, description="Sentra identifier")
    sentra_name: Optional[str] = Field(None, description="Sentra name")
    mms_code: Optional[str] = Field(None, description="MMS code")
    mms_name: Optional[str] = Field(None, alias="mmsName", description="MMS name")
    co_assignment_nik: Optional[str] = Field(None, description="Credit Officer Assignment NIK")
    co_assignment_code: Optional[str] = Field(None, description="Credit Officer Assignment Code")
    co_assignment_name: Optional[str] = Field(None, description="Credit Officer Assignment Name")
    co_enrol_nik: Optional[str] = Field(None, description="Credit Officer Enrollment NIK")
    co_enrol_code: Optional[str] = Field(None, description="Credit Officer Enrollment Code")
    co_enrol_name: Optional[str] = Field(None, description="Credit Officer Enrollment Name")
    enroll_date_time: Optional[datetime] = Field(None, description="Original enrollment timestamp")
    image_url: Optional[str] = Field(None, description="URL to stored face image")
    fraud_status: str = Field(..., description="Fraud status (clean, fraud, error)")
    check_status: str = Field(..., description="Check status (pending, processing, checked)")
    last_checked_at: Optional[datetime] = Field(None, description="Last fraud check timestamp")
    enrolled_at: datetime = Field(..., description="Enrollment timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")
    
    class Config:
        from_attributes = True


class FraudCaseSchema(BaseModel):
    """Schema for fraud case"""
    
    id: int = Field(..., description="Fraud case ID")
    primary_enrollment_id: int = Field(..., description="Primary enrollment ID")
    duplicate_enrollment_id: int = Field(..., description="Duplicate enrollment ID")
    distance: float = Field(..., description="IP distance score (higher = more similar)")
    detected_at: datetime = Field(..., description="Detection timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    primary_enrollment: Optional[EnrolledFaceSchema] = Field(None, description="Primary enrollment data")
    duplicate_enrollment: Optional[EnrolledFaceSchema] = Field(None, description="Duplicate enrollment data")
    
    class Config:
        from_attributes = True


class FaceMatch(BaseModel):
    """Single face match result"""
    
    id: str = Field(..., description="Enrollment ID")
    nik: str = Field(..., description="Nomor Induk Kependudukan")
    cif_name: Optional[str] = Field(None, description="Customer Information File Name")
    cif_code: Optional[str] = Field(None, description="Customer Information File code")
    sentra_id: Optional[str] = Field(None, description="Sentra identifier")
    sentra_name: Optional[str] = Field(None, description="Sentra name")
    mms_code: Optional[str] = Field(None, description="MMS code")
    mms_name: Optional[str] = Field(None, alias="mmsName", description="MMS name")
    co_assignment_nik: Optional[str] = Field(None, description="Credit Officer Assignment NIK")
    co_assignment_code: Optional[str] = Field(None, description="Credit Officer Assignment Code")
    co_assignment_name: Optional[str] = Field(None, description="Credit Officer Assignment Name")
    co_enrol_nik: Optional[str] = Field(None, description="Credit Officer Enrollment NIK")
    co_enrol_code: Optional[str] = Field(None, description="Credit Officer Enrollment Code")
    co_enrol_name: Optional[str] = Field(None, description="Credit Officer Enrollment Name")
    enroll_date_time: Optional[datetime] = Field(None, description="Original enrollment timestamp")
    image_url: Optional[str] = Field(None, description="URL to stored face image")
    distance: float = Field(..., description="Provider-specific distance (L2: lower=similar, IP: higher=similar)")
    enrolled_at: Optional[datetime] = Field(None, description="Enrollment timestamp")

class FaceSearchResponse(BaseModel):
    """Simple face search response"""
    
    faces: List[FaceMatch] = Field(..., description="List of matching faces")
    total: int = Field(..., description="Total number of matches found")
    search_ms: float = Field(..., description="Search execution time in milliseconds")


class FaceDuplicateMatch(BaseModel):
    """Single duplicate match result for face validation"""

    model_config = ConfigDict(populate_by_name=True)

    nik: str = Field(..., description="Nomor Induk Kependudukan")
    cif_name: Optional[str] = Field(None, alias="cifName", description="Customer Information File Name")
    cif_code: Optional[str] = Field(None, alias="cifCode", description="Customer Information File Code")
    sentra_id: Optional[str] = Field(None, alias="sentraId", description="Sentra identifier")
    sentra_name: Optional[str] = Field(None, alias="sentraName", description="Sentra name")
    mms_code: Optional[str] = Field(None, alias="mmsCode", description="MMS code")
    mms_name: Optional[str] = Field(None, alias="mmsName", description="MMS name")
    image_url: Optional[str] = Field(None, alias="imageUrl", description="URL to stored face image")
    distance: float = Field(..., description="IP similarity score (higher = more similar)")


class FaceValidationResponse(BaseModel):
    """Face validation response — indicates whether a duplicate exists"""

    model_config = ConfigDict(populate_by_name=True)

    is_duplicate: bool = Field(..., alias="isDuplicate", description="True if duplicate(s) found above threshold")
    duplicates: List[FaceDuplicateMatch] = Field(..., description="List of duplicate matches")


class HealthCheckResponse(BaseModel):
    """Health check response"""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(..., description="Current timestamp")


class ErrorDetail(BaseModel):
    """Error detail structure"""
    
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[dict] = Field(None, description="Additional error details")


class ErrorResponse(BaseModel):
    """Response model for errors"""
    
    status: str = Field(default="error", description="Response status")
    error: ErrorDetail = Field(..., description="Error details")


class MetricsResponse(BaseModel):
    """Metrics response"""
    
    total_faces: int = Field(..., description="Total number of faces in database")
    collection_name: str = Field(..., description="Milvus collection name")
    service_type: str = Field(default="dedup", description="Service type")
