# Fraud Detection Scheduler - Documentation

## 📋 Overview

Scheduler otomatis untuk mendeteksi duplikasi wajah (fraud detection) menggunakan APScheduler. Sistem ini akan memproses enrollment yang pending secara berkala dan mencari wajah kembar di database.

---

## 🏗️ Arsitektur

### **Flow Diagram**

```
┌─────────────────────────────────────────────────────────────┐
│  SCHEDULER (APScheduler)                                    │
│  - Runs every 5 minutes (configurable)                     │
│  - Single worker (no concurrent processing)                │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  QUERY PENDING ENROLLMENTS                                  │
│  - SELECT TOP 100 WHERE check_status = 'pending'           │
│  - ORDER BY created_at ASC                                 │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  UPDATE STATUS TO PROCESSING                                │
│  - check_status = 'processing'                             │
│  - processing_by = 'scheduler-fraud-detector'              │
│  - processing_started_at = NOW()                           │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  FOR EACH ENROLLMENT:                                       │
│  1. Get milvus_id                                          │
│  2. Query Milvus → Get embedding                           │
│  3. Search TOP 5 similar faces                             │
│  4. Filter: distance >= 0.7 AND milvus_id != current      │
└─────────────────────────────────────────────────────────────┘
                        ↓
              ┌─────────┴─────────┐
              ↓                   ↓
    ┌──────────────────┐  ┌──────────────────┐
    │ DUPLICATES FOUND │  │ NO DUPLICATES    │
    │ (distance >= 0.7)│  │                  │
    └──────────────────┘  └──────────────────┘
              ↓                   ↓
    ┌──────────────────┐  ┌──────────────────┐
    │ SAVE FRAUD CASES │  │ UPDATE STATUS    │
    │ • FraudCase      │  │ • fraud_status   │
    │ • distance (IP)  │  │   = 'clean'      │
    │                  │  │ • check_status   │
    │ UPDATE STATUS    │  │   = 'checked'    │
    │ • fraud_status   │  └──────────────────┘
    │   = 'fraud'      │
    │ • check_status   │
    │   = 'checked'    │
    └──────────────────┘
```

---

## 📊 Database Schema

### **Table: enrolled_faces**

| Column | Type | Description |
|--------|------|-------------|
| `id` | BigInteger | Primary key |
| `milvus_id` | String(50) | ID di Milvus collection |
| `nik` | String(20) | Nomor Induk Kependudukan |
| `sentra_id` | String(20) | ID sentra |
| `check_status` | String(20) | Status pengecekan: `pending`, `processing`, `checked` |
| `fraud_status` | String(20) | Status fraud: `clean`, `fraud` |
| `processing_by` | String(100) | Identifier scheduler/worker |
| `processing_started_at` | DateTime | Waktu mulai proses |
| `processing_attempts` | Integer | Jumlah percobaan |
| `last_checked_at` | DateTime | Waktu terakhir dicek |
| `last_error` | String(500) | Error message (jika ada) |

### **Table: fraud_cases**

| Column | Type | Description |
|--------|------|-------------|
| `id` | BigInteger | Primary key |
| `primary_enrollment_id` | BigInteger | ID enrollment yang dicek |
| `duplicate_enrollment_id` | BigInteger | ID enrollment duplikat |
| `distance` | Float | IP distance dari Milvus (0-1, higher = more similar) |
| `detected_at` | DateTime | Waktu deteksi |

---

## ⚙️ Configuration

### **Environment Variables**

Tambahkan ke file `.env`:

```env
# Fraud Detection Scheduler
FRAUD_DETECTOR_ENABLED=true
FRAUD_DETECTOR_INTERVAL_SECONDS=30
FRAUD_DETECTOR_BATCH_SIZE=100
FRAUD_DETECTOR_THRESHOLD=0.7
FRAUD_DETECTOR_TOP_K=5
```

### **Configuration Details**

| Variable | Default | Description |
|----------|---------|-------------|
| `FRAUD_DETECTOR_ENABLED` | `true` | Enable/disable scheduler |
| `FRAUD_DETECTOR_INTERVAL_SECONDS` | `30` | Interval eksekusi (detik) |
| `FRAUD_DETECTOR_BATCH_SIZE` | `100` | Jumlah data per batch |
| `FRAUD_DETECTOR_THRESHOLD` | `0.7` | IP distance threshold (>= 0.7 = fraud) |
| `FRAUD_DETECTOR_TOP_K` | `5` | Jumlah hasil search dari Milvus |

---

## 🚀 Deployment

### **1. Install Dependencies**

```bash
pip install -r requirements.txt
```

### **2. Update Database**

Jalankan SQL ini secara manual di SQL Server:

```sql
-- Rename column
EXEC sp_rename 'fraud_cases.similarity_score', 'distance', 'COLUMN';

-- Verify the change
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'fraud_cases' AND COLUMN_NAME = 'distance';
```

### **3. Start Service**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Scheduler akan otomatis start saat aplikasi dijalankan.

---

## 📝 Status Flow

### **check_status States**

