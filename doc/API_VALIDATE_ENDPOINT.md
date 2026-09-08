# API Documentation: POST /api/v1/faces/validate

## Overview

Validate apakah wajah dalam gambar sudah ada di database (duplikat) berdasarkan threshold similarity yang ditentukan.

---

## Endpoint

```
POST /api/v1/faces/validate
Content-Type: multipart/form-data
```

---

## Request

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-Correlation-ID` | Optional | Custom correlation ID untuk request tracing. Jika tidak dikirim, server akan generate UUID otomatis. |

### Form Data Parameters

| Field | Type | Required | Default | Constraints | Description |
|-------|------|----------|---------|-------------|-------------|
| `image` | File | ✅ Yes | - | JPG, PNG only; max 10MB | Face image file |
| `limit` | integer | No | `10` | min: 1, max: 50 | Jumlah maksimal kandidat duplikat yang dicek |
| `sentra_id` | string | No | `null` | - | Filter hanya dari Sentra ID tertentu |
| `distance` | float | No | `0.6` (server default) | min: 0.0, max: 1.0 | Minimum similarity threshold (IP metric). Semakin tinggi = semakin mirip |

---

## Response

### Success — 200 OK

```json
{
  "success": true,
  "statusCode": 200,
  "data": {
    "isDuplicate": true,
    "duplicates": [
      {
        "nik": "3201234567890001",
        "cifName": "Budi Santoso",
        "cifCode": "CIF-001",
        "sentraId": "SNT-001",
        "sentraName": "Sentra Bogor",
        "mmsCode": "MMS-001",
        "mmsName": "MMS Bogor Timur",
        "imageUrl": "https://storage.example.com/faces/abc123.jpg",
        "distance": 0.9423
      }
    ]
  },
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

**Jika tidak ada duplikat:**
```json
{
  "success": true,
  "statusCode": 200,
  "data": {
    "isDuplicate": false,
    "duplicates": []
  },
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

### Field Description — Success Data

| Field | Type | Description |
|-------|------|-------------|
| `isDuplicate` | boolean | `true` jika ada duplikat di atas threshold, `false` jika tidak ada |
| `duplicates` | array | List wajah duplikat yang ditemukan (kosong jika tidak ada) |
| `duplicates[].nik` | string | NIK dari enrollment yang duplikat |
| `duplicates[].cifName` | string\|null | Nama CIF nasabah |
| `duplicates[].cifCode` | string\|null | Kode CIF nasabah |
| `duplicates[].sentraId` | string\|null | ID Sentra |
| `duplicates[].sentraName` | string\|null | Nama Sentra |
| `duplicates[].mmsCode` | string\|null | Kode MMS |
| `duplicates[].mmsName` | string\|null | Nama MMS |
| `duplicates[].imageUrl` | string\|null | URL foto wajah yang tersimpan |
| `duplicates[].distance` | float | IP similarity score (0.0–1.0). Semakin tinggi = semakin mirip |

---

## Error Responses

### Error Response Format (Semua Error)

```json
{
  "success": false,
  "statusCode": 400,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}
  },
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

---

### 400 Bad Request

#### `NO_FACE_DETECTED`
Tidak ada wajah yang terdeteksi di dalam gambar.

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
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

#### `MULTIPLE_FACES_DETECTED`
Lebih dari satu wajah terdeteksi di gambar (jika `allow_multiple_faces = false`).

