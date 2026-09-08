# API Error Response Documentation

## Error Response Format

Semua error menggunakan format yang sama:

```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Error message",
    "details": {}
  }
}
```

## Error Code Mapping

| HTTP Status | Error Code | Message |
|-------------|------------|---------|
| **422** | `FIELD_REQUIRED` | "Image file is required" |
| **422** | `INVALID_PARAMETER` | "Invalid value for {field}" |
| **422** | `INVALID_TYPE` | "Invalid type for {field}" |
| **422** | `VALIDATION_ERROR` | "Validation failed" |
| **400** | `NO_FACE_DETECTED` | "No face detected in image" |
| **400** | `MULTIPLE_FACES_DETECTED` | "Multiple faces detected in image" |
| **400** | `INVALID_IMAGE` | "Invalid or corrupted image" |
| **400** | `UNSUPPORTED_FORMAT` | "Image format {format} not supported" |
| **413** | `IMAGE_TOO_LARGE` | "Image file is too large" |
| **500** | `EMBEDDING_EXTRACTION_FAILED` | "Failed to extract face embedding" |
| **500** | `DATABASE_ERROR` | "Database operation failed" |
| **500** | `SEARCH_ERROR` | "Search operation failed" |
| **500** | `INTERNAL_ERROR` | "An internal error occurred" |

## Response Examples

### Validation Error (422)
```json
{
  "status": "error",
  "error": {
    "code": "FIELD_REQUIRED",
    "message": "Image file is required",
    "details": {
      "field": "image"
    }
  }
}
```

### Business Logic Error (400)
```json
{
  "status": "error",
  "error": {
    "code": "UNSUPPORTED_FORMAT",
    "message": "Image format WEBP not supported",
    "details": {
      "format_detected": "WEBP"
    }
  }
}
```

### Multiple Faces Error (400)
```json
{
  "status": "error",
  "error": {
    "code": "MULTIPLE_FACES_DETECTED",
    "message": "Multiple faces detected in image",
    "details": {
      "face_count": 3
    }
  }
}
```

### Image Too Large Error (413)
```json
{
  "status": "error",
  "error": {
    "code": "IMAGE_TOO_LARGE",
    "message": "Image file is too large",
    "details": {
      "file_size_mb": 12.5,
      "max_size_mb": 10.0
    }
  }
}
```

### Server Error (500)
```json
{
  "status": "error",
  "error": {
    "code": "DATABASE_ERROR",
    "message": "Database operation failed",
    "details": {}
  }
}
```
