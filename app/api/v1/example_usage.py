"""
EXAMPLE: How to use ResponseFormatter for consistent API responses

This file shows best practices for using ResponseFormatter in your endpoints
to return standardized success and error responses with camelCase.
"""

import structlog
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from app.core.insightface import InsightFaceClient
from app.utils.exceptions import (
    FaceDetectionError,
    InvalidImageError,
    EmbeddingExtractionError,
)
from app.utils.response import ResponseFormatter

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/example", tags=["example"])
face_client = InsightFaceClient()


# ============================================================================
# EXAMPLE 1: Success Response - Enrollment with 201 Created
# ============================================================================
@router.post("/enroll")
async def enroll_face(file: UploadFile = File(...)) -> JSONResponse:
    """
    Example endpoint showing success response with 201 Created.
    
    **Response (201 Created):**
    ```json
    {
      "success": true,
      "statusCode": 201,
      "data": {
        "enrollmentId": "enr_12345",
        "embeddingDimension": 512,
        "faceDetected": true,
        "confidence": 0.95
      },
      "message": "Face enrollment successful"
    }
    ```
    """
    try:
        # Read file
        file_data = await file.read()
        
        # Process image
        embedding, metadata = face_client.process_image(
            file_data=file_data,
            filename=file.filename
        )
        
        # Return success response with 201 Created
        response_data = {
            "enrollmentId": "enr_12345",
            "embeddingDimension": metadata["embedding_dimension"],
            "faceDetected": True,
            "confidence": metadata["confidence"]
        }
        
        return JSONResponse(
            status_code=201,
            content=ResponseFormatter.created(
                data=response_data,
                message="Face enrollment successful"
            )
        )
        
    except InvalidImageError as e:
        # Return error response (400 Bad Request)
        return JSONResponse(
            status_code=400,
            content=ResponseFormatter.error(
                error_code=e.code,
                message=e.message,
                status_code=400,
                details=e.details
            )
        )
    except FaceDetectionError as e:
        # Return error response (400 Bad Request)
        return JSONResponse(
            status_code=400,
            content=ResponseFormatter.error(
                error_code=e.code,
                message=e.message,
                status_code=400,
                details=e.details
            )
        )
    except EmbeddingExtractionError as e:
        # Return error response (500 Internal Server Error)
        return JSONResponse(
            status_code=500,
            content=ResponseFormatter.error(
                error_code=e.code,
                message=e.message,
                status_code=500,
                details=e.details
            )
        )


# ============================================================================
# EXAMPLE 2: Success Response - GET with data
# ============================================================================
@router.get("/enrollments/{enrollmentId}")
async def get_enrollment(enrollmentId: int) -> JSONResponse:
    """
    Example endpoint showing success response with GET data.
    
    **Response (200 OK):**
    ```json
    {
      "success": true,
      "statusCode": 200,
      "data": {
        "enrollmentId": 12345,
        "nik": "1234567890123456",
        "faceDetected": true,
        "confidence": 0.95,
        "enrolledAt": "2026-05-20T10:30:00Z"
      },
      "message": "Enrollment retrieved successfully"
    }
    ```
    """
    try:
        # Simulate fetching from database
        enrollment_data = {
            "enrollmentId": enrollmentId,
            "nik": "1234567890123456",
            "faceDetected": True,
            "confidence": 0.95,
            "enrolledAt": "2026-05-20T10:30:00Z"
        }
        
        return JSONResponse(
            status_code=200,
            content=ResponseFormatter.success(
                data=enrollment_data,
                status_code=200,
                message="Enrollment retrieved successfully"
            )
        )
        
    except Exception as e:
        logger.error("get_enrollment_failed", error=str(e))
        return JSONResponse(
            status_code=500,
            content=ResponseFormatter.error(
                error_code="INTERNAL_ERROR",
                message="Failed to retrieve enrollment",
                status_code=500,
                details={"errorType": type(e).__name__}
            )
        )


# ============================================================================
# EXAMPLE 3: No Content Response (204)
# ============================================================================
@router.delete("/enrollments/{enrollmentId}")
async def delete_enrollment(enrollmentId: int) -> JSONResponse:
    """
    Example endpoint showing 204 No Content response.
    
    **Response (204 No Content):**
    ```json
    {
      "success": true,
      "statusCode": 204,
      "message": "No content"
    }
    ```
    """
    try:
        # Delete enrollment
        logger.info("enrollment_deleted", enrollmentId=enrollmentId)
        
        return JSONResponse(
            status_code=204,
            content=ResponseFormatter.no_content()
        )
        
    except Exception as e:
        logger.error("delete_enrollment_failed", error=str(e))
        return JSONResponse(
            status_code=500,
            content=ResponseFormatter.error(
                error_code="INTERNAL_ERROR",
                message="Failed to delete enrollment",
                status_code=500
            )
        )


