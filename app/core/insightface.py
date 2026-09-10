"""Face detection and embedding extraction using InsightFace"""

import io
import os
from typing import Tuple, Optional, List, Dict, Any

import cv2
import numpy as np
import structlog
from PIL import Image

from app.config.settings import settings
from app.core.quality import ImageQualityValidator
from app.utils.exceptions import (
    FaceDetectionError,
    MultipleFacesError,
    InvalidImageError,
    UnsupportedImageFormatError,
    ImageTooLargeError,
    EmbeddingExtractionError,
    DatabaseError,
    ImageResolutionError,
    ImageBlurError,
    ImageLightingError,
    FaceTooSmallError,
    FaceNotFullyVisibleError,
    FaceOccludedError,
)

logger = structlog.get_logger(__name__)

_WARMUP_IMAGE_SIZE = 640


class InsightFaceClient:
    """Client for face detection, embedding extraction, and verification using InsightFace"""

    def __init__(self):
        """Initialize InsightFace models"""
        try:
            from insightface.app import FaceAnalysis

            self.threshold = settings.face_detection_threshold
            self.max_image_size = settings.image_max_size
            self.allow_multiple_faces = settings.allow_multiple_faces

            # Initialize InsightFace
            self.app = FaceAnalysis(
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )

            # ctx_id: 0 for GPU, -1 for CPU
            # det_size: detection size (640x640 is good balance)
            self.gpu_available = self._check_gpu_available()
            ctx_id = 0 if self.gpu_available else -1
            self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))

            logger.info(
                "insightface_initialized",
                provider="insightface",
                gpu_available=self.gpu_available,
                det_size=(640, 640)
            )

        except ImportError as e:
            logger.error("insightface_import_failed", error=str(e))
            raise ImportError(
                "InsightFace not installed. Install with: pip install insightface onnxruntime-gpu"
            )
        except Exception as e:
            logger.error("insightface_initialization_failed", error=str(e))
            raise

    def _check_gpu_available(self) -> bool:
        """Check if GPU is available for ONNX Runtime"""
        try:
            import onnxruntime as ort
            available_providers = ort.get_available_providers()
            gpu_available = 'CUDAExecutionProvider' in available_providers

            logger.info(
                "onnxruntime_providers",
                available=available_providers,
                gpu_available=gpu_available
            )

            return gpu_available
        except Exception as e:
            logger.warning("gpu_check_failed", error=str(e))
            return False

    def warmup(self) -> None:
        """Warm up model runtime.

        Uses an optional real-face image from INSIGHTFACE_WARMUP_IMAGE_PATH for full
        detector+recognizer warmup. Falls back to detector-only warmup with dummy image.
        """
        warmup_image_path = os.getenv("INSIGHTFACE_WARMUP_IMAGE_PATH")

        if warmup_image_path:
            try:
                with open(warmup_image_path, "rb") as f:
                    file_data = f.read()

                # Full pipeline warmup: validate -> preprocess -> detect -> embedding
                self.process_image(file_data=file_data, filename=os.path.basename(warmup_image_path))
                logger.info(
                    "insightface_warmup_completed",
                    mode="full_pipeline",
                    warmup_image_path=warmup_image_path,
                )
                return
            except Exception as e:
                logger.warning(
                    "insightface_full_warmup_failed",
                    warmup_image_path=warmup_image_path,
                    error=str(e),
                )

        try:
            dummy = np.zeros((_WARMUP_IMAGE_SIZE, _WARMUP_IMAGE_SIZE, 3), dtype=np.uint8)
            faces = self.app.get(dummy)
            logger.info(
                "insightface_warmup_completed",
                mode="detector_only",
                detected_faces=len(faces),
                image_size=_WARMUP_IMAGE_SIZE,
            )
        except Exception as e:
            logger.warning("insightface_warmup_failed", error=str(e))

    def validate_image_format(self, file_data: bytes, filename: str, field: Optional[str] = None) -> None:
        """Validate image format and size"""
        prefix = f"{field} ({filename}): " if field and filename else (f"{field}: " if field else "")
        # Check if file is empty
        file_size = len(file_data)
        if file_size == 0:
            raise InvalidImageError(
                message=f"{prefix}Image file is empty",
                details={"filename": filename, **({"field": field} if field else {})}
            )

        # Check file size
        if file_size > settings.max_upload_size:
            raise ImageTooLargeError(
                file_size=file_size,
                max_size=settings.max_upload_size
            )

        # Check file extension
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in settings.image_extensions_set:
            raise UnsupportedImageFormatError(
                format_detected=file_ext,
                message=f"{prefix}File extension {file_ext} not supported"
            )

        # Try to open and verify image
        try:
            image = Image.open(io.BytesIO(file_data))
            image_format = image.format

            if image_format not in settings.image_formats_set:
                raise UnsupportedImageFormatError(
                    format_detected=image_format,
                    message=f"{prefix}Image format {image_format} not supported"
                )

            # Check minimum image resolution
            if settings.quality_validation_enabled:
                ImageQualityValidator.validate_resolution(
                    width=image.size[0],
                    height=image.size[1],
                    field=field,
                    filename=filename
                )

            # Verify image is not corrupted
            image.verify()

            logger.info(
                "image_validated",
                format=image_format,
                size_bytes=file_size,
                dimensions=image.size
            )

        except (UnsupportedImageFormatError, ImageTooLargeError, ImageResolutionError):
            raise
        except Exception as e:
            logger.error("image_validation_failed", error=str(e))
            raise InvalidImageError(
                message=f"Invalid or corrupted image: {str(e)}",
                details={"filename": filename}
            )

    def preprocess_image(self, file_data: bytes) -> np.ndarray:
        """Preprocess image for InsightFace (needs BGR format)"""
        try:
            # Load image using PIL
            image = Image.open(io.BytesIO(file_data))

            # Convert to RGB
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Convert PIL to numpy array (RGB)
            img_array = np.array(image)

            # Convert RGB to BGR (OpenCV/InsightFace format)
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

            return img_bgr

        except Exception as e:
            logger.error("image_preprocessing_failed", error=str(e))
            raise InvalidImageError(
                message=f"Failed to preprocess image: {str(e)}"
            )

    def _validate_and_select_face(
        self,
        faces: list,
        field: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Tuple[list, int]:
        """Validate face count and select face (largest if multiple)
        
        Args:
            faces: List of detected Face objects from InsightFace
            field: Optional field name (e.g. 'image1' or 'image2')
            filename: Optional filename
            
        Returns:
            Tuple of (validated_faces, face_count)
            
        Raises:
            FaceDetectionError: If no faces detected
            MultipleFacesError: If multiple faces and not allowed
        """
        face_count = len(faces)
        logger.info("faces_detected", count=face_count, provider="insightface", field=field, filename=filename)

        prefix = f"{field} ({filename}): " if field and filename else (f"{field}: " if field else "")
        err_details = {"provider": "insightface", **({"field": field} if field else {}), **({"filename": filename} if filename else {})}

        # Validate face count
        if face_count == 0:
            raise FaceDetectionError(
                message=f"{prefix}No face detected in image",
                details=err_details
            )

        if face_count > 1:
            if not self.allow_multiple_faces:
                # Strict mode: reject multiple faces
                raise MultipleFacesError(
                    face_count=face_count,
                    message=f"{prefix}Multiple faces detected ({face_count}). Please provide image with single face.",
                    details=err_details
                )
            else:
                # Allow mode: select largest face
                logger.info(
                    "multiple_faces_selecting_largest",
                    count=face_count,
                    provider="insightface"
                )
                # Sort faces by bbox area (width * height), largest first
                faces = sorted(
                    faces,
                    key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
                    reverse=True
                )
                logger.info(
                    "largest_face_selected",
                    bbox_area=int((faces[0].bbox[2] - faces[0].bbox[0]) * (faces[0].bbox[3] - faces[0].bbox[1])),
                    total_faces=face_count
                )

        return faces, face_count

    def detect_faces(self, img_array: np.ndarray) -> Tuple[list, int]:
        """Detect faces using InsightFace
        
        Note: InsightFace does detection and embedding extraction together,
        but we keep this method for interface compatibility.
        """
        try:
            # Detect faces (InsightFace returns Face objects with embeddings)
            faces = self.app.get(img_array)

            # Validate and select face
            faces, face_count = self._validate_and_select_face(faces)

            # Return face locations for compatibility
            face_locations = [face.bbox.tolist() for face in faces]

            return face_locations, face_count

        except (FaceDetectionError, MultipleFacesError):
            raise
        except Exception as e:
            logger.error("face_detection_failed", error=str(e))
            raise FaceDetectionError(
                message=f"Face detection failed: {str(e)}",
                details={"provider": "insightface"}
            )

    def extract_embedding(self, img_array: np.ndarray, face_locations: list) -> np.ndarray:
        """Extract face embedding using InsightFace
        
        Note: InsightFace extracts embeddings during detection.
        This method re-runs detection for interface compatibility.
        """
        try:
            # Run detection (includes embedding extraction)
            faces = self.app.get(img_array)

            if not faces or len(faces) == 0:
                raise EmbeddingExtractionError(
                    message="Failed to extract face embedding",
                    details={"provider": "insightface"}
                )

            # Get first (and only) face
            face = faces[0]
            embedding = face.embedding  # 512-dim numpy array

            # Validate embedding shape
            if embedding.shape[0] != 512:
                raise EmbeddingExtractionError(
                    message=f"Invalid embedding shape: {embedding.shape}",
                    details={"expected_shape": (512,), "actual_shape": embedding.shape}
                )

            # Normalize embedding (recommended for cosine similarity)
            norm = float(np.linalg.norm(embedding))
            if norm > 0:
                embedding = embedding / norm

            logger.info(
                "embedding_extracted",
                dimension=embedding.shape[0],
                norm=round(norm, 4),
                confidence=float(face.det_score),
                dtype=str(embedding.dtype),
                provider="insightface"
            )

            return embedding

        except EmbeddingExtractionError:
            raise
        except Exception as e:
            logger.error("embedding_extraction_failed", error=str(e))
            raise EmbeddingExtractionError(
                message=f"Failed to extract embedding: {str(e)}",
                details={"provider": "insightface"}
            )

    def verify_face_match(
            self,
            query_embedding: np.ndarray,
            candidate_embedding: np.ndarray,
            tolerance: float = 0.4,  # InsightFace uses cosine similarity (0.25-0.5 typical)
    ) -> Tuple[bool, float]:
        """Verify if two face embeddings match using cosine similarity
        
        Args:
            query_embedding: Query face embedding (normalized)
            candidate_embedding: Candidate face embedding (normalized)
            tolerance: Similarity threshold (default 0.4)
        
        Returns:
            Tuple of (is_match, similarity)
            
        Note: Higher similarity = more similar (opposite of distance)
        """
        try:
            # Cosine similarity (for normalized vectors, this is just dot product)
            similarity = float(np.dot(query_embedding, candidate_embedding))
            is_match = similarity >= tolerance

            return is_match, similarity

        except Exception as e:
            logger.error("face_verification_failed", error=str(e))
            return False, 0.0

    def process_image(
        self,
        file_data: bytes,
        filename: str,
        field: Optional[str] = None
    ) -> Tuple[np.ndarray, dict]:
        """Complete pipeline: validate, preprocess, detect, extract
        
        For InsightFace, detection and embedding extraction happen together,
        making this more efficient.
        """
        # Step 1: Validate
        self.validate_image_format(file_data, filename, field=field)

        # Step 2: Preprocess
        img_array = self.preprocess_image(file_data)

        # Quality check: Blur & Lighting
        quality_metrics = {}
        if settings.quality_validation_enabled:
            blur_score = ImageQualityValidator.validate_blur(
                img_array,
                field=field,
                filename=filename
            )
            lighting_score = ImageQualityValidator.validate_lighting(
                img_array,
                field=field,
                filename=filename
            )
            quality_metrics["blur_score"] = blur_score
            quality_metrics["brightness"] = lighting_score

        # Step 3 & 4: Detect and extract (combined for efficiency)
        try:
            faces = self.app.get(img_array)

            # Validate and select face
            faces, face_count = self._validate_and_select_face(
                faces,
                field=field,
                filename=filename
            )

            # Get first (and only, or largest) face
            face = faces[0]

            # Quality check: Face integrity & occlusion
            if settings.quality_validation_enabled:
                integrity_metrics = ImageQualityValidator.validate_face_integrity(
                    img_shape=img_array.shape,
                    bbox=face.bbox.tolist(),
                    field=field,
                    filename=filename
                )
                occlusion_metrics = ImageQualityValidator.validate_landmarks_and_occlusion(
                    face,
                    field=field,
                    filename=filename
                )
                quality_metrics.update(integrity_metrics)
                quality_metrics.update(occlusion_metrics)

            embedding = face.embedding

            # Normalize embedding
            norm = float(np.linalg.norm(embedding))
            if norm > 0:
                embedding = embedding / norm

            # Prepare metadata
            metadata = {
                "face_count": face_count,
                "face_location": face.bbox.tolist(),
                "embedding_dimension": embedding.shape[0],
                "image_shape": img_array.shape,
                "confidence": float(face.det_score),
                "provider": "insightface",
                "quality_metrics": quality_metrics
            }

            # Add landmarks if available
            if hasattr(face, 'landmark') and face.landmark is not None:
                metadata["landmarks"] = face.landmark.tolist()

            logger.info(
                "image_processing_complete",
                filename=filename,
                metadata=metadata
            )

            return embedding, metadata

        except (
            FaceDetectionError,
            MultipleFacesError,
            DatabaseError,
            ImageResolutionError,
            ImageBlurError,
            ImageLightingError,
            FaceTooSmallError,
            FaceNotFullyVisibleError,
            FaceOccludedError,
        ):
            raise
        except Exception as e:
            logger.error("face_processing_failed", error=str(e))
            raise EmbeddingExtractionError(
                message=f"Failed to process image: {str(e)}",
                details={"provider": "insightface"}
            )

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by InsightFace (512)"""
        return 512

    def get_provider_name(self) -> str:
        """Get the name of the face recognition provider"""
        return "insightface"
