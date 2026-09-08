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
