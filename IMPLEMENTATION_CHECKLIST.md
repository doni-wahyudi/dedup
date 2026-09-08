# Implementation Checklist - Standard Response Format

## ✅ Completed

- [x] Created `app/utils/response.py` - Response formatter utility
- [x] Updated `app/middleware/error_handler.py` - Consistent error formatting
- [x] Created example endpoints in `app/api/v1/example_usage.py`
- [x] Created comprehensive guide in `RESPONSE_FORMAT_GUIDE.md`

## 📋 What Was Done

### 1. Response Formatter (`app/utils/response.py`)
```python
from app.utils.response import ResponseFormatter

# Success response
ResponseFormatter.success(data=..., status_code=200, message="...")

# Error response
ResponseFormatter.error(error_code="...", message="...", status_code=400, details={...})

# Created response (201)
ResponseFormatter.created(data=..., message="...")

# No content response (204)
ResponseFormatter.no_content()
```

### 2. Updated Error Handler
- All custom exceptions are caught and formatted automatically
- Returns camelCase JSON with standardized format
- Includes timestamp in error responses

### 3. Response Format (All responses follow this)
**Success:**
```json
{
  "success": true,
  "statusCode": 200,
  "data": {...},
  "message": "..."
}
```

**Error:**
```json
{
  "success": false,
  "statusCode": 400,
  "error": {
    "code": "ERROR_CODE",
    "message": "...",
    "details": {...}
  },
  "timestamp": "2026-05-20T10:30:45Z"
}
```

---

## 🚀 Next Steps for Your Endpoints

### Step 1: Update Endpoint Import
```python
from app.utils.response import ResponseFormatter
from fastapi.responses import JSONResponse
```

### Step 2: Return Formatted Response
```python
@router.post("/enroll")
async def enroll_face(file: UploadFile):
    try:
        # Your logic...
        
        return JSONResponse(
            status_code=201,
            content=ResponseFormatter.created(
                data=enrollment_data,
                message="Face enrollment successful"
            )
        )
    except InvalidImageError as e:
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

### Step 3: Remove Old Error Handling
- ❌ Remove manual error formatting
- ❌ Remove inconsistent response structures
- ✅ Let middleware handle exceptions automatically

---

## 📚 File Locations

| File | Purpose |
|------|---------|
| `app/utils/response.py` | Response formatter utility |
| `app/middleware/error_handler.py` | Global exception handler (updated) |
| `app/api/v1/example_usage.py` | Example endpoint implementations |
| `RESPONSE_FORMAT_GUIDE.md` | Complete reference guide |

---

## 🔍 Quick Reference

### JSON Field Names (camelCase)
- ❌ `enrollment_id` → ✅ `enrollmentId`
- ❌ `face_count` → ✅ `faceCount`
- ❌ `image_size` → ✅ `imageSize`
- ❌ `embedding_dimension` → ✅ `embeddingDimension`
- ❌ `face_detected` → ✅ `faceDetected`
- ❌ `status_code` → ✅ `statusCode`

### HTTP Status Codes
- `200` - GET, general success
- `201` - POST (resource created)
- `204` - DELETE (no response body)
- `400` - Bad Request
- `413` - Payload Too Large
- `422` - Validation Error
- `500` - Internal Server Error

### Auto-Handled Exceptions
- `FaceDetectionError` → 400
- `MultipleFacesError` → 400
- `InvalidImageError` → 400
- `UnsupportedImageFormatError` → 400
- `ImageTooLargeError` → 413
- `EmbeddingExtractionError` → 500
- `DatabaseError` → 500
- `SearchError` → 500

---

## ✨ Examples

### Example 1: Create Enrollment
**Request:**
```
POST /api/v1/enrollments
Content-Type: multipart/form-data
```

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

### Example 2: No Face Detected
**Response (400 Bad Request):**
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

### Example 3: File Too Large
**Response (413 Payload Too Large):**
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

---

## 📝 Notes

1. The **error handler middleware** automatically catches all custom exceptions
2. You **don't need to format errors manually** - just let exceptions propagate
3. **ResponseFormatter** is used in endpoints for success responses
4. All JSON fields use **camelCase** consistently
5. Error responses always include **timestamp** in ISO 8601 format

---

## 🎯 Testing

### Test Success Response
```bash
curl -X POST http://localhost:8000/api/v1/enrollments \
  -F "file=@face.jpg"
```

### Test Error Response
```bash
curl -X POST http://localhost:8000/api/v1/enrollments \
  -F "file=@invalid.txt"
```

Both should follow the standardized format!

---

## 💡 Tips

1. Copy from `app/api/v1/example_usage.py` when creating new endpoints
2. Check `RESPONSE_FORMAT_GUIDE.md` for detailed examples
3. Keep all JSON fields in **camelCase**
4. Always use **appropriate HTTP status codes**
5. Include **meaningful error details** for debugging

---

**Status**: ✅ Ready to use in all endpoints
**Created**: 2026-05-20
