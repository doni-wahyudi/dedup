# Fraud Detection Flow - Final Design

## Overview
Service untuk mendeteksi duplikat wajah (fraud detection) dalam batch. Setiap wajah yang pending akan dicek apakah ada duplikat di database dengan membandingkan embedding-nya.

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                   FRAUD DETECTION BATCH PROCESS                 │
└─────────────────────────────────────────────────────────────────┘

STEP 1: GET PENDING FACES
├─ Query DB: SELECT * FROM enrolled_faces WHERE status='pending'
├─ Limit: batch_size (misal 10)
├─ Return: [Face1, Face2, ..., Face10]
└─ Each face punya: id, milvus_id, nik, sentra_id, dll

STEP 2: BULK UPDATE TO PROCESSING
├─ Query: UPDATE enrolled_faces SET status='processing' 
│         WHERE id IN (Face1.id, Face2.id, ..., Face10.id)
├─ Also set: processing_by, processing_started_at, processing_attempts++
└─ Purpose: LOCK (cegah processor lain ambil)

STEP 3: GET EMBEDDINGS FROM MILVUS (BULK)
├─ Extract: milvus_ids = [Face1.milvus_id, Face2.milvus_id, ..., Face10.milvus_id]
├─ Query Milvus: SELECT embedding WHERE id IN (milvus_ids)
├─ Return: {
│    "face1_milvus_id": [0.1, 0.2, 0.3, ...],
│    "face2_milvus_id": [0.4, 0.5, 0.6, ...],
│    ...
│  }
└─ Total query: 1x ke Milvus (efficient)

STEP 4: BATCH SEARCH SIMILAR FACES
├─ Input: embedding vectors dari STEP 3
├─ Query Milvus: search_vector(embeddings, limit=top_k)
│              = search_vector([embedding1, embedding2, ...], limit=5)
├─ Output: untuk SETIAP embedding → top_5 hasil mirip
│  
│  Contoh untuk Face1:
│  ├─ Rank 1: {id: "face1_milvus_id", distance: 1.0}      ← Diri sendiri!
│  ├─ Rank 2: {id: "faceA_milvus_id", distance: 0.95}     ← Mirip
│  ├─ Rank 3: {id: "faceB_milvus_id", distance: 0.92}     ← Mirip
│  ├─ Rank 4: {id: "faceC_milvus_id", distance: 0.78}     ← Kurang mirip
│  └─ Rank 5: {id: "faceD_milvus_id", distance: 0.65}     ← Tidak mirip
│
│  Contoh untuk Face2:
│  ├─ Rank 1: {id: "face2_milvus_id", distance: 1.0}      ← Diri sendiri!
│  └─ Rank 2: {id: "faceE_milvus_id", distance: 0.88}     ← Mirip
│
└─ Total query: 1x ke Milvus (batch search)

STEP 5: FILTER DUPLICATES (PER FACE)
├─ Threshold: 0.7
├─
├─ FOR EACH Face:
│  │
│  ├─ Face1:
│  │  ├─ Hasil search: [(face1, 1.0), (faceA, 0.95), (faceB, 0.92), ...]
│  │  ├─ Filter 1: Hilangkan diri sendiri
│  │  │            IF result.id == face1.milvus_id SKIP
│  │  │            Hasil: [(faceA, 0.95), (faceB, 0.92), (faceC, 0.78), ...]
│  │  ├─ Filter 2: Ambil yang distance >= 0.7 (threshold)
│  │  │            (faceA, 0.95) >= 0.7 ✓ FRAUD
│  │  │            (faceB, 0.92) >= 0.7 ✓ FRAUD
│  │  │            (faceC, 0.78) >= 0.7 ✓ FRAUD (close!)
│  │  │            (faceD, 0.65) < 0.7  ✗ SKIP
│  │  │
│  │  ├─ Duplicates found: [faceA, faceB, faceC]
│  │  ├─ Action: _process_duplicates_for_face(Face1, [faceA, faceB, faceC])
│  │  │         └─ Create FraudCase(Face1→faceA, distance=0.95)
│  │  │         └─ Create FraudCase(Face1→faceB, distance=0.92)
│  │  │         └─ Create FraudCase(Face1→faceC, distance=0.78)
│  │  └─ Return: {is_fraud: true, fraud_count: 3}
│  │
│  ├─ Face2:
│  │  ├─ Hasil search: [(face2, 1.0), (faceE, 0.88)]
│  │  ├─ Filter 1: Hilangkan diri sendiri
│  │  │            Hasil: [(faceE, 0.88)]
│  │  ├─ Filter 2: Ambil yang >= 0.7
│  │  │            (faceE, 0.88) >= 0.7 ✓ FRAUD
│  │  ├─ Duplicates found: [faceE]
│  │  ├─ Action: Create FraudCase(Face2→faceE, distance=0.88)
│  │  └─ Return: {is_fraud: true, fraud_count: 1}
│  │
│  └─ Face3 (example):
│     ├─ Hasil search: [(face3, 1.0), (faceF, 0.65), (faceG, 0.55)]
│     ├─ Filter 1: Hilangkan diri sendiri
│     │            Hasil: [(faceF, 0.65), (faceG, 0.55)]
│     ├─ Filter 2: Ambil yang >= 0.7
│     │            (faceF, 0.65) < 0.7  ✗ SKIP
│     │            (faceG, 0.55) < 0.7  ✗ SKIP
│     ├─ Duplicates found: [] (kosong!)
│     └─ Return: {is_fraud: false, fraud_count: 0}
│
└─ Result: List of per-face results

