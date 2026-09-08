# Standard API Response Format Guide

## Overview
All API responses follow a consistent format with camelCase field names for JSON.

---

## Success Response Format

### Structure
```json
{
  "success": true,
  "statusCode": 200,
  "data": {},
  "message": "Success message"
}
```

### Fields
- `success` (boolean): Always `true` for success responses
- `statusCode` (number): HTTP status code (200, 201, 204, etc.)
- `data` (object/array): Response payload (null for 204 No Content)
- `message` (string): Optional human-readable message

### HTTP Status Codes for Success
| Status | When Used | Example |
|--------|-----------|---------|
| 200 | GET, general success | Retrieved enrollment data |
| 201 | POST (resource created) | Created new enrollment |
| 204 | DELETE (no content) | Deleted enrollment |

### Examples

#### GET - List Enrollments (200 OK)
```json
{
  "success": true,
  "statusCode": 200,
  "data": [
    {
      "enrollmentId": 12345,
      "nik": "1234567890123456",
      "cifName": "John Doe",
      "sentraId": "SENTRA_001",
      "fraudStatus": "clean",
      "confidence": 0.95,
      "enrolledAt": "2026-05-20T10:30:00Z"
    }
  ],
  "message": "Enrollments retrieved successfully"
}
```

#### POST - Create Enrollment (201 Created)
```json
{
  "success": true,
  "statusCode": 201,
  "data": {
    "enrollmentId": "enr_67890",
    "embeddingDimension": 512,
    "faceDetected": true,
    "confidence": 0.98,
    "faceLandmarks": {
      "leftEye": [100, 150],
      "rightEye": [200, 150],
      "nose": [150, 180],
      "mouth": [150, 220]
    }
  },
  "message": "Face enrollment successful"
}
```

#### DELETE - Remove Enrollment (204 No Content)
```json
{
  "success": true,
  "statusCode": 204,
  "message": "Resource deleted successfully"
}
```

---

## Error Response Format

### Structure
```json
{
  "success": false,
  "statusCode": 400,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  },
  "timestamp": "2026-05-20T10:30:45Z"
}
```

### Fields
- `success` (boolean): Always `false` for error responses
- `statusCode` (number): HTTP status code (400, 401, 403, 404, 413, 500, etc.)
- `error` (object): Error information
  - `code` (string): Machine-readable error code (SNAKE_CASE)
  - `message` (string): Human-readable error message
  - `details` (object): Additional context about the error
- `timestamp` (string): ISO 8601 UTC timestamp when error occurred

### HTTP Status Codes for Errors
| Status | When Used | Example |
|--------|-----------|---------|
| 400 | Bad Request | Invalid input, missing fields |
| 401 | Unauthorized | Auth failed, missing token |
| 403 | Forbidden | Authenticated but not authorized |
| 404 | Not Found | Resource not found |
| 413 | Payload Too Large | File/image too large |
| 422 | Unprocessable Entity | Validation error |
| 500 | Internal Server Error | Server error, database error |

### Error Codes
| Code | Status | Description |
|------|--------|-------------|
| `NO_FACE_DETECTED` | 400 | No face found in image |
| `MULTIPLE_FACES_DETECTED` | 400 | Multiple faces detected |
| `INVALID_IMAGE` | 400 | Image corrupted or invalid |
| `UNSUPPORTED_FORMAT` | 400 | File format not supported |
| `IMAGE_TOO_LARGE` | 413 | File size exceeds limit |
| `EMBEDDING_EXTRACTION_FAILED` | 500 | Failed to extract embedding |
| `DATABASE_ERROR` | 500 | Database operation failed |
| `SEARCH_ERROR` | 500 | Search operation failed |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

### Examples

#### Face Not Detected (400 Bad Request)
```json
{
  "success": false,
  "statusCode": 400,
  "error": {
    "code": "NO_FACE_DETECTED",
    "message": "No face detected in image",
    "details": {
      "provider": "insightface",
      "imageSize": [1920, 1080]
    }
  },
  "timestamp": "2026-05-20T10:30:45Z"
}
```

#### Multiple Faces Detected (400 Bad Request)
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

#### Invalid Image Format (400 Bad Request)
```json
{
  "success": false,
  "statusCode": 400,
  "error": {
    "code": "UNSUPPORTED_FORMAT",
    "message": "File extension .bmp not supported",
    "details": {
      "formatDetected": ".bmp",
      "supportedFormats": [".jpg", ".png", ".jpeg"]
    }
  },
  "timestamp": "2026-05-20T10:30:45Z"
}
```

#### Image Too Large (413 Payload Too Large)
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

#### Validation Error (422 Unprocessable Entity)
```json
{
  "success": false,
  "statusCode": 422,
  "error": {
    "code": "FIELD_REQUIRED",
    "message": "Image file is required",
    "details": {
      "field": "image",
      "errorType": "missing"
    }
  },
  "timestamp": "2026-05-20T10:30:45Z"
}
```

#### Embedding Extraction Failed (500 Internal Server Error)
```json
{
  "success": false,
  "statusCode": 500,
  "error": {
    "code": "EMBEDDING_EXTRACTION_FAILED",
    "message": "Failed to extract embedding: CUDA error occurred",
    "details": {
      "provider": "insightface",
      "errorType": "CUDA_ERROR"
    }
  },
  "timestamp": "2026-05-20T10:30:45Z"
}
```

#### Database Error (500 Internal Server Error)
```json
{
  "success": false,
  "statusCode": 500,
  "error": {
    "code": "DATABASE_ERROR",
    "message": "Failed to save enrollment to database",
    "details": {
      "operation": "insert",
      "table": "enrollments"
    }
  },
  "timestamp": "2026-05-20T10:30:45Z"
}
```

---

## Implementation Guide

### Using ResponseFormatter

#### Success Response
```python
from app.utils.response import ResponseFormatter
from fastapi.responses import JSONResponse

@router.post("/enroll")
async def enroll_face(file: UploadFile):
    # Process image...
    
    return JSONResponse(
        status_code=201,
        content=ResponseFormatter.success(
            data=enrollment_data,
            status_code=201,
            message="Face enrollment successful"
        )
    )
```

#### Created Response (201)
```python
return JSONResponse(
    status_code=201,
    content=ResponseFormatter.created(
        data=enrollment_data,
        message="Face enrollment successful"
    )
)
```

#### Error Response
```python
return JSONResponse(
    status_code=400,
    content=ResponseFormatter.error(
        error_code=e.code,
        message=e.message,
        status_code=400,
        details=e.details
    )
)
```

#### No Content Response (204)
```python
return JSONResponse(
    status_code=204,
    content=ResponseFormatter.no_content()
)
```

---

## Important Notes

1. **Always use camelCase** for JSON field names:
   - ❌ `enrollment_id`, `face_count`, `image_size`
   - ✅ `enrollmentId`, `faceCount`, `imageSize`

2. **Timestamp Format**:
   - Use ISO 8601 UTC format: `2026-05-20T10:30:45Z`
   - Generated automatically in error responses

3. **Custom Exceptions**:
   - Automatically caught by middleware
   - Formatted consistently with `ResponseFormatter.error()`
   - No need to manually format in endpoints

4. **Error Details**:
   - Include relevant context (field names, actual vs expected values, etc.)
   - Use camelCase for nested field names

5. **Status Code Selection**:
   - Use 400 for client errors (validation, bad input)
   - Use 413 for file size errors specifically
   - Use 500 for server errors (database, processing errors)

---

## Example Files

See `app/api/v1/example_usage.py` for complete endpoint examples.
