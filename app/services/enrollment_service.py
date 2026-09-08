"""Service for enrollment management operations"""

from typing import Optional

import structlog

from app.database.repositories.enrollment import EnrolledFaceRepository
from app.models.schemas import EnrolledFaceSchema, PaginatedResponse, PaginationMetadata
from app.utils.exceptions import DedupServiceError

logger = structlog.get_logger(__name__)


class EnrollmentService:
    """Service layer for enrollment business logic"""

    def __init__(self):
        self.enrolled_face_repo = EnrolledFaceRepository()

    def list_enrollments(
            self,
            page: int = 1,
            page_size: int = 10,
            nik: Optional[str] = None,
            sentra_id: Optional[str] = None,
            fraud_status: Optional[str] = None,
            check_status: Optional[str] = None,
            sort_by: str = "created_at",
            sort_asc: bool = False,
    ) -> PaginatedResponse[EnrolledFaceSchema]:
        """Get paginated list of enrolled faces with optional filters and sorting"""
        result = self.enrolled_face_repo.get_paginated(
            page=page,
            page_size=page_size,
            nik=nik,
            sentra_id=sentra_id,
            fraud_status=fraud_status,
            check_status=check_status,
            sort_by=sort_by,
            sort_asc=sort_asc,
        )

        faces_schemas = [EnrolledFaceSchema.model_validate(face) for face in result["data"]]

        return PaginatedResponse(
            content=faces_schemas,
            pagination=PaginationMetadata(**result["pagination"]),
        )

    def get_enrollment_by_id(self, enrollment_id: int) -> EnrolledFaceSchema:
        """Get enrollment detail by ID.

        Raises:
            DedupServiceError: If enrollment is not found.
        """
        enrollment = self.enrolled_face_repo.get(enrollment_id)

        if not enrollment:
            raise DedupServiceError(f"Enrollment with ID {enrollment_id} not found")

        return EnrolledFaceSchema.model_validate(enrollment)
