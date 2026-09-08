# Fraud Detection Service - Flow Explanation

## Visual Flow Diagram

```
╔════════════════════════════════════════════════════════════════╗
║       FRAUD DETECTION SERVICE - process_fraud_detection_batch  ║
╚════════════════════════════════════════════════════════════════╝

┌─ STEP 1: GET PENDING FACES ─────────────────────────────────────┐
│                                                                   │
│  Ambil wajah yang belum dicek fraud dari database               │
│  • Query: SELECT * FROM enrolled_faces WHERE status='pending'   │
│  • Limit: misalnya 10 per batch (batch_size)                   │
│  • Return: List[EnrolledFace] = [Face1, Face2, ..., Face10]    │
│                                                                   │
│  Status Timeline: pending → processing → checked                 │
└───────────────────────────────────────────────────────────────────┘
                              ↓
┌─ STEP 2: MARK AS PROCESSING ───────────────────────────────────┐
│                                                                   │
│  Lock mechanism - cegah processor lain proses wajah yang sama   │
│  • Bulk update: UPDATE enrolled_faces SET status='processing'  │
│  • Set processing_by = processor_id (misal "fraud-detector-1")│
│  • Increment: processing_attempts += 1                         │
│  • Set: processing_started_at = NOW()                          │
│                                                                   │
│  Database sebelum:                                              │
│  ┌────────────────────────────┐                                │
│  │ Face1  | status=pending    │                                │
│  │ Face2  | status=pending    │                                │
│  │ Face10 | status=pending    │                                │
│  └────────────────────────────┘                                │
│                                                                   │
│  Database sesudah:                                              │
│  ┌────────────────────────────┐                                │
│  │ Face1  | status=processing │                                │
│  │ Face2  | status=processing │                                │
│  │ Face10 | status=processing │                                │
│  └────────────────────────────┘                                │
└───────────────────────────────────────────────────────────────────┘
                              ↓
┌─ STEP 3: CHECK DUPLICATES (CORE LOGIC) ───────────────────────┐
│                                                                   │
│  ┌─ 3A: GET ALL EMBEDDINGS FROM MILVUS ──────────────────────┐│
│  │                                                              ││
│  │  Ekstrak vektor (embedding) setiap wajah dari Milvus      ││
│  │  • Input: milvus_ids = ["id1", "id2", ..., "id10"]       ││
│  │  • Query Milvus: SELECT embedding WHERE id IN (...)      ││
│  │  • Return: {                                              ││
│  │      "id1": [0.1, 0.2, 0.3, ...],  // embedding vector  ││
│  │      "id2": [0.4, 0.5, 0.6, ...],                        ││
│  │      ...                                                   ││
│  │    }                                                       ││
│  └──────────────────────────────────────────────────────────┘│
│                           ↓                                      │
│  ┌─ 3B: BATCH SEARCH SIMILAR FACES ─────────────────────────┐│
│  │                                                              ││
│  │  Cari top_k wajah paling mirip untuk setiap embedding    ││
│  │  Input: embedding vectors dari 3A                         ││
│  │  Process: Untuk setiap embedding, cari wajah mirip       ││
│  │  Output: [                                                ││
│  │    [                                                       ││
│  │      {"id": "faceA", "distance": 0.95},  // mirip banget ││
│  │      {"id": "faceB", "distance": 0.92},  // mirip         ││
│  │      {"id": "faceC", "distance": 0.78}   // kurang mirip  ││
│  │    ],                                                      ││
│  │    [                                                       ││
│  │      {"id": "faceD", "distance": 0.88}   // Face2 mirip   ││
│  │    ],                                                      ││
│  │    ...                                                     ││
│  │  ]                                                         ││
│  └──────────────────────────────────────────────────────────┘│
│                           ↓                                      │
│  ┌─ 3C: PROCESS RESULTS FOR EACH FACE ───────────────────────┐│
│  │                                                              ││
│  │  Loop setiap wajah dan hasilnya:                          ││
│  │                                                              ││
│  │  Face1 Results: [faceA(0.95), faceB(0.92), faceC(0.78)]   ││
│  │  ├─ Filter: hapus diri sendiri                             ││
│  │  ├─ Filter: hanya ambil distance >= threshold (0.85)      ││
│  │  ├─ Hasil: [faceA(0.95), faceB(0.92)]  // Duplikat!       ││
│  │  ├─ Action: _process_duplicates_for_face()                ││
│  │  │          → Buat FraudCase(Face1→faceA)                 ││
│  │  │          → Buat FraudCase(Face1→faceB)                 ││
│  │  └─ Return: {is_fraud: true, fraud_count: 2}              ││
│  │                                                              ││
│  │  Face2 Results: [faceD(0.88)]                             ││
│  │  ├─ Filter: hapus diri sendiri                             ││
│  │  ├─ Filter: ambil distance >= 0.85                        ││
│  │  ├─ Hasil: [faceD(0.88)]  // Duplikat!                    ││
│  │  └─ Return: {is_fraud: true, fraud_count: 1}              ││
│  │                                                              ││
│  │  Face10 Results: [...]                                    ││
│  │  ├─ Tidak ada duplikat                                    ││
│  │  └─ Return: {is_fraud: false, fraud_count: 0}             ││
│  └──────────────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────────────────────┘
                              ↓
┌─ STEP 4: PROCESS RESULTS (HANDLE SUCCESS/ERROR) ───────────────┐
│                                                                   │
│  Loop setiap (face, result) dan update database               │
│                                                                   │
│  ┌─ 4A: HANDLE ERROR CASE ────────────────────────────────────┐│
│  │  if result["error"]:                                        ││
│  │                                                              ││
│  │  Contoh: ada error saat checking Face3                    ││
│  │  • Log error                                               ││
│  │  • stats["errors"] += 1                                    ││
│  │  • Check: face.processing_attempts berapa?                ││
│  │                                                              ││
│  │    Attempt 1 → Reset to pending (coba lagi nanti)          ││
│  │    Attempt 2 → Reset to pending (coba lagi nanti)          ││
│  │    Attempt 3 → Reset to pending (coba lagi nanti)          ││
│  │    Attempt 4 → Give up! Mark as "clean"                   ││
│  │                                                              ││
│  │  DB sebelum: Face3 | status=processing | attempts=3       ││
│  │  DB sesudah:                                               ││
│  │    Jika < 3x: Face3 | status=pending | attempts=4         ││
│  │    Jika = 3x: Face3 | status=checked | fraud=clean        ││
│  └──────────────────────────────────────────────────────────┘│
│  ┌─ 4B: HANDLE SUCCESS CASE ──────────────────────────────────┐│
│  │  else:                                                      ││
│  │                                                              ││
│  │  Contoh: Face1 selesai di-check                           ││
│  │  • is_fraud = result["is_fraud"]                          ││
│  │  • fraud_count = result["fraud_count"]                    ││
│  │                                                              ││
│  │  Jika ada duplikat (is_fraud=true):                       ││
│  │    • Update: Face1 status=checked, fraud_status=fraud     ││
│  │    • Stats: fraud_detected += 1                           ││
│  │    • Stats: fraud_cases_created += 2                      ││
│  │                                                              ││
│  │  Jika tidak ada duplikat (is_fraud=false):                ││
│  │    • Update: Face1 status=checked, fraud_status=clean     ││
│  │    • Stats: clean += 1                                    ││
│  │                                                              ││
│  │  DB sebelum: Face1 | status=processing                    ││
│  │  DB sesudah:  Face1 | status=checked | fraud_status=fraud ││
│  └──────────────────────────────────────────────────────────┘│
│  ┌─ 4C: EXCEPTION DALAM LOOP (Per-Face Exception) ────────────┐│
│  │                                                              ││
│  │  try:                                                       ││
│  │    ... process Face1, Face2, Face3, ...                   ││
│  │  except Exception:                                          ││
│  │    # Error terjadi saat processing hasil                  ││
│  │    # Misal: database connection error saat update         ││
│  │    # → Retry logic sama seperti 4A                        ││
│  └──────────────────────────────────────────────────────────┘│
│  ┌─ 4D: OUTER EXCEPTION (Batch-Level Error) ──────────────────┐│
│  │                                                              ││
│  │  except Exception at BATCH LEVEL:                          ││
│  │                                                              ││
│  │  Contoh: Milvus error saat batch search                   ││
│  │  • Log batch error                                         ││
│  │  • Reset SEMUA faces ke pending untuk retry               ││
│  │  • Atau mark semua "clean" jika sudah max attempts        ││
│  │                                                              ││
│  │  for face in pending_faces:                               ││
│  │    if face.processing_attempts < 3:                       ││
│  │      Reset to pending (retry batch berikutnya)            ││
│  │    else:                                                   ││
│  │      Mark as clean (give up)                              ││
│  └──────────────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────────────────────┘
                              ↓
┌─ STEP 5: RETURN STATISTICS ───────────────────────────────────┐
│                                                                   │
│  Return Dict:                                                   │
│  {                                                              │
│    "processed": 8,              // Total selesai sukses        │
│    "fraud_detected": 2,         // Ada duplikat               │
│    "clean": 6,                  // Tidak ada duplikat          │
│    "errors": 2,                 // Ada error                  │
│    "fraud_cases_created": 5     // Total fraud case dibuat    │
│  }                                                              │
└───────────────────────────────────────────────────────────────────┘
```

