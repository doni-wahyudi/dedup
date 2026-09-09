"""Custom exception classes for dedup service"""

from typing import Optional


class DedupServiceError(Exception):
    """Base exception for dedup service errors"""
    
    def __init__(
        self,
        message: str,
        code: str = "DEDUP_ERROR",
        details: Optional[dict] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class FaceDetectionError(DedupServiceError):
    """Raised when face detection fails"""
    
    def __init__(self, message: str = "No face detected in image", details: Optional[dict] = None):
        super().__init__(message=message, code="NO_FACE_DETECTED", details=details)


class MultipleFacesError(DedupServiceError):
    """Raised when multiple faces are detected"""
    
    def __init__(
        self,
        face_count: int,
        message: str = "Multiple faces detected in image",
        details: Optional[dict] = None
    ):
        details = details or {}
        details["face_count"] = face_count
        super().__init__(message=message, code="MULTIPLE_FACES_DETECTED", details=details)


class InvalidImageError(DedupServiceError):
    """Raised when image is invalid or corrupted"""
    
    def __init__(self, message: str = "Invalid or corrupted image", details: Optional[dict] = None):
        super().__init__(message=message, code="INVALID_IMAGE", details=details)


class UnsupportedImageFormatError(DedupServiceError):
    """Raised when image format is not supported"""
    
    def __init__(
        self, 
        message: str = "Unsupported image format", 
        format_detected: Optional[str] = None,
        details: Optional[dict] = None
    ):
        details = details or {}
        if format_detected:
            details["format_detected"] = format_detected
        super().__init__(message=message, code="UNSUPPORTED_FORMAT", details=details)


class ImageTooLargeError(DedupServiceError):
    """Raised when image file is too large"""
    
    def __init__(
        self,
        file_size: int,
        max_size: int,
        message: str = "Image file is too large",
        details: Optional[dict] = None
    ):
        details = details or {}
        details["file_size_mb"] = round(file_size / (1024 * 1024), 2)
        details["max_size_mb"] = round(max_size / (1024 * 1024), 2)
        super().__init__(message=message, code="IMAGE_TOO_LARGE", details=details)


class EmbeddingExtractionError(DedupServiceError):
    """Raised when embedding extraction fails"""
    
    def __init__(self, message: str = "Failed to extract face embedding", details: Optional[dict] = None):
        super().__init__(message=message, code="EMBEDDING_EXTRACTION_FAILED", details=details)


class DatabaseError(DedupServiceError):
    """Raised when database operation fails"""
    
    def __init__(self, message: str = "Database operation failed", details: Optional[dict] = None):
        super().__init__(message=message, code="DATABASE_ERROR", details=details)


# Image Quality Validation Errors

class ImageResolutionError(DedupServiceError):
    """Raised when image resolution is below minimum required"""

    def __init__(
        self,
        width: int,
        height: int,
        min_width: int,
        min_height: int,
        message: Optional[str] = None,
        details: Optional[dict] = None
    ):
        details = details or {}
        details.update({
            "detected_width": width,
            "detected_height": height,
            "min_width": min_width,
            "min_height": min_height
        })
        msg = message or f"Image resolution ({width}x{height}) is below minimum required ({min_width}x{min_height})"
        super().__init__(message=msg, code="IMAGE_RESOLUTION_TOO_LOW", details=details)


class ImageBlurError(DedupServiceError):
    """Raised when image blur score is below minimum sharpness threshold"""

    def __init__(
        self,
        blur_score: float,
        threshold: float,
        message: Optional[str] = None,
        details: Optional[dict] = None
    ):
        details = details or {}
        details.update({
            "blur_score": round(blur_score, 2),
            "threshold": threshold
        })
        msg = message or f"Image is too blurry (sharpness score {blur_score:.2f} is below minimum threshold {threshold})"
        super().__init__(message=msg, code="IMAGE_BLURRY", details=details)


class ImageLightingError(DedupServiceError):
    """Raised when image lighting/illumination is outside acceptable bounds"""

    def __init__(
        self,
        brightness: float,
        min_brightness: float,
        max_brightness: float,
        issue: str = "improper_lighting",
        message: Optional[str] = None,
        details: Optional[dict] = None
    ):
        details = details or {}
        details.update({
            "brightness": round(brightness, 2),
            "min_brightness": min_brightness,
            "max_brightness": max_brightness,
            "issue": issue
        })
        msg = message or f"Image lighting is invalid ({issue}: brightness {brightness:.2f} not in [{min_brightness}, {max_brightness}])"
        super().__init__(message=msg, code="IMAGE_LIGHTING_INVALID", details=details)


class FaceTooSmallError(DedupServiceError):
    """Raised when detected face bounding box is smaller than minimum required size"""

    def __init__(
        self,
        face_width: int,
        face_height: int,
        min_size: int,
        message: Optional[str] = None,
        details: Optional[dict] = None
    ):
        details = details or {}
        details.update({
            "face_width": face_width,
            "face_height": face_height,
            "min_face_size": min_size
        })
        msg = message or f"Detected face ({face_width}x{face_height}) is too small (minimum required {min_size}x{min_size})"
        super().__init__(message=msg, code="FACE_TOO_SMALL", details=details)


class FaceNotFullyVisibleError(DedupServiceError):
    """Raised when face is cut off by the image boundary"""

    def __init__(
        self,
        boundary_issues: list,
        message: Optional[str] = None,
        details: Optional[dict] = None
    ):
        details = details or {}
        details["boundary_issues"] = boundary_issues
        msg = message or f"Face is not fully visible, cut off at image boundary: {', '.join(boundary_issues)}"
        super().__init__(message=msg, code="FACE_NOT_FULLY_VISIBLE", details=details)


class FaceOccludedError(DedupServiceError):
    """Raised when face key landmarks are occluded or missing"""

    def __init__(
        self,
        missing_landmarks: list,
        message: Optional[str] = None,
        details: Optional[dict] = None
    ):
        details = details or {}
        details["missing_landmarks"] = missing_landmarks
        msg = message or f"Face is partially occluded, missing key features: {', '.join(missing_landmarks)}"
        super().__init__(message=msg, code="FACE_OCCLUDED", details=details)