STEP 6: UPDATE DATABASE & STATS
├─ FOR EACH (Face, Result):
│  │
│  ├─ Face1 (fraud_count=3):
│  │  ├─ Query: UPDATE enrolled_faces 
│  │  │         SET status='checked', fraud_status='fraud'
│  │  │         WHERE id=Face1.id
│  │  ├─ Stats: processed++, fraud_detected++, fraud_cases_created+=3
│  │  └─ Log: "Face1 marked as FRAUD, 3 duplicates found"
│  │
│  ├─ Face2 (fraud_count=1):
│  │  ├─ Query: UPDATE enrolled_faces 
│  │  │         SET status='checked', fraud_status='fraud'
│  │  │         WHERE id=Face2.id
│  │  ├─ Stats: processed++, fraud_detected++, fraud_cases_created+=1
│  │  └─ Log: "Face2 marked as FRAUD, 1 duplicate found"
│  │
│  └─ Face3 (fraud_count=0):
│     ├─ Query: UPDATE enrolled_faces 
│     │         SET status='checked', fraud_status='clean'
│     │         WHERE id=Face3.id
│     ├─ Stats: processed++, clean++
│     └─ Log: "Face3 marked as CLEAN"
│
└─ Final Stats: {processed: 10, fraud_detected: 2, clean: 8, 
                 fraud_cases_created: 4, errors: 0}

STEP 7: ERROR HANDLING (if needed)
├─ IF error saat step 3-5 (per face):
│  ├─ Check: attempts < 3?
│  ├─ YES: reset to pending (coba lagi nanti)
│  └─ NO: mark as clean (give up)
│
├─ IF error saat batch (step 3-4):
│  ├─ Reset ALL faces to pending
│  └─ Retry batch berikutnya

STEP 8: RETURN STATISTICS
├─ Return: {
│    "processed": 10,
│    "fraud_detected": 2,
│    "clean": 8,
│    "errors": 0,
│    "fraud_cases_created": 4
│  }
└─ End of batch
```

---

## Database State Changes

### BEFORE BATCH:
```
enrolled_faces:
┌───────────────────────────────────────┐
│ id  │ status   │ fraud_status │ ...   │
├─────┼──────────┼──────────────┼───────┤
│ 1   │ pending  │ null         │ ...   │
│ 2   │ pending  │ null         │ ...   │
│ 3   │ pending  │ null         │ ...   │
│ 10  │ pending  │ null         │ ...   │
└───────────────────────────────────────┘

fraud_cases: (empty)
```

### AFTER BATCH:
```
enrolled_faces:
┌───────────────────────────────────────┐
│ id  │ status  │ fraud_status │ ...    │
├─────┼─────────┼──────────────┼────────┤
│ 1   │ checked │ fraud        │ ...    │
│ 2   │ checked │ fraud        │ ...    │
│ 3   │ checked │ clean        │ ...    │
│ ... │ checked │ clean/fraud  │ ...    │
│ 10  │ checked │ clean        │ ...    │
└───────────────────────────────────────┘

fraud_cases:
┌─────────────────────────────────────────┐
│ id  │ primary_id │ duplicate_id │ distance │
├─────┼────────────┼──────────────┼──────────┤
│ 1   │ 1          │ A            │ 0.95     │
│ 2   │ 1          │ B            │ 0.92     │
│ 3   │ 1          │ C            │ 0.78     │
│ 4   │ 2          │ E            │ 0.88     │
└─────────────────────────────────────────┘
```

---

## Key Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `batch_size` | Config | Jumlah faces per batch (misal 10) |
| `fraud_threshold` | 0.7 | Minimum distance untuk dianggap duplikat |
| `top_k` | Config | Jumlah top hasil search per face (misal 5) |
| `MAX_RETRY_ATTEMPTS` | 3 | Max retry sebelum give up |

---

## Important Notes

### 1. Self-Elimination
```
Logic: if str(result["id"]) == face.milvus_id:
       then SKIP

