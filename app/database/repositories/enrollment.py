"""Repository for enrollment and fraud detection operations"""

from typing import List, Optional, Dict, Any

import structlog
from sqlalchemy.sql import func

from app.database.models.enrollment import EnrolledFace, FraudCase
from app.database.repositories import GenericRepository
from app.database.specifications.criteria import QueryOperator, Filter

logger = structlog.get_logger(__name__)


class EnrolledFaceRepository(GenericRepository[EnrolledFace]):
    """Specialized repository for EnrolledFace operations"""

    def __init__(self):
        super().__init__(EnrolledFace)

    def find_by_nik(self, nik: str) -> List[EnrolledFace]:
        """Find enrolled faces by NIK"""
        return self.find_by(nik=nik)

    def find_by_sentra_id(self, sentra_id: str) -> List[EnrolledFace]:
        """Find enrolled faces by Sentra ID"""
        return self.find_by(sentra_id=sentra_id)

    def find_by_milvus_id(self, milvus_id: str) -> Optional[EnrolledFace]:
        """Find enrolled face by Milvus ID"""
        faces = self.find_by(milvus_id=milvus_id)
        return faces[0] if faces else None

    def find_by_milvus_ids(self, milvus_ids: List[str]) -> List[EnrolledFace]:
        """Find enrolled faces by multiple Milvus IDs (batch query)"""
        try:
            if not milvus_ids:
                return []

            with self.db_client.get_session() as session:
                faces = session.query(self.model).filter(
                    self.model.milvus_id.in_(milvus_ids)
                ).all()
                logger.debug("batch_find_by_milvus_ids", count=len(faces), requested=len(milvus_ids))
                return faces
        except Exception as e:
            logger.error("find_by_milvus_ids_failed", error=str(e))
            raise

    def find_by_fraud_status(self, fraud_status: str) -> List[EnrolledFace]:
        """Find enrolled faces by fraud status"""
        return self.find_by(fraud_status=fraud_status)

    def find_pending_fraud_checks(self, limit: int = 100, scheduler_id: int = None, total_schedulers: int = None) -> \
    List[EnrolledFace]:
        """Find faces pending fraud check with optional modulo distribution
        
        Args:
            limit: Maximum number of faces to return
            scheduler_id: Scheduler ID (0-indexed) for concurrent processing
            total_schedulers: Total number of concurrent schedulers
        """
        try:
            with self.db_client.get_session() as session:
                query = session.query(self.model).filter(
                    self.model.check_status == 'pending'
                )

                # Add modulo filter if scheduler distribution is configured
                if scheduler_id is not None and total_schedulers and total_schedulers > 1:
                    query = query.filter(
                        (self.model.id % total_schedulers) == scheduler_id
                    )
                    logger.debug("modulo_filter_applied", scheduler_id=scheduler_id, total_schedulers=total_schedulers)

                faces = query.order_by(self.model.created_at.asc()).limit(limit).all()
                return faces
        except Exception as e:
            logger.error("find_pending_fraud_checks_failed", error=str(e))
            raise

    def find_processing_faces(self, processor_id: str = None) -> List[EnrolledFace]:
        """Find faces currently being processed"""
        if processor_id:
            return self.find_by(check_status='processing', processing_by=processor_id)
        else:
            return self.find_by(check_status='processing')

    def update_to_processing(self, face: EnrolledFace, processor_id: str) -> EnrolledFace:
        """Update face status to processing"""
        try:
            with self.db_client.get_session() as session:
                face.check_status = 'processing'
                face.processing_by = processor_id
                face.processing_started_at = func.now()
                face.processing_attempts += 1
                session.add(face)
                session.commit()
                session.refresh(face)
                return face
        except Exception as e:
            logger.error("update_to_processing_failed", face_id=face.id, error=str(e))
            raise

    def bulk_update_to_processing(self, faces: List[EnrolledFace], processor_id: str) -> int:
        """Bulk update multiple faces to processing status (optimized for batch)"""
        try:
            if not faces:
                return 0

            with self.db_client.get_session() as session:
                face_ids = [face.id for face in faces]
                count = session.query(self.model).filter(
                    self.model.id.in_(face_ids)
                ).update({
                    self.model.check_status: 'processing',
                    self.model.processing_by: processor_id,
                    self.model.processing_started_at: func.now(),
                    self.model.processing_attempts: self.model.processing_attempts + 1
                }, synchronize_session=False)
                session.commit()
                logger.info("bulk_update_to_processing_completed", count=count, processor_id=processor_id)
                return count
        except Exception as e:
            logger.error("bulk_update_to_processing_failed", face_count=len(faces), error=str(e))
            raise

    def update_check_result(self, face: EnrolledFace, fraud_status: str, error_msg: str = None) -> EnrolledFace:
        """Update face after fraud check is completed"""
        try:
            with self.db_client.get_session() as session:
                face.check_status = 'checked'
                face.fraud_status = fraud_status
                face.last_checked_at = func.now()
                if error_msg:
                    face.last_error = error_msg
                session.add(face)
                session.commit()
                session.refresh(face)
                return face
        except Exception as e:
            logger.error("update_check_result_failed", face_id=face.id, error=str(e))
            raise

    def reset_to_pending(self, face: EnrolledFace, error_msg: str) -> EnrolledFace:
        """Reset face to pending for retry"""
        try:
            with self.db_client.get_session() as session:
                face.check_status = 'pending'
                face.last_error = error_msg
                session.add(face)
                session.commit()
                session.refresh(face)
                return face
        except Exception as e:
            logger.error("reset_to_pending_failed", face_id=face.id, error=str(e))
            raise

    def get_paginated(
            self,
            page: int = 1,
            page_size: int = 10,
            nik: str = None,
            sentra_id: str = None,
            fraud_status: str = None,
            check_status: str = None,
            sort_by: str = "created_at",
            sort_asc: bool = False
    ) -> Dict[str, Any]:
        """Get paginated enrolled faces with optional filters and sorting"""
        filters = [
            Filter(field="nik", operator=QueryOperator.EQUALS, value=nik) if nik else None,
            Filter(field="sentra_id", operator=QueryOperator.EQUALS, value=sentra_id) if sentra_id else None,
            Filter(field="fraud_status", operator=QueryOperator.EQUALS, value=fraud_status) if fraud_status else None,
            Filter(field="check_status", operator=QueryOperator.EQUALS, value=check_status) if check_status else None,
        ]
        filters = [f for f in filters if f]

        return self.paginate(
            filters=filters,
            sorts=[(sort_by, sort_asc)],
            page=page,
            page_size=page_size
        )