```json
{
  "success": false,
  "statusCode": 400,
  "error": {
    "code": "MULTIPLE_FACES_DETECTED",
    "message": "Multiple faces detected (2). Please provide image with single face.",
    "details": {
      "provider": "insightface",
      "face_count": 2
    }
  },
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

#### `INVALID_IMAGE`
Gambar rusak, corrupt, atau kosong.

```json
{
  "success": false,
  "statusCode": 400,
  "error": {
    "code": "INVALID_IMAGE",
    "message": "Invalid or corrupted image: cannot identify image file",
    "details": {
      "filename": "photo.jpg"
    }
  },
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

> Juga muncul jika file kosong (0 bytes):
> `"message": "Image file is empty"`

#### `UNSUPPORTED_FORMAT`
Format gambar tidak didukung. Hanya JPG dan PNG yang diterima.

```json
{
  "success": false,
  "statusCode": 400,
  "error": {
    "code": "UNSUPPORTED_FORMAT",
    "message": "File extension .bmp not supported",
    "details": {
      "format_detected": ".bmp"
    }
  },
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

---

### 413 Request Entity Too Large

#### `IMAGE_TOO_LARGE`
Ukuran file gambar melebihi batas maksimum (default: 10MB).

```json
{
  "success": false,
  "statusCode": 413,
  "error": {
    "code": "IMAGE_TOO_LARGE",
    "message": "Image file is too large",
    "details": {
      "file_size_mb": 15.2,
      "max_size_mb": 10.0
    }
  },
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

---

### 422 Unprocessable Entity

FastAPI validation errors — terjadi sebelum request masuk ke handler.

#### `FIELD_REQUIRED`
Field mandatory tidak dikirim (contoh: `image` tidak ada).

```json
{
  "success": false,
  "statusCode": 422,
  "error": {
    "code": "FIELD_REQUIRED",
    "message": "Field 'image' is required",
    "details": {
      "field": "image",
      "location": ["body", "image"]
    }
  },
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

#### `INVALID_PARAMETER`
Nilai parameter di luar range yang diizinkan.

```json
{
  "success": false,
  "statusCode": 422,
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "Input should be less than or equal to 50",
    "details": {
      "field": "limit",
      "location": ["body", "limit"]
    }
  },
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

> Constraints: `limit` (1–50), `distance` (0.0–1.0)

#### `VALIDATION_ERROR`
Validation error lainnya (tipe data tidak sesuai, dll).

```json
{
  "success": false,
  "statusCode": 422,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Input should be a valid number",
    "details": {
      "field": "distance",
      "location": ["body", "distance"]
    }
  },
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

---

### 500 Internal Server Error

#### `EMBEDDING_EXTRACTION_FAILED`
Gagal extract face embedding dari gambar (error internal InsightFace).

```json
{
  "success": false,
  "statusCode": 500,
  "error": {
    "code": "EMBEDDING_EXTRACTION_FAILED",
    "message": "Failed to process image: <detail error>",
    "details": {
      "provider": "insightface"
    }
  },
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

#### `DATABASE_ERROR`
Error saat query ke Milvus (vector database) atau SQL Server.

```json
{
  "success": false,
  "statusCode": 500,
  "error": {
    "code": "DATABASE_ERROR",
    "message": "Database operation failed: <detail error>",
    "details": {}
  },
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

#### `DEDUP_ERROR`
Exception tidak tertangani di service layer (unexpected error).

```json
{
  "success": false,
  "statusCode": 500,
  "error": {
    "code": "DEDUP_ERROR",
    "message": "Validation failed: <detail error>",
    "details": {}
  },
  "timestamp": "2026-05-20T15:42:26.121332Z",
  "correlationId": "ded0298b-2afb-4a72-8072-821f7a413884"
}
```

---

## Error Code Summary

| HTTP Status | Error Code | Penyebab |
|------------|-----------|----------|
| **400** | `NO_FACE_DETECTED` | Tidak ada wajah di gambar |
| **400** | `MULTIPLE_FACES_DETECTED` | Lebih dari 1 wajah di gambar |
| **400** | `INVALID_IMAGE` | Gambar corrupt, invalid, atau kosong |
| **400** | `UNSUPPORTED_FORMAT` | Format bukan JPG/PNG |
| **413** | `IMAGE_TOO_LARGE` | File > 10MB |
| **422** | `FIELD_REQUIRED` | Field mandatory tidak dikirim |
| **422** | `INVALID_PARAMETER` | Parameter out of range |
| **422** | `VALIDATION_ERROR` | Tipe data tidak sesuai |
| **500** | `EMBEDDING_EXTRACTION_FAILED` | Gagal extract embedding |
| **500** | `DATABASE_ERROR` | Error database (Milvus/SQL Server) |
| **500** | `DEDUP_ERROR` | Unexpected error di service layer |

---

## Response Headers

| Header | Description |
|--------|-------------|
| `X-Correlation-ID` | Correlation ID untuk request ini (sama dengan `correlationId` di body) |

---

## Notes

- **`distance` field** di `duplicates[]` menggunakan **IP (Inner Product) metric**: nilai `1.0` = identik, nilai lebih tinggi = lebih mirip
- **Default threshold** adalah `0.6` — hanya enrollment dengan `distance >= 0.6` yang dikembalikan sebagai duplikat
- **`correlationId`** di response body selalu sama dengan header `X-Correlation-ID`
- Image yang dikirim **harus mengandung tepat 1 wajah** (kecuali server dikonfigurasi `allow_multiple_faces = true`)
