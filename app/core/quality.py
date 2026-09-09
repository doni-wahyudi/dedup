"""Image Quality Validator for biometric face comparison and enrollment

Enforces quality standards:
- Minimum image resolution
- Minimum face size
- Image sharpness / blur detection (Laplacian variance)
- Lighting / illumination (mean luminance)
- Face boundary integrity (face not cropped at edges)
- Occlusion / landmark completeness
"""

from typing import Tuple, Dict, Any, Optional
import cv2
import numpy as np
from PIL import Image
import structlog

from app.config.settings import settings
from app.utils.exceptions import (
    ImageResolutionError,
    ImageBlurError,
    ImageLightingError,
    FaceTooSmallError,
    FaceNotFullyVisibleError,
    FaceOccludedError,
)

logger = structlog.get_logger(__name__)


class ImageQualityValidator:
    """Validates photographic and biometric quality of face images"""

    @staticmethod
    def validate_resolution(
        width: int,
        height: int,
        min_width: Optional[int] = None,
        min_height: Optional[int] = None
    ) -> Dict[str, int]:
        """Validate that image resolution meets minimum requirements
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
            min_width: Minimum required width (defaults to settings.quality_min_image_width)
            min_height: Minimum required height (defaults to settings.quality_min_image_height)
            
        Raises:
            ImageResolutionError: If resolution is below minimum
        """
        req_min_w = min_width if min_width is not None else settings.quality_min_image_width
        req_min_h = min_height if min_height is not None else settings.quality_min_image_height

        if width < req_min_w or height < req_min_h:
            logger.warning(
                "image_resolution_too_low",
                width=width,
                height=height,
                min_width=req_min_w,
                min_height=req_min_h
            )
            raise ImageResolutionError(
                width=width,
                height=height,
                min_width=req_min_w,
                min_height=req_min_h
            )

        return {"width": width, "height": height}

    @staticmethod
    def validate_blur(
        img_bgr: np.ndarray,
        threshold: Optional[float] = None
    ) -> float:
        """Validate image sharpness using Variance of Laplacian
        
        Args:
            img_bgr: Image as numpy array in BGR format
            threshold: Minimum sharpness threshold (defaults to settings.quality_blur_threshold)
            
        Returns:
            blur_score (higher = sharper, lower = more blurry)
            
        Raises:
            ImageBlurError: If blur_score is below threshold
        """
        thresh = threshold if threshold is not None else settings.quality_blur_threshold

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        if blur_score < thresh:
            logger.warning(
                "image_blurry_rejected",
                blur_score=round(blur_score, 2),
                threshold=thresh
            )
            raise ImageBlurError(
                blur_score=blur_score,
                threshold=thresh
            )

        return round(blur_score, 2)

    @staticmethod
    def validate_lighting(
        img_bgr: np.ndarray,
        min_brightness: Optional[float] = None,
        max_brightness: Optional[float] = None
    ) -> float:
        """Validate illumination / lighting of image
        
        Args:
            img_bgr: Image as numpy array in BGR format
            min_brightness: Minimum average luminance (defaults to settings.quality_lighting_min)
            max_brightness: Maximum average luminance (defaults to settings.quality_lighting_max)
            
        Returns:
            mean brightness value (0-255)
            
        Raises:
            ImageLightingError: If image is underexposed or overexposed
        """
        min_b = min_brightness if min_brightness is not None else settings.quality_lighting_min
        max_b = max_brightness if max_brightness is not None else settings.quality_lighting_max

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))

        if brightness < min_b:
            logger.warning(
                "image_underexposed_rejected",
                brightness=round(brightness, 2),
                min_brightness=min_b
            )
            raise ImageLightingError(
                brightness=brightness,
                min_brightness=min_b,
                max_brightness=max_b,
                issue="underexposed_too_dark"
            )

        if brightness > max_b:
            logger.warning(
                "image_overexposed_rejected",
                brightness=round(brightness, 2),
                max_brightness=max_b
            )
            raise ImageLightingError(
                brightness=brightness,
                min_brightness=min_b,
                max_brightness=max_b,
                issue="overexposed_too_bright"
            )

        return round(brightness, 2)

    @staticmethod
    def validate_face_integrity(
        img_shape: Tuple[int, int, ...],
        bbox: list,
        min_face_size: Optional[int] = None,
        boundary_margin: Optional[int] = None
    ) -> Dict[str, Any]:
        """Ensure face is fully visible within image boundaries and sufficiently sized
        
        Args:
            img_shape: Image shape (height, width, channels)
            bbox: Face bounding box [x1, y1, x2, y2]
            min_face_size: Minimum face box width and height
            boundary_margin: Minimum pixels from boundary to avoid cut-off face
            
        Raises:
            FaceTooSmallError: If face box dimensions are below minimum
            FaceNotFullyVisibleError: If face touches or crosses image boundary
        """
        min_size = min_face_size if min_face_size is not None else settings.quality_min_face_size
        margin = boundary_margin if boundary_margin is not None else settings.quality_boundary_margin

        img_h, img_w = img_shape[:2]
        x1, y1, x2, y2 = bbox

        face_w = int(x2 - x1)
        face_h = int(y2 - y1)

        # Check face size
        if face_w < min_size or face_h < min_size:
            logger.warning(
                "face_too_small_rejected",
                face_width=face_w,
                face_height=face_h,
                min_size=min_size
            )
            raise FaceTooSmallError(
                face_width=face_w,
                face_height=face_h,
                min_size=min_size
            )

        # Check boundary cut-off
        boundary_issues = []
        if x1 <= margin:
            boundary_issues.append("left edge")
        if y1 <= margin:
            boundary_issues.append("top edge")
        if x2 >= img_w - margin:
            boundary_issues.append("right edge")
        if y2 >= img_h - margin:
            boundary_issues.append("bottom edge")

        if boundary_issues:
            logger.warning(
                "face_boundary_cut_off",
                boundary_issues=boundary_issues,
                bbox=bbox,
                img_shape=(img_w, img_h)
            )
            raise FaceNotFullyVisibleError(boundary_issues=boundary_issues)

        return {
            "face_width": face_w,
            "face_height": face_h
        }

    @staticmethod
    def validate_landmarks_and_occlusion(face: Any) -> Dict[str, Any]:
        """Validate that essential facial landmarks are detectable and not occluded
        
        Args:
            face: InsightFace Face object
            
        Raises:
            FaceOccludedError: If facial landmarks are missing or corrupted
        """
        kps = getattr(face, 'kps', None)
        if kps is None or len(kps) < 5:
            logger.warning("face_landmarks_missing_or_occluded")
            raise FaceOccludedError(missing_landmarks=["facial_landmarks_missing"])

        # Check for NaN or Inf coordinates in landmarks
        if np.isnan(kps).any() or np.isinf(kps).any():
            logger.warning("face_landmarks_invalid_coordinates")
            raise FaceOccludedError(missing_landmarks=["invalid_landmark_coordinates"])

        # Check detection confidence score against quality bar
        det_score = float(getattr(face, 'det_score', 0.0))
        if det_score < settings.face_detection_threshold:
            logger.warning("face_detection_confidence_too_low", det_score=det_score)
            raise FaceOccludedError(missing_landmarks=["low_confidence_due_to_obstruction"])

        return {
            "landmarks_detected": len(kps),
            "detection_score": round(det_score, 4)
        }