Penjelasan: 
- Setiap face search akan mengembalikan diri sendiri di rank 1 
  (karena embedding identik, distance=1.0)
- Kita skip ini untuk tidak membuat FraudCase dengan diri sendiri
```

### 2. Two-Way Fraud Cases
```
Scenario:
- Face1 search → dapat Face2 → save FraudCase(Face1→Face2)
- Face2 search → dapat Face1 → save FraudCase(Face2→Face1)

Result: 2 entries di fraud_cases table (EXPECTED)
```

### 3. Threshold-Based Filtering
```
distance >= 0.7 → FRAUD
distance < 0.7  → CLEAN

Example:
- 0.95 ✓ FRAUD (mirip banget)
- 0.78 ✓ FRAUD (mirip)
- 0.65 ✗ CLEAN (tidak mirip)
```

### 4. Bulk Operations
```
STEP 1: Bulk get embeddings (1x query)
STEP 2: Bulk search similar (1x query)
STEP 3: Bulk update processing (1x query)
STEP 4: Per-face update (N queries, tapi efficient)

Result: Minimal database/Milvus calls
```

### 5. Error Handling & Retry
```
Per-Face Error:
├─ attempts < 3 → reset to pending (coba lagi)
└─ attempts = 3 → mark as clean (give up)

Batch Error:
└─ Reset ALL to pending (whole batch retry)
```

---

## Method Dependencies

```
process_fraud_detection_batch()
├─ enrollment_repo.find_pending_fraud_checks()
├─ enrollment_repo.bulk_update_to_processing()
├─ _check_faces_for_duplicates_batch()
│  ├─ _get_embeddings_by_milvus_ids_batch()
│  │  └─ milvus_client.collection.query()
│  ├─ _batch_search_similar_faces()
│  │  └─ milvus_client.batch_search_similar_faces()
│  └─ _process_duplicates_for_face()
│     ├─ enrollment_repo.find_by_milvus_ids()
│     ├─ fraud_repo.check_existing_fraud_cases_batch()
│     └─ fraud_repo.add()
├─ enrollment_repo.update_check_result()
├─ enrollment_repo.reset_to_pending()
└─ Return stats
```

---

## Return Value

```python
{
    "processed": int,              # Total faces successfully processed
    "fraud_detected": int,         # Faces marked as fraud
    "clean": int,                  # Faces marked as clean
    "errors": int,                 # Faces with errors
    "fraud_cases_created": int     # Total FraudCase records created
}

Example:
{
    "processed": 10,
    "fraud_detected": 2,
    "clean": 8,
    "errors": 0,
    "fraud_cases_created": 4
}
```

---

## Status Transition

```
Initial: pending
        │
        ├─► (STEP 2) processing
        │           │
        │           ├─► (STEP 6) checked + fraud_status='fraud'
        │           │
        │           ├─► (STEP 6) checked + fraud_status='clean'
        │           │
        │           └─► (ERROR) pending ← (retry)
```

---

## Success Path Example

```
Input:
├─ Face1 (milvus_id="m1")
├─ Face2 (milvus_id="m2")
└─ Face3 (milvus_id="m3")

STEP 1: Get pending ✓
├─ Get Face1, Face2, Face3

STEP 2: Bulk update ✓
├─ All faces → processing

STEP 3: Get embeddings ✓
├─ Get embedding for m1, m2, m3 from Milvus

STEP 4: Batch search ✓
├─ Search m1 embedding → top_5 results
├─ Search m2 embedding → top_5 results
├─ Search m3 embedding → top_5 results

STEP 5: Filter duplicates ✓
├─ Face1: [faceA(0.95), faceB(0.92)] → fraud
├─ Face2: [faceC(0.85)] → fraud
├─ Face3: [] → clean

STEP 6: Update & Save ✓
├─ Face1 → fraud_status='fraud', fraud_count=2
├─ Face2 → fraud_status='fraud', fraud_count=1
├─ Face3 → fraud_status='clean', fraud_count=0
├─ Save FraudCase(1→A, 1→B, 2→C)

STEP 8: Return ✓
{
    "processed": 3,
    "fraud_detected": 2,
    "clean": 1,
    "errors": 0,
    "fraud_cases_created": 3
}
```

---

## Config Settings Required

```python
# In settings.py
fraud_detector_batch_size = 10          # Faces per batch
fraud_detector_threshold = 0.7          # Distance threshold
fraud_detector_top_k = 5                # Top-k search results
```
