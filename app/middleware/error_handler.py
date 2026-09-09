"""Global exception handler middleware"""

import uuid
from datetime import datetime

import structlog
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.middleware.correlation_id import get_correlation_id
from app.utils.exceptions import (
    DedupServiceError,
    FaceDetectionError,
    MultipleFacesError,
    InvalidImageError,
    UnsupportedImageFormatError,
    ImageTooLargeError,
    DatabaseError,
    EmbeddingExtractionError,
    ImageResolutionError,
    ImageBlurError,
    ImageLightingError,
    FaceTooSmallError,
    FaceNotFullyVisibleError,
    FaceOccludedError,
)
from app.utils.response import ResponseFormatter

logger = structlog.get_logger(__name__)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for all requests
    
    Maps custom exceptions to appropriate HTTP status codes and responses
    """
    # Get correlation ID from middleware context (same ID already in response header)
    correlation_id = get_correlation_id() or str(uuid.uuid4())
    
    # Default error response
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "INTERNAL_ERROR"
    error_message = "An internal error occurred"
    error_details = None
    
    # Map custom exceptions
    if isinstance(exc, (
        FaceDetectionError,
        MultipleFacesError,
        InvalidImageError,
        UnsupportedImageFormatError,
        ImageResolutionError,
        ImageBlurError,
        ImageLightingError,
        FaceTooSmallError,
        FaceNotFullyVisibleError,
        FaceOccludedError,
    )):
        status_code = status.HTTP_400_BAD_REQUEST
        error_code = exc.code
        error_message = exc.message
        error_details = exc.details
        
    elif isinstance(exc, ImageTooLargeError):
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        error_code = exc.code
        error_message = exc.message
        error_details = exc.details
        
    elif isinstance(exc, EmbeddingExtractionError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_code = exc.code
        error_message = exc.message
        error_details = exc.details
        
    elif isinstance(exc, DatabaseError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_code = exc.code
        error_message = exc.message
        error_details = exc.details
        
    elif isinstance(exc, DedupServiceError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_code = exc.code
        error_message = exc.message
        error_details = exc.details
    
    # Log error with correlation ID
    logger.error(
        "request_error",
        path=request.url.path,
        method=request.method,
        status_code=status_code,
        error_code=error_code,
        error_message=error_message,
        error_type=type(exc).__name__,
        correlation_id=correlation_id,
    )
    
    # Build response with consistent format
    response_body = ResponseFormatter.error(
        error_code=error_code,
        message=error_message,
        status_code=status_code,
        details=error_details,
        timestamp=datetime.utcnow().isoformat() + "Z",
        correlation_id=correlation_id
    )
    
    return JSONResponse(
        status_code=status_code,
        content=response_body,
        headers={"X-Correlation-ID": correlation_id}
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle FastAPI validation errors with consistent format"""
    
    # Get correlation ID from middleware context (same ID already in response header)
    correlation_id = get_correlation_id() or str(uuid.uuid4())
    
    # Extract validation error details
    errors = exc.errors()
    
    # Determine error code and message based on first error
    first_error = errors[0] if errors else {}
    error_type = first_error.get("type", "validation_error")
    field_location = first_error.get("loc", [])
    field_name = field_location[-1] if field_location else "unknown"
    
    # Map validation error types to our error codes
    if error_type == "missing":
        error_code = "FIELD_REQUIRED"
        if field_name == "image":
            error_message = "Image file is required"
        else:
            error_message = f"{field_name} is required"
    elif error_type in ["greater_than_equal", "less_than_equal", "greater_than", "less_than"]:
        error_code = "INVALID_PARAMETER"
        error_message = f"Invalid value for {field_name}: {first_error.get('msg', 'validation failed')}"
    elif error_type == "type_error":
        error_code = "INVALID_TYPE"
        error_message = f"Invalid type for {field_name}: {first_error.get('msg', 'type error')}"
    else:
        error_code = "VALIDATION_ERROR"
        error_message = first_error.get("msg", "Validation failed")
    
    # Build validation details
    validation_details = {
        "field": field_name,
        "error_type": error_type,
        "input": first_error.get("input"),
        "validation_errors": errors
    }
    
    # Log validation error with correlation ID
    logger.error(
        "validation_error",
        path=request.url.path,
        method=request.method,
        field=field_name,
        error_type=error_type,
        error_count=len(errors),
        correlation_id=correlation_id
    )
    
    # Return consistent structured response with correlation ID
    response_body = ResponseFormatter.error(
        error_code=error_code,
        message=error_message,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details=validation_details,
        timestamp=datetime.utcnow().isoformat() + "Z",
        correlation_id=correlation_id
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response_body,
        headers={"X-Correlation-ID": correlation_id}
    )


def register_error_handlers(app):
    """Register all error handlers for the FastAPI app"""
    from app.utils.exceptions import DedupServiceError
    
    # Register validation error handler
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # Register business logic error handlers
    app.add_exception_handler(DedupServiceError, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