# ============================================================================
# EXAMPLE 4: Multiple Error Types with Details
# ============================================================================
@router.post("/verify")
async def verify_faces(file: UploadFile = File(...)) -> JSONResponse:
    """
    Example endpoint showing how errors are automatically handled by middleware.
    The middleware catches exceptions and formats them consistently.
    
    **Success Response (200 OK):**
    ```json
    {
      "success": true,
      "statusCode": 200,
      "data": {
        "isMatch": true,
        "similarity": 0.95
      },
      "message": "Face verification completed"
    }
    ```
    
    **Error Responses (automatically handled by middleware):**
    
    Face Not Detected (400):
    ```json
    {
      "success": false,
      "statusCode": 400,
      "error": {
        "code": "NO_FACE_DETECTED",
        "message": "No face detected in image",
        "details": {
          "provider": "insightface"
        }
      },
      "timestamp": "2026-05-20T10:30:45Z"
    }
    ```
    
    Multiple Faces (400):
    ```json
    {
      "success": false,
      "statusCode": 400,
      "error": {
        "code": "MULTIPLE_FACES_DETECTED",
        "message": "Multiple faces detected (3). Please provide image with single face.",
        "details": {
          "faceCount": 3,
          "provider": "insightface"
        }
      },
      "timestamp": "2026-05-20T10:30:45Z"
    }
    ```
    
    Image Too Large (413):
    ```json
    {
      "success": false,
      "statusCode": 413,
      "error": {
        "code": "IMAGE_TOO_LARGE",
        "message": "Image file is too large",
        "details": {
          "fileSizeMb": 15.5,
          "maxSizeMb": 10.0
        }
      },
      "timestamp": "2026-05-20T10:30:45Z"
    }
    ```
    
    Invalid Image Format (400):
    ```json
    {
      "success": false,
      "statusCode": 400,
      "error": {
        "code": "UNSUPPORTED_FORMAT",
        "message": "File extension .bmp not supported",
        "details": {
          "formatDetected": ".bmp"
        }
      },
      "timestamp": "2026-05-20T10:30:45Z"
    }
    ```
    
    Internal Server Error (500):
    ```json
    {
      "success": false,
      "statusCode": 500,
      "error": {
        "code": "EMBEDDING_EXTRACTION_FAILED",
        "message": "Failed to extract embedding: CUDA error",
        "details": {
          "provider": "insightface",
          "errorType": "CUDA_ERROR"
        }
      },
      "timestamp": "2026-05-20T10:30:45Z"
    }
    ```
    """
    try:
        # Read file
        file_data = await file.read()
        
        # Process images and verify
        embedding, metadata = face_client.process_image(
            file_data=file_data,
            filename=file.filename
        )
        
        # Simulate verification
        is_match = True
        similarity = 0.95
        
        return JSONResponse(
            status_code=200,
            content=ResponseFormatter.success(
                data={
                    "isMatch": is_match,
                    "similarity": similarity
                },
                status_code=200,
                message="Face verification completed"
            )
        )
        
    # All custom exceptions are automatically caught by middleware
    # and formatted with ResponseFormatter.error()
    except Exception as e:
        logger.error("verify_faces_failed", error=str(e))
        raise  # Let middleware handle it


# ============================================================================
# NOTES FOR DEVELOPERS
# ============================================================================
"""
1. ALWAYS use ResponseFormatter for API responses to maintain consistency

2. Use appropriate status codes:
   - 200: GET, general success
   - 201: POST (resource created)
   - 204: DELETE (no content)
   - 400: Bad Request (validation, invalid input)
   - 413: Payload Too Large (file too large)
   - 500: Internal Server Error

3. Use camelCase for all JSON field names:
   - enrollmentId (not enrollment_id)
   - embeddingDimension (not embedding_dimension)
   - faceDetected (not face_detected)
   - statusCode (not status_code)

4. Custom exceptions are automatically caught by middleware:
   - FaceDetectionError
   - MultipleFacesError
   - InvalidImageError
   - UnsupportedImageFormatError
   - ImageTooLargeError
   - EmbeddingExtractionError
   - DatabaseError
   - SearchError
   - DedupServiceError

5. Error responses always include:
   - success: false
   - statusCode: HTTP status code
   - error.code: Machine-readable error code
   - error.message: Human-readable error message
   - error.details: Additional context (optional)
   - timestamp: ISO 8601 timestamp

6. Success responses always include:
   - success: true
   - statusCode: HTTP status code
   - data: Response payload (null for 204)
   - message: Optional success message
"""
