import time
from typing import Optional

import structlog

from app.config.settings import settings
from app.core.insightface import InsightFaceClient
from app.core.milvus import milvus_client
from app.middleware.correlation_id import get_source_channel
from app.models.schemas import FaceSearchResponse, FaceMatch, FaceDuplicateMatch, FaceValidationResponse, FaceCompareResponse
from app.utils.exceptions import DedupServiceError

logger = structlog.get_logger(__name__)


class DedupService:
    """Service for deduplication and face search operations"""
    
    def __init__(self):
        self.insightface_client = InsightFaceClient()
        self.milvus_client = milvus_client
    
    def search_similar_faces(
        self,
        image_data: bytes,
        filename: str,
        limit: int = 10,
        sentra_id: Optional[str] = None,
        distance: Optional[float] = None,
        channel: Optional[str] = None,
    ) -> FaceSearchResponse:
        """Search for similar faces using provider-specific distance matching
        
        Args:
            image_data: Face image bytes
            filename: Original filename
            limit: Maximum results to return
            sentra_id: Optional Sentra ID filter
            distance: Optional distance filter for results
            channel: Optional source channel identifier
        
        Returns:
            FaceSearchResponse with matches sorted by distance, filtered if specified
        """
        start_time = time.time()
        effective_channel = channel or get_source_channel() or None
        
        try:
            # Extract face embedding
            embedding_start = time.time()
            embedding, metadata = self.insightface_client.process_image(image_data, filename)
            if embedding is None:
                raise DedupServiceError("No face detected in image")
            embedding_ms = (time.time() - embedding_start) * 1000
            
            logger.info(
                "query_embedding_extracted",
                embedding_dimension=len(embedding),
                filename=filename,
                source_channel=effective_channel,
            )
            
            # Search top K similar faces in Milvus
            milvus_start = time.time()
            search_results = self.milvus_client.search_similar_faces(
                query_vector=embedding,
                limit=limit,
                sentra_id=sentra_id,
                distance=distance
            )
            milvus_ms = (time.time() - milvus_start) * 1000
            
            matches = []
            for result in search_results:
                match = FaceMatch(
                    id=str(result["id"]),
                    nik=result["nik"],
                    cif_name=result.get("cif_name"),
                    cif_code=result.get("cif_code"),
                    sentra_id=result.get("sentra_id"),
                    sentra_name=result.get("sentra_name"),
                    mms_code=result.get("mms_code"),
                    mms_name=result.get("mms_name"),
                    co_assignment_nik=result.get("co_assignment_nik"),
                    co_assignment_code=result.get("co_assignment_code"),
                    co_assignment_name=result.get("co_assignment_name"),
                    co_enrol_nik=result.get("co_enrol_nik"),
                    co_enrol_code=result.get("co_enrol_code"),
                    co_enrol_name=result.get("co_enrol_name"),
                    enroll_date_time=result.get("enroll_date_time"),
                    image_url=result.get("image_url"),
                    distance=round(result["distance"], 4),
                    enrolled_at=result.get("created_at")
                )
                matches.append(match)
            
            # Calculate search time
            search_time_ms = (time.time() - start_time) * 1000
            
            logger.info(
                "search_completed",
                matches_found=len(matches),
                embedding_ms=round(embedding_ms, 1),
                milvus_ms=round(milvus_ms, 1),
                search_time_ms=round(search_time_ms, 1),
                limit_requested=limit,
                sentra_id_filter=sentra_id,
                source_channel=effective_channel,
            )
            
            return FaceSearchResponse(
                faces=matches,
                total=len(matches),
                search_ms=round(search_time_ms, 1),
                channel=effective_channel,
            )
            
        except DedupServiceError:
            # Re-raise DedupServiceError and its subclasses to preserve error codes
            raise
        except Exception as e:
            logger.error("search_failed", error=str(e))
            raise DedupServiceError(f"Search failed: {str(e)}")

    def validate_face(
        self,
        image_data: bytes,
        filename: str,
        limit: int = 10,
        sentra_id: Optional[str] = None,
        distance: Optional[float] = None,
        channel: Optional[str] = None,
    ) -> FaceValidationResponse:
        """Validate whether a face is a duplicate of an existing enrollment.

        Args:
            image_data: Face image bytes
            filename: Original filename
            limit: Maximum candidates to retrieve from Milvus
            sentra_id: Optional Sentra ID filter
            distance: Minimum similarity threshold (IP metric). Uses default_threshold if None.
            channel: Optional source channel identifier

        Returns:
            FaceValidationResponse with is_duplicate flag and list of matches above threshold
        """
        start_time = time.time()
        threshold = distance if distance is not None else settings.default_threshold
        effective_channel = channel or get_source_channel() or None

        try:
            embedding_start = time.time()
            embedding, metadata = self.insightface_client.process_image(image_data, filename)
            if embedding is None:
                raise DedupServiceError("No face detected in image")
            embedding_ms = (time.time() - embedding_start) * 1000

            milvus_start = time.time()
            search_results = self.milvus_client.search_similar_faces(
                query_vector=embedding,
                limit=limit,
                sentra_id=sentra_id,
                distance=threshold,
            )
            milvus_ms = (time.time() - milvus_start) * 1000

            duplicates = [
                FaceDuplicateMatch(
                    nik=r["nik"],
                    cif_name=r.get("cif_name"),
                    cif_code=r.get("cif_code"),
                    sentra_id=r.get("sentra_id"),
                    sentra_name=r.get("sentra_name"),
                    mms_code=r.get("mms_code"),
                    mms_name=r.get("mms_name"),
                    image_url=r.get("image_url"),
                    distance=round(r["distance"], 4),
                )
                for r in search_results
            ]

            search_ms = round((time.time() - start_time) * 1000, 1)

            logger.info(
                "validate_face_completed",
                is_duplicate=len(duplicates) > 0,
                duplicates_found=len(duplicates),
                threshold=threshold,
                embedding_ms=round(embedding_ms, 1),
                milvus_ms=round(milvus_ms, 1),
                search_time_ms=search_ms,
                source_channel=effective_channel,
            )

            return FaceValidationResponse(
                is_duplicate=len(duplicates) > 0,
                duplicates=duplicates,
                channel=effective_channel,
            )

        except DedupServiceError:
            raise
        except Exception as e:
            logger.error("validate_face_failed", error=str(e))
            raise DedupServiceError(f"Validation failed: {str(e)}")

    def compare_faces(
        self,
        image1_data: bytes,
        image1_filename: str,
        image2_data: bytes,
        image2_filename: str,
        threshold: Optional[float] = None,
        channel: Optional[str] = None,
    ) -> FaceCompareResponse:
        """Compare two face images and return similarity result.

        Performs 1:1 face comparison using cosine similarity on InsightFace
        embeddings. Both images go through the full validation pipeline
        (format check, face detection, single-face enforcement).

        Args:
            image1_data: First face image bytes
            image1_filename: First image filename
            image2_data: Second face image bytes
            image2_filename: Second image filename
            threshold: Optional similarity threshold override
            channel: Optional source channel identifier

        Returns:
            FaceCompareResponse with match status and similarity score
        """
        start_time = time.time()
        effective_threshold = threshold if threshold is not None else settings.face_compare_threshold
        effective_channel = channel or get_source_channel() or None

        try:
            # Process first image (validate format, detect face, extract embedding)
            embedding1, metadata1 = self.insightface_client.process_image(
                image1_data, image1_filename, field="image1"
            )
            if embedding1 is None:
                raise DedupServiceError("image1: No face detected in first image")

            # Process second image (same pipeline)
            embedding2, metadata2 = self.insightface_client.process_image(
                image2_data, image2_filename, field="image2"
            )
            if embedding2 is None:
                raise DedupServiceError("image2: No face detected in second image")

            # Compare embeddings using cosine similarity
            is_match, similarity = self.insightface_client.verify_face_match(
                embedding1, embedding2, tolerance=effective_threshold
            )

            processing_time_ms = round((time.time() - start_time) * 1000, 1)

            logger.info(
                "face_compare_completed",
                is_match=is_match,
                similarity=round(similarity, 4),
                threshold=effective_threshold,
                processing_time_ms=processing_time_ms,
                source_channel=effective_channel,
            )

            return FaceCompareResponse(
                is_match=is_match,
                status="Match" if is_match else "No Match",
                similarity_score=round(similarity, 4),
                threshold=effective_threshold,
                processing_time_ms=processing_time_ms,
                channel=effective_channel,
            )

        except DedupServiceError:
            raise
        except Exception as e:
            logger.error("face_compare_failed", error=str(e))
            raise DedupServiceError(f"Face comparison failed: {str(e)}")


# Global instance
dedup_service = DedupService()