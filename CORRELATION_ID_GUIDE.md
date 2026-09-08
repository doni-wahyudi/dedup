# Correlation ID Tracing Guide

## Overview
Correlation ID adalah unique identifier untuk setiap request yang memudahkan tracing across logs, responses, dan monitoring.

---

## How It Works

### 1. Request Flow
```
Request → CorrelationIdMiddleware → Extract/Generate ID → Set in Context
                                                               ↓
                                                        Throughout Request Lifecycle
                                                               ↓
                                                        Error Handler → Add to Response
```

### 2. Sources (In Priority Order)
1. `X-Correlation-ID` header (preferred)
2. `X-Request-ID` header (fallback)
3. Auto-generate UUID (if not provided)

### 3. Response Format
All responses include `correlationId`:

**Success Response:**
```json
{
  "success": true,
  "statusCode": 200,
  "data": {...}
}
```
(No correlationId in success responses - use header instead)

**Error Response:**
```json
{
  "success": false,
  "statusCode": 400,
  "error": {
    "code": "ERROR_CODE",
    "message": "Error message",
    "details": {...}
  },
  "timestamp": "2026-05-20T10:30:45Z",
  "correlationId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response Headers:**
```
X-Correlation-ID: 550e8400-e29b-41d4-a716-446655440000
```

---

## Usage Examples

### Example 1: Client Provides Correlation ID
**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/enrollments \
  -H "X-Correlation-ID: my-custom-id-12345" \
  -F "file=@face.jpg"
```

**Response (Error):**
```json
{
  "success": false,
  "statusCode": 400,
  "error": {
    "code": "NO_FACE_DETECTED",
    "message": "No face detected in image",
    "details": {...}
  },
  "timestamp": "2026-05-20T10:30:45Z",
  "correlationId": "my-custom-id-12345"
}
```

**Response Headers:**
```
X-Correlation-ID: my-custom-id-12345
```

### Example 2: Server Generates Correlation ID
**Request (no header):**
```bash
curl -X POST http://localhost:8000/api/v1/enrollments \
  -F "file=@invalid.txt"
```

