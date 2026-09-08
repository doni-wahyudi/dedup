"""API endpoints for enrollment management"""

from typing import Optional

import structlog
from fastapi import APIRouter, Query, HTTPException, status

from app.models.schemas import EnrolledFaceSchema, PaginatedResponse
from app.services.enrollment_service import EnrollmentService
from app.utils.exceptions import DedupServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/enrollments", tags=["enrollments"])
enrollment_service = EnrollmentService()


@router.get("/", response_model=PaginatedResponse[EnrolledFaceSchema])
async def list_enrollments(
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(10, ge=1, le=100, description="Items per page"),
        nik: Optional[str] = Query(None, description="Filter by NIK"),
        sentra_id: Optional[str] = Query(None, description="Filter by Sentra ID"),
        fraud_status: Optional[str] = Query(None, description="Filter by fraud status (clean, fraud, suspected)"),
        check_status: Optional[str] = Query(None, description="Filter by check status (pending, processing, checked)"),
        sort_by: str = Query("created_at", description="Sort field"),
        sort_asc: bool = Query(False, description="Sort ascending (default: descending)")
):
    """
    Get paginated list of enrolled faces with optional filters and sorting.
    
    **Parameters:**
    - `page`: Page number (1-indexed)
    - `page_size`: Number of items per page (max 100)
    - `nik`: Filter by NIK
    - `sentra_id`: Filter by Sentra ID
    - `fraud_status`: Filter by fraud status
    - `check_status`: Filter by check status
    - `sort_by`: Field to sort by (default: created_at)
    - `sort_asc`: Sort in ascending order (default: descending)
    """
    try:
        return enrollment_service.list_enrollments(
            page=page,
            page_size=page_size,
            nik=nik,
            sentra_id=sentra_id,
            fraud_status=fraud_status,
            check_status=check_status,
            sort_by=sort_by,
            sort_asc=sort_asc,
        )
    except Exception as e:
        logger.error("list_enrollments_failed", error=str(e), page=page, page_size=page_size)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list enrollments"
        )


@router.get("/{enrollment_id}", response_model=EnrolledFaceSchema)
async def get_enrollment_by_id(enrollment_id: int):
    """
    Get enrollment detail by ID.
    
    **Parameters:**
    - `enrollment_id`: Enrollment ID
    
    **Returns:**
    - Enrollment details
    
    **Raises:**
    - 404: Enrollment not found
    """
    try:
        return enrollment_service.get_enrollment_by_id(enrollment_id)
    except DedupServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("get_enrollment_by_id_failed", error=str(e), enrollment_id=enrollment_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get enrollment"
        )