---

## Status & Attempt Tracking

```
INITIAL STATE (dari query Step 1):
┌─────────────────────────────────────────┐
│ EnrolledFace                             │
├─────────────────────────────────────────┤
│ id  │ status   │ attempts │ fraud_status │
├─────┼──────────┼──────────┼──────────────┤
│ 1   │ pending  │ 0        │ null         │
│ 2   │ pending  │ 0        │ null         │
│ 3   │ pending  │ 0        │ null         │
│ 10  │ pending  │ 0        │ null         │
└─────────────────────────────────────────┘

AFTER STEP 2 (bulk_update_to_processing):
┌─────────────────────────────────────────┐
│ EnrolledFace                             │
├─────────────────────────────────────────┤
│ id  │ status      │ attempts │ fraud_status │
├─────┼─────────────┼──────────┼──────────────┤
│ 1   │ processing  │ 1        │ null         │
│ 2   │ processing  │ 1        │ null         │
│ 3   │ processing  │ 1        │ null         │
│ 10  │ processing  │ 1        │ null         │
└─────────────────────────────────────────┘

AFTER STEP 4 (process results):

Scenario A - Success:
┌─────────────────────────────────────────────┐
│ Face1 → Success (fraud=true)                 │
│ UPDATE: status=checked, fraud_status=fraud  │
└─────────────────────────────────────────────┘

Scenario B - Error, Attempt < 3:
┌─────────────────────────────────────────────┐
│ Face2 → Error (attempts=1)                   │
│ UPDATE: status=pending, attempts=2           │
│ (akan di-process lagi di batch berikutnya)  │
└─────────────────────────────────────────────┘

Scenario C - Error, Attempt = 3:
┌──────────────────────────────────────────────┐
│ Face3 → Error (attempts=3)                    │
│ UPDATE: status=checked, fraud_status=clean   │
│ (give up, mark as clean)                    │
└──────────────────────────────────────────────┘
```

