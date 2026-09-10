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
        min_height: Optional[int] = None,
        field: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Dict[str, int]:
        """Validate that image resolution meets minimum requirements"""
        req_min_w = min_width if min_width is not None else settings.quality_min_image_width
        req_min_h = min_height if min_height is not None else settings.quality_min_image_height

        if width < req_min_w or height < req_min_h:
            logger.warning(
                "image_resolution_too_low",
                width=width,
                height=height,
                min_width=req_min_w,
                min_height=req_min_h,
                field=field,
                filename=filename
            )
            raise ImageResolutionError(
                width=width,
                height=height,
                min_width=req_min_w,
                min_height=req_min_h,
                field=field,
                filename=filename
            )

        return {"width": width, "height": height}

    @staticmethod
    def validate_blur(
        img_bgr: np.ndarray,
        threshold: Optional[float] = None,
        field: Optional[str] = None,
        filename: Optional[str] = None
    ) -> float:
        """Validate image sharpness using Variance of Laplacian with scale normalization
        
        Note: High-resolution images (e.g. 4000x3000 from mobile phones) have pixel gradients
        spread across many pixels, naturally yielding low raw Laplacian variance despite being
        sharp. We standardize the evaluation resolution (max dimension 1000px) so the sharpness
        metric is scale-invariant and accurately detects true blur.
        """
        thresh = threshold if threshold is not None else settings.quality_blur_threshold

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Standardize evaluation scale to 1000px max dimension using bilinear interpolation (preserves sharp edges)
        max_dim = 1000
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            gray_eval = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)
        else:
            gray_eval = gray

        blur_score = float(cv2.Laplacian(gray_eval, cv2.CV_64F).var())

        if blur_score < thresh:
            logger.warning(
                "image_blurry_rejected",
                blur_score=round(blur_score, 2),
                threshold=thresh,
                field=field,
                filename=filename
            )
            raise ImageBlurError(
                blur_score=blur_score,
                threshold=thresh,
                field=field,
                filename=filename
            )

        return round(blur_score, 2)

    @staticmethod
    def validate_lighting(
        img_bgr: np.ndarray,
        min_brightness: Optional[float] = None,
        max_brightness: Optional[float] = None,
        field: Optional[str] = None,
        filename: Optional[str] = None
    ) -> float:
        """Validate illumination / lighting of image"""
        min_b = min_brightness if min_brightness is not None else settings.quality_lighting_min
        max_b = max_brightness if max_brightness is not None else settings.quality_lighting_max

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))

        if brightness < min_b:
            logger.warning(
                "image_underexposed_rejected",
                brightness=round(brightness, 2),
                min_brightness=min_b,
                field=field,
                filename=filename
            )
            raise ImageLightingError(
                brightness=brightness,
                min_brightness=min_b,
                max_brightness=max_b,
                issue="underexposed_too_dark",
                field=field,
                filename=filename
            )

        if brightness > max_b:
            logger.warning(
                "image_overexposed_rejected",
                brightness=round(brightness, 2),
                max_brightness=max_b,
                field=field,
                filename=filename
            )
            raise ImageLightingError(
                brightness=brightness,
                min_brightness=min_b,
                max_brightness=max_b,
                issue="overexposed_too_bright",
                field=field,
                filename=filename
            )

        return round(brightness, 2)

    @staticmethod
    def validate_face_integrity(
        img_shape: Tuple[int, int, ...],
        bbox: list,
        min_face_size: Optional[int] = None,
        boundary_margin: Optional[int] = None,
        field: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Ensure face is fully visible within image boundaries and sufficiently sized"""
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
                min_size=min_size,
                field=field,
                filename=filename
            )
            raise FaceTooSmallError(
                face_width=face_w,
                face_height=face_h,
                min_size=min_size,
                field=field,
                filename=filename
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
                img_shape=(img_w, img_h),
                field=field,
                filename=filename
            )
            raise FaceNotFullyVisibleError(
                boundary_issues=boundary_issues,
                field=field,
                filename=filename
            )

        return {
            "face_width": face_w,
            "face_height": face_h
        }

    @staticmethod
    def validate_landmarks_and_occlusion(
        face: Any,
        field: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate that essential facial landmarks are detectable and not occluded"""
        kps = getattr(face, 'kps', None)
        if kps is None or len(kps) < 5:
            logger.warning("face_landmarks_missing_or_occluded", field=field, filename=filename)
            raise FaceOccludedError(
                missing_landmarks=["facial_landmarks_missing"],
                field=field,
                filename=filename
            )

        # Check for NaN or Inf coordinates in landmarks
        if np.isnan(kps).any() or np.isinf(kps).any():
            logger.warning("face_landmarks_invalid_coordinates", field=field, filename=filename)
            raise FaceOccludedError(
                missing_landmarks=["invalid_landmark_coordinates"],
                field=field,
                filename=filename
            )

        # Check detection confidence score against quality bar
        det_score = float(getattr(face, 'det_score', 0.0))
        if det_score < settings.face_detection_threshold:
            logger.warning(
                "face_detection_confidence_too_low",
                det_score=det_score,
                field=field,
                filename=filename
            )
            raise FaceOccludedError(
                missing_landmarks=["low_confidence_due_to_obstruction"],
                field=field,
                filename=filename
            )

        return {
            "landmarks_detected": len(kps),
            "detection_score": round(det_score, 4)
        }