**Response (Error):**
```json
{
  "success": false,
  "statusCode": 400,
  "error": {
    "code": "UNSUPPORTED_FORMAT",
    "message": "File extension .txt not supported",
    "details": {...}
  },
  "timestamp": "2026-05-20T10:30:45Z",
  "correlationId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response Headers:**
```
X-Correlation-ID: 550e8400-e29b-41d4-a716-446655440000
```

---

## Tracing in Logs

### Request Start Log
```json
{
  "event": "request_started",
  "path": "/api/v1/enrollments",
  "method": "POST",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Error Log
```json
{
  "event": "request_error",
  "path": "/api/v1/enrollments",
  "method": "POST",
  "status_code": 400,
  "error_code": "NO_FACE_DETECTED",
  "error_message": "No face detected in image",
  "error_type": "FaceDetectionError",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Request Complete Log
```json
{
  "event": "request_completed",
  "path": "/api/v1/enrollments",
  "method": "POST",
  "status_code": 400,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Using in Code

### In Endpoints
```python
from fastapi import Request
from app.middleware.correlation_id import get_correlation_id

@router.post("/enroll")
async def enroll_face(request: Request, file: UploadFile):
    # Get correlation ID from context
    correlation_id = get_correlation_id()
    
    # Log with correlation ID
    logger.info("processing_enrollment", 
                correlation_id=correlation_id, 
                filename=file.filename)
    
    # ... your code ...
```

### In Services
```python
from app.middleware.correlation_id import get_correlation_id

class EnrollmentService:
    def process_enrollment(self, data):
        correlation_id = get_correlation_id()
        logger.info("enrollment_processing", 
                    correlation_id=correlation_id)
        # ... your code ...
```

### In Database Operations
```python
from app.middleware.correlation_id import get_correlation_id

async def save_enrollment(enrollment_data):
    correlation_id = get_correlation_id()
    logger.info("saving_to_database",
                correlation_id=correlation_id,
                table="enrollments")
    # ... your code ...
```

---

## Tracing Flow Example

### Scenario: Upload Invalid Image
```
1. Client sends request:
   POST /api/v1/enrollments
   X-Correlation-ID: trace-001

2. CorrelationIdMiddleware:
   - Extracts correlation ID: "trace-001"
   - Sets in context variable
   - Log: request_started, correlation_id=trace-001

3. Endpoint receives request:
   - Gets correlation ID: get_correlation_id() → "trace-001"
   - Passes to service

4. Service validates image:
   - Log: image_validation_failed, correlation_id=trace-001
   - Raises UnsupportedImageFormatError

5. Error Handler catches exception:
   - Gets correlation ID from request header: "trace-001"
   - Log: request_error, correlation_id=trace-001
   - Builds error response with correlationId: "trace-001"

6. Response returned:
   {
     "success": false,
     "statusCode": 400,
     "error": {...},
     "correlationId": "trace-001",
     "timestamp": "2026-05-20T10:30:45Z"
   }
   Headers: X-Correlation-ID: trace-001

7. Client receives response:
   - Can use correlation ID "trace-001" to search logs
   - Finds all events for this request in log system
```

---

## Best Practices

### 1. Generate Unique IDs for Each Request
```bash
# Generate UUID for each request
curl -X POST http://localhost:8000/api/v1/enrollments \
  -H "X-Correlation-ID: $(uuidgen)" \
  -F "file=@face.jpg"
```

### 2. Pass Through Service Calls
If calling other services, pass correlation ID:
```python
@router.post("/enroll")
async def enroll_face(file: UploadFile):
    correlation_id = get_correlation_id()
    
    # Call another service with correlation ID
    result = await dedup_service.process(
        file_data,
        correlation_id=correlation_id
    )
```

### 3. Log Important Events
```python
logger.info("face_detected",
            correlation_id=get_correlation_id(),
            face_count=2,
            confidence=0.95)

logger.warning("high_similarity_found",
               correlation_id=get_correlation_id(),
               similarity=0.98,
               matched_enrollment_id=123)

logger.error("processing_failed",
             correlation_id=get_correlation_id(),
             error_type="CUDA_ERROR")
```

### 4. Include in Monitoring/Alerting
Use correlation ID in alerts to link to specific request:
```
Alert: Face detection failed
Correlation ID: 550e8400-e29b-41d4-a716-446655440000
Timestamp: 2026-05-20T10:30:45Z
Error: No face detected in image
```

---

## Implementation Details

### Files Modified/Created
1. **app/middleware/correlation_id.py** - Middleware for correlation ID handling
2. **app/middleware/error_handler.py** - Updated to include correlation ID
3. **app/utils/response.py** - Updated ResponseFormatter for correlation ID
4. **app/main.py** - Registered CorrelationIdMiddleware

### Context Variable
```python
_correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')
```
- Thread-safe storage per request
- Available throughout request lifecycle
- Automatically cleaned up after request completes

### Middleware Order
```
Request → CorrelationIdMiddleware (sets correlation ID)
       → LoggingMiddleware (logs with correlation ID)
       → CORS Middleware
       → Error Handler (catches and logs with correlation ID)
       → Endpoint
```

---

## Troubleshooting

### Correlation ID Not Showing in Response
1. Check if it's error response (correlation ID only in errors)
2. Check response headers for X-Correlation-ID
3. Check request had valid format

### All Requests Have Same Correlation ID
1. Likely using same header for all requests
2. Or middleware not generating new UUIDs
3. Check that each request sends unique X-Correlation-ID or none

### Cannot Find Request in Logs
1. Use correlation ID from error response or response header
2. Search logs for: `correlation_id=<your-id>`
3. Check log aggregation system (if using ELK, Splunk, etc.)

---

## Log Queries

### Elasticsearch/ELK
```json
GET logs/_search
{
  "query": {
    "match": {
      "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
}
```

### Splunk
```
correlation_id="550e8400-e29b-41d4-a716-446655440000"
```

### CloudWatch
```
fields @timestamp, @message, correlation_id
| filter correlation_id = "550e8400-e29b-41d4-a716-446655440000"
```

---

## Example: Complete Request Trace

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/enrollments \
  -H "X-Correlation-ID: trace-12345" \
  -F "file=@face.jpg"
```

**All Logs for This Request:**
```
[2026-05-20T10:30:44Z] REQUEST_STARTED - correlation_id=trace-12345
[2026-05-20T10:30:44Z] IMAGE_VALIDATION - correlation_id=trace-12345
[2026-05-20T10:30:44Z] FACE_DETECTION_STARTED - correlation_id=trace-12345
[2026-05-20T10:30:44Z] FACE_DETECTED - correlation_id=trace-12345, face_count=1
[2026-05-20T10:30:44Z] EMBEDDING_EXTRACTION - correlation_id=trace-12345
[2026-05-20T10:30:44Z] DATABASE_INSERT - correlation_id=trace-12345
[2026-05-20T10:30:45Z] REQUEST_COMPLETED - correlation_id=trace-12345, status=201
```

**Response:**
```json
{
  "success": true,
  "statusCode": 201,
  "data": {
    "enrollmentId": "enr_99999",
    "embeddingDimension": 512,
    "faceDetected": true,
    "confidence": 0.98
  }
}
```

**Response Headers:**
```
X-Correlation-ID: trace-12345
```

---

Now you can trace any request from client → API → logs using the correlation ID!