---

## Key Concepts

### Distance Threshold
```
Similarity Score (Distance):
- 1.0  = identical (100% mirip)
- 0.95 = very similar
- 0.85 = threshold ✓ (dianggap duplikat)
- 0.78 = not similar enough ✗
- 0.50 = quite different
- 0.0  = completely different

Jadi: distance >= 0.85 → FRAUD
```

### Retry Logic
```
Max Retry = 3 attempts

Attempt 1 (attempts=0→1):
  - Error? → Reset to pending
  - Success? → Mark checked

Attempt 2 (attempts=1→2):
  - Error? → Reset to pending
  - Success? → Mark checked

Attempt 3 (attempts=2→3):
  - Error? → Reset to pending
  - Success? → Mark checked

Attempt 4 (attempts=3→4):
  - Error? → MARK CLEAN (give up)
  - Success? → Mark checked
```

---

## FraudCase Creation Example

```
Face1 (milvus_id="id1") has duplicates:
  ├─ faceA (distance=0.95) → Create FraudCase(1→A)
  └─ faceB (distance=0.92) → Create FraudCase(1→B)

Result in FraudCase table:
┌──────────────────────────────┐
│ FraudCase                     │
├──────────────────────────────┤
│ id │ primary │ duplicate │ distance │
├────┼─────────┼───────────┼──────────┤
│ 1  │ Face1   │ faceA     │ 0.95     │
│ 2  │ Face1   │ faceB     │ 0.92     │
└──────────────────────────────┘
```

---

## Statistics Return Example

```python
{
    "processed": 8,              # Successfully processed
    "fraud_detected": 2,         # Found duplicates
    "clean": 6,                  # No duplicates found
    "errors": 2,                 # Failed (will retry)
    "fraud_cases_created": 5     # Total pairs marked as fraud
}

Total batch size = processed + errors = 8 + 2 = 10
```
