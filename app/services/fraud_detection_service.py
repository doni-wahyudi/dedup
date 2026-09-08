"""Service for fraud detection and duplicate face checking

Clean architecture with clear separation of concerns:
- Level 1: Main orchestrator (process_fraud_detection_batch)
- Level 2: Phase handlers (_get_pending_faces, _check_duplicates_batch, etc.)
- Level 3: Specific operations (small, focused functions)
"""

from typing import List, Dict, Optional, TypedDict

import structlog

from app.config.settings import settings
from app.core.milvus import MilvusClient
from app.database.models.enrollment import EnrolledFace
from app.database.repositories.enrollment import EnrolledFaceRepository, FraudCaseRepository
from app.utils.exceptions import DatabaseError

logger = structlog.get_logger(__name__)


class CheckResult(TypedDict):
    """Result from checking a single face"""
    is_fraud: bool
    fraud_count: int
    error: Optional[str]


class FraudDetectionService:
    """Service for detecting duplicate faces (fraud detection)
    
    Main flow:
    1. Get pending faces from database
    2. Mark them as processing (lock)
    3. Check for duplicates in Milvus
    4. Process results and update database
    5. Return statistics
    """
    
    MAX_RETRY_ATTEMPTS = 3
    
    def __init__(self):
        self.enrollment_repo = EnrolledFaceRepository()
        self.fraud_repo = FraudCaseRepository()
        self.milvus_client: Optional[MilvusClient] = None
        self.batch_size = settings.fraud_detector_batch_size
        self.fraud_threshold = settings.fraud_detector_threshold
        self.top_k = settings.fraud_detector_top_k
        # Scheduler configuration for concurrent processing
        self.scheduler_id: Optional[int] = None
        self.total_schedulers: Optional[int] = None
    
    def set_milvus_client(self, milvus_client: MilvusClient):
        """Set Milvus client instance"""
        self.milvus_client = milvus_client
    
    def set_scheduler(self, scheduler_id: int, total_schedulers: int):
        """Set scheduler configuration for concurrent processing
        
        Args:
            scheduler_id: Scheduler ID (0-indexed)
            total_schedulers: Total number of schedulers
        """
        if scheduler_id < 0 or scheduler_id >= total_schedulers:
            raise ValueError(f"scheduler_id must be between 0 and {total_schedulers-1}")
        self.scheduler_id = scheduler_id
        self.total_schedulers = total_schedulers
        logger.info("scheduler_configured", scheduler_id=scheduler_id, total_schedulers=total_schedulers)
    
    # ============================================================================
    # LEVEL 1: MAIN ORCHESTRATOR
    # ============================================================================
    
    def process_fraud_detection_batch(self) -> Dict[str, int]:
        """Main entry point - orchestrates the entire fraud detection flow
        
        Returns:
            Statistics dictionary with keys:
            - processed: Successfully checked faces
            - fraud_detected: Faces with duplicates found
            - clean: Faces with no duplicates
            - errors: Faces that failed to process
            - fraud_cases_created: Total fraud cases created
        """
        stats = {
            "processed": 0,
            "fraud_detected": 0,
            "clean": 0,
            "errors": 0,
            "fraud_cases_created": 0
        }
        pending_faces = []
        
        try:
            # Phase 1: Get pending faces
            pending_faces = self._get_pending_faces()
            if not pending_faces:
                logger.info("no_pending_faces")
                return stats
            
            logger.info("batch_started", batch_size=len(pending_faces))
            
            # Phase 2: Mark as processing (lock mechanism)
            self._mark_as_processing(pending_faces)
            
            # Phase 3: Check for duplicates (core logic)
            check_results = self._check_duplicates_batch(pending_faces)
            
            # Phase 4: Process results and update database
            stats = self._process_results(pending_faces, check_results, stats)
            
            logger.info("batch_completed", **stats)
            return stats
            
        except Exception as e:
            logger.error("batch_failed", error=str(e), batch_size=len(pending_faces))
            self._handle_batch_error(pending_faces)
            return stats
    
    # ============================================================================
    # LEVEL 2: PHASE HANDLERS
    # ============================================================================
    
    def _get_pending_faces(self) -> List[EnrolledFace]:
        """Phase 1: Get faces that need fraud checking
        
        Returns faces with status='pending' ordered by creation time.
        Uses modulo distribution if scheduler_id is configured.
        """
        try:
            faces = self.enrollment_repo.find_pending_fraud_checks(
                limit=self.batch_size,
                scheduler_id=self.scheduler_id,
                total_schedulers=self.total_schedulers
            )
            logger.info(
                "pending_faces_retrieved",
                count=len(faces),
                scheduler_id=self.scheduler_id,
                total_schedulers=self.total_schedulers
            )
            return faces
        except Exception as e:
            logger.error("get_pending_faces_failed", error=str(e))
            raise
    
    def _mark_as_processing(self, faces: List[EnrolledFace]) -> None:
        """Phase 2: Mark faces as processing to prevent concurrent processing
        
        Updates status to 'processing' and increments attempts counter
        """
        try:
            self.enrollment_repo.bulk_update_to_processing(faces, processor_id="fraud_detector")
            logger.info("faces_marked_processing", count=len(faces))
        except Exception as e:
            logger.error("mark_processing_failed", error=str(e))
            raise
    
    def _check_duplicates_batch(self, faces: List[EnrolledFace]) -> List[CheckResult]:
        """Phase 3: Core fraud detection - check all faces for duplicates
        
        Steps:
        1. Get embeddings from Milvus
        2. Batch search for similar faces
        3. Process results for each face
        
        Returns:
            List of CheckResult, one per input face
        """
        results: List[CheckResult] = []
        
        try:
            # Step 3A: Get embeddings from Milvus
            embeddings_map = self._get_embeddings_from_milvus(faces)
            
            # Step 3B: Batch search for similar faces
            search_results = self._batch_search_similar_faces(faces, embeddings_map)
            
            # Step 3C: Process results for each face
            for face, matches in zip(faces, search_results):
                result = self._check_single_face(face, matches)
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error("check_duplicates_failed", error=str(e))
            # Return error result for all faces
            return [{"is_fraud": False, "fraud_count": 0, "error": str(e)} for _ in faces]
    
    def _process_results(
        self,
        faces: List[EnrolledFace],
        results: List[CheckResult],
        stats: Dict[str, int]
    ) -> Dict[str, int]:
        """Phase 4: Process check results and update database
        
        Handles both success and error cases for each face
        """
        for face, result in zip(faces, results):
            try:
                if result.get("error"):
                    # Handle error case
                    self._handle_face_error(face, result["error"], stats)
                else:
                    # Handle success case
                    self._handle_face_success(face, result, stats)
                    
            except Exception as e:
                logger.error(
                    "process_result_failed",
                    face_id=face.id,
                    error=str(e)
                )
                self._handle_face_error(face, str(e), stats)
        
        return stats
    
    # ============================================================================
    # LEVEL 3: SPECIFIC OPERATIONS
    # ============================================================================
    
    def _get_embeddings_from_milvus(
        self,
        faces: List[EnrolledFace]
    ) -> Dict[str, List[float]]:
        """Get face embeddings from Milvus by IDs
        
        Returns:
            Dictionary mapping milvus_id -> embedding vector
        """
        if not self.milvus_client:
            raise DatabaseError("Milvus client not initialized")
        
        milvus_ids = [face.milvus_id for face in faces]
        
        # Get embeddings using milvus get_by_ids
        results = self.milvus_client.get_by_ids(
            ids=milvus_ids,
            output_fields=["id", "embedding"]
        )
        
        # Convert to dict for easy lookup
        embeddings_map = {
            str(item["id"]): item["embedding"]
            for item in results
            if item.get("embedding")
        }
        
        logger.debug("embeddings_retrieved", count=len(embeddings_map))
        return embeddings_map
    
    def _batch_search_similar_faces(
        self,
        faces: List[EnrolledFace],
        embeddings_map: Dict[str, List[float]]
    ) -> List[List[Dict]]:
        """Batch search for similar faces in Milvus
        
        Returns:
            List of match lists, one per input face
        """
        if not self.milvus_client:
            raise DatabaseError("Milvus client not initialized")
        
        # Prepare query vectors (maintain order)
        query_vectors = [embeddings_map[face.milvus_id] for face in faces]
        
        # Batch search in Milvus
        search_results = self.milvus_client.batch_search_similar_faces(
            query_vectors=query_vectors,
            limit=self.top_k,
            distance=None  # We'll filter by threshold later
        )
        
        logger.debug("batch_search_completed", queries=len(query_vectors))
        return search_results
    
    def _check_single_face(
        self,
        face: EnrolledFace,
        matches: List[Dict]
    ) -> CheckResult:
        """Check a single face for duplicates
        
        Steps:
        1. Filter out self-matches
        2. Filter by distance threshold
        3. Create fraud cases if duplicates found
        """
        try:
            # Filter duplicates
            duplicates = self._filter_duplicates(face, matches)
            
            if duplicates:
                # Create fraud cases
                fraud_count = self._create_fraud_cases(face, duplicates)
                
                logger.info(
                    "duplicates_found",
                    face_id=face.id,
                    nik=face.nik,
                    duplicate_count=len(duplicates)
                )
                
                return {
                    "is_fraud": True,
                    "fraud_count": fraud_count,
                    "error": None
                }
            else:
                return {
                    "is_fraud": False,
                    "fraud_count": 0,
                    "error": None
                }
                
        except Exception as e:
            logger.error("check_single_face_failed", face_id=face.id, error=str(e))
            return {
                "is_fraud": False,
                "fraud_count": 0,
                "error": str(e)
            }
    
    def _filter_duplicates(
        self,
        face: EnrolledFace,
        matches: List[Dict]
    ) -> List[Dict]:
        """Filter matches to find actual duplicates
        
        Filters:
        1. Remove self-match (same milvus_id)
        2. Only keep matches >= threshold
        """
        duplicates = []
        
        for match in matches:
            match_id = str(match["id"])
            distance = match["distance"]
            
            # Skip self-match
            if match_id == face.milvus_id:
                continue
            
            # Check threshold (IP metric: higher = more similar)
            if distance >= self.fraud_threshold:
                duplicates.append(match)
        
        return duplicates
    
    def _create_fraud_cases(
        self,
        face: EnrolledFace,
        duplicates: List[Dict]
    ) -> int:
        """Create fraud case records for detected duplicates
        
        Bulk optimization: batch insert all fraud cases in one DB query
        instead of N separate inserts.
        
        Returns:
            Number of fraud cases created
        """
        if not duplicates:
            return 0
        
        try:
            # Batch query: get all duplicate faces in one DB call
            duplicate_milvus_ids = [str(d["id"]) for d in duplicates]
            duplicate_faces_list = self.enrollment_repo.find_by_milvus_ids(duplicate_milvus_ids)
            
            # Convert to map for O(1) lookup
            duplicate_faces_map = {face.milvus_id: face for face in duplicate_faces_list}
            
            # Prepare fraud case records for bulk insert
            fraud_cases_to_create = []
            for duplicate in duplicates:
                duplicate_milvus_id = str(duplicate["id"])
                duplicate_face = duplicate_faces_map.get(duplicate_milvus_id)
                
                if duplicate_face:
                    fraud_cases_to_create.append({
                        "primary_enrollment_id": face.id,
                        "duplicate_enrollment_id": duplicate_face.id,
                        "distance": duplicate["distance"]
                    })
            
            # Bulk insert all at once (1 DB query)
            if fraud_cases_to_create:
                return self.fraud_repo.bulk_create_fraud_cases(fraud_cases_to_create)
            
            return 0
                        
        except Exception as e:
            logger.error(
                "create_fraud_cases_failed",
                face_id=face.id,
                duplicate_count=len(duplicates),
                error=str(e)
            )
            raise
    
    def _handle_face_success(
        self,
        face: EnrolledFace,
        result: CheckResult,
        stats: Dict[str, int]
    ) -> None:
        """Handle successful fraud check for a face"""
        is_fraud = result["is_fraud"]
        fraud_count = result["fraud_count"]
        
        # Determine fraud status
        fraud_status = "fraud" if is_fraud else "clean"
        
        # Update face in database
        self.enrollment_repo.update_check_result(
            face=face,
            fraud_status=fraud_status
        )
        
        # Update statistics
        stats["processed"] += 1
        if is_fraud:
            stats["fraud_detected"] += 1
            stats["fraud_cases_created"] += fraud_count
        else:
            stats["clean"] += 1
    
    def _handle_face_error(
        self,
        face: EnrolledFace,
        error: str,
        stats: Dict[str, int]
    ) -> None:
        """Handle error case for a face - implements retry logic
        
        Retry logic:
        - If attempts < MAX_RETRY_ATTEMPTS: reset to pending
        - If attempts >= MAX_RETRY_ATTEMPTS: mark as failed with error status
        """
        stats["errors"] += 1
        
        # Get current attempts (after marking as processing)
        current_attempts = getattr(face, 'processing_attempts', 0)
        
        if current_attempts >= self.MAX_RETRY_ATTEMPTS:
            # Give up - mark as failed with error status
            self.enrollment_repo.update_check_result(
                face=face,
                fraud_status="error",
                error_msg=error
            )
            logger.warning(
                "fraud_check_given_up",
                face_id=face.id,
                attempts=current_attempts,
                error=error
            )
        else:
            # Retry - reset to pending
            self.enrollment_repo.reset_to_pending(face, error_msg=error)
            logger.info(
                "fraud_check_retry_scheduled",
                face_id=face.id,
                attempts=current_attempts,
                error=error
            )
    
    def _handle_batch_error(self, faces: List[EnrolledFace]) -> None:
        """Handle batch-level error - reset all faces appropriately"""
        for face in faces:
            try:
                current_attempts = getattr(face, 'processing_attempts', 0)
                
                if current_attempts >= self.MAX_RETRY_ATTEMPTS:
                    # Give up - mark as error
                    self.enrollment_repo.update_check_result(
                        face=face,
                        fraud_status="error",
                        error_msg="Batch error - max retries reached"
                    )
                else:
                    # Retry
                    self.enrollment_repo.reset_to_pending(face, error_msg="Batch error")
                    
            except Exception as e:
                logger.error(
                    "handle_batch_error_failed",
                    face_id=face.id,
                    error=str(e)
                )
    


# Global instance
fraud_detection_service = FraudDetectionService()