class FraudCaseRepository(GenericRepository[FraudCase]):
    """Specialized repository for FraudCase operations"""

    def __init__(self):
        super().__init__(FraudCase)

    def find_by_enrollment_id(self, enrollment_id: int) -> List[FraudCase]:
        """Find fraud cases involving specific enrollment ID"""
        try:
            with self.db_client.get_session() as session:
                cases = session.query(self.model).filter(
                    (self.model.primary_enrollment_id == enrollment_id) |
                    (self.model.duplicate_enrollment_id == enrollment_id)
                ).all()
                return cases
        except Exception as e:
            logger.error("find_fraud_cases_by_enrollment_failed", enrollment_id=enrollment_id, error=str(e))
            raise

    def find_high_distance_cases(self, min_distance: float = 0.9) -> List[FraudCase]:
        """Find fraud cases with high distance scores (IP metric)"""
        try:
            with self.db_client.get_session() as session:
                cases = session.query(self.model).filter(
                    self.model.distance >= min_distance
                ).order_by(self.model.distance.desc()).all()
                return cases
        except Exception as e:
            logger.error("find_high_distance_cases_failed", error=str(e))
            raise

    def check_existing_fraud_case(self, primary_id: int, duplicate_id: int) -> Optional[FraudCase]:
        """Check if fraud case already exists between two enrollments"""
        try:
            with self.db_client.get_session() as session:
                case = session.query(self.model).filter(
                    self.model.primary_enrollment_id == primary_id,
                    self.model.duplicate_enrollment_id == duplicate_id
                ).first()
                return case
        except Exception as e:
            logger.error("check_existing_fraud_case_failed", error=str(e))
            raise

    def check_existing_fraud_cases_batch(self, primary_id: int, duplicate_ids: List[int]) -> List[FraudCase]:
        """Check existing fraud cases for multiple duplicates (batch query)"""
        try:
            if not duplicate_ids:
                return []

            with self.db_client.get_session() as session:
                cases = session.query(self.model).filter(
                    self.model.primary_enrollment_id == primary_id,
                    self.model.duplicate_enrollment_id.in_(duplicate_ids)
                ).all()
                logger.debug("batch_check_fraud_cases", primary_id=primary_id, duplicates_count=len(duplicate_ids),
                             existing_count=len(cases))
                return cases
        except Exception as e:
            logger.error("check_existing_fraud_cases_batch_failed", error=str(e))
            raise

    def bulk_create_fraud_cases(self, fraud_cases: List[Dict[str, Any]]) -> int:
        """Bulk create fraud case records (optimized for batch insert)
        
        Args:
            fraud_cases: List of dicts with keys:
                - primary_enrollment_id
                - duplicate_enrollment_id
                - distance
        
        Returns:
            Number of fraud cases created
        """
        try:
            if not fraud_cases:
                return 0

            with self.db_client.get_session() as session:
                # Create FraudCase objects
                fraud_case_objs = [
                    FraudCase(
                        primary_enrollment_id=case["primary_enrollment_id"],
                        duplicate_enrollment_id=case["duplicate_enrollment_id"],
                        distance=case["distance"]
                    )
                    for case in fraud_cases
                ]

                # Bulk insert
                session.add_all(fraud_case_objs)
                session.commit()

                logger.info("bulk_create_fraud_cases_completed", count=len(fraud_case_objs))
                return len(fraud_case_objs)
        except Exception as e:
            logger.error("bulk_create_fraud_cases_failed", count=len(fraud_cases), error=str(e))
            raise