```
pending → processing → checked
   ↑          ↓
   └─────── (error & retry < 3)
```

| Status | Description |
|--------|-------------|
| `pending` | Belum diproses / siap untuk diproses ulang |
| `processing` | Sedang diproses oleh scheduler |
| `checked` | Sudah selesai diproses |

### **fraud_status States**

| Status | Description |
|--------|-------------|
| `clean` | Tidak ada duplikasi ditemukan |
| `fraud` | Ada duplikasi ditemukan (distance >= 0.7) |

---

## 🔍 How It Works

### **Distance Metric: Inner Product (IP)**

InsightFace menggunakan **Inner Product** metric:
- Range: 0.0 to 1.0 (normalized embeddings)
- **Higher = More Similar**
- Threshold: **>= 0.7** → Dianggap duplikasi

### **Processing Logic**

1. **Ambil Batch**: Query 100 data dengan status `pending`
2. **Update Status**: Set ke `processing` untuk mencegah double processing
3. **Get Embedding**: Query Milvus untuk mendapatkan embedding vector
4. **Search Similar**: Cari TOP 5 wajah paling mirip
5. **Filter Results**:
   - Skip jika `milvus_id` sama (self)
   - Skip jika `distance < 0.7` (tidak memenuhi threshold)
6. **Save Fraud Cases**: Simpan pasangan yang memenuhi threshold
7. **Update Status**: Set ke `checked` dengan `fraud_status` yang sesuai

### **Contoh Hasil**

```
Enrollment A (id: 100, milvus_id: "abc123")
↓ Search TOP 5 di Milvus
↓ Results:
  - milvus_id: "abc123" → distance: 1.00 ❌ SKIP (self)
  - milvus_id: "def456" → distance: 0.85 ✅ SAVE (>= 0.7)
  - milvus_id: "ghi789" → distance: 0.72 ✅ SAVE (>= 0.7)
  - milvus_id: "jkl012" → distance: 0.65 ❌ SKIP (< 0.7)
  - milvus_id: "mno345" → distance: 0.45 ❌ SKIP (< 0.7)

Result: 2 fraud cases created
```

---

## 🛠️ API Endpoints (Future Enhancement)

Bisa ditambahkan endpoint untuk monitoring scheduler:

### **GET /api/v1/scheduler/status**

Get scheduler status and statistics.

**Response:**
```json
{
  "enabled": true,
  "running": true,
  "interval_minutes": 5,
  "next_run": "2026-01-07T10:30:00Z"
}
```

### **POST /api/v1/scheduler/trigger**

Manually trigger fraud detection job.

---

## 📊 Monitoring & Logging

Scheduler menggunakan **structlog** untuk logging. Contoh log output:

```json
{
  "event": "fraud_detection_job_started",
  "timestamp": "2026-01-07T10:25:00Z"
}

{
  "event": "face_processed",
  "face_id": 12345,
  "milvus_id": "abc123",
  "fraud_status": "fraud",
  "duplicates_found": 2
}

{
  "event": "fraud_detection_job_completed",
  "duration_seconds": 45.2,
  "processed": 100,
  "fraud_detected": 15,
  "clean": 85,
  "errors": 0,
  "fraud_cases_created": 28
}
```

---

## ⚠️ Error Handling

### **Retry Logic**

Jika proses gagal:
- **Attempts < 3**: Reset ke `pending` untuk retry
- **Attempts >= 3**: Set ke `checked` dengan `fraud_status = 'clean'` dan log error

### **Common Errors**

| Error | Solution |
|-------|----------|
| `Milvus connection failed` | Check Milvus service status |
| `Embedding not found` | Check if milvus_id exists in collection |
| `Database connection lost` | Check SQL Server connectivity |

---

## 🔧 Troubleshooting

### **Scheduler tidak berjalan**

Check logs:
```bash
grep "fraud_detector_scheduler" /var/log/dedup-service.log
```

Check environment variables:
```bash
echo $FRAUD_DETECTOR_ENABLED
```

### **Stuck in processing**

Query stuck records:
```sql
SELECT * FROM enrolled_faces 
WHERE check_status = 'processing' 
AND processing_started_at < DATEADD(hour, -1, GETDATE());
```

Reset manually:
```sql
UPDATE enrolled_faces 
SET check_status = 'pending', processing_by = NULL 
WHERE check_status = 'processing' 
AND processing_started_at < DATEADD(hour, -1, GETDATE());
```

---

## 📈 Performance Tips

1. **Adjust Batch Size**: Sesuaikan dengan kapasitas server
2. **Adjust Interval**: Sesuaikan dengan volume data
3. **Monitor Queue**: Pantau jumlah pending enrollments
4. **Database Indexes**: Pastikan indexes sudah optimal

---

## 🎯 Future Enhancements

- [ ] Web UI untuk monitoring scheduler
- [ ] Alert notification (email/webhook)
- [ ] Multiple scheduler workers
- [ ] Automatic stuck process recovery
- [ ] Historical statistics dashboard
- [ ] Manual recheck API endpoint

---

## 📞 Support

Jika ada pertanyaan atau issue, silakan hubungi tim development.
