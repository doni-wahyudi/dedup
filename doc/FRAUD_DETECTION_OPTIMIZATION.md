# Fraud Detection Service Optimization

## Overview

Optimasi pada `FraudDetectionService` untuk meningkatkan performance dengan batch processing embedding search di Milvus.

## Masalah Sebelumnya

1. **Sequential Processing**: Setiap face diproses satu per satu dalam loop
2. **Redundant Queries**: 
   - Query individual ke Milvus untuk mendapatkan embedding setiap face
   - Search individual untuk mencari similar faces
   - Query individual ke database untuk duplicate faces
3. **Performance Impact**: Dengan batch size besar, processing menjadi lambat

## Solusi Optimasi

### 1. Batch Processing Architecture

- **Batch Embedding Retrieval**: Ambil semua embedding sekaligus dengan satu query
- **Batch Vector Search**: Search multiple embeddings dalam satu operasi Milvus
- **Batch Database Queries**: Query duplicate faces dan fraud cases dalam batch

### 2. ID Mapping System

Menggunakan Milvus ID sebagai primary key untuk mapping:

```python
# Face -> Milvus ID mapping untuk tracking
milvus_ids = [face.milvus_id for face in faces]

# Batch get embeddings
embeddings_map = {milvus_id: embedding for result in batch_query}

# Batch search dengan multiple vectors
search_results = collection.search(data=query_vectors, ...)

# Map hasil kembali ke face yang benar berdasarkan index
```

### 3. Improved Methods

#### New Batch Methods:
- `_check_faces_for_duplicates_batch()`: Batch processing untuk multiple faces
- `_get_embeddings_by_milvus_ids_batch()`: Batch retrieval embeddings dari Milvus  
- `_batch_search_similar_faces()`: Batch vector search untuk multiple queries
- `_process_duplicates_for_face()`: Optimized duplicate processing per face

#### Enhanced Milvus Client:
- `batch_search_similar_faces()`: Native batch search di MilvusClient

### 4. Backward Compatibility

Method lama tetap tersedia untuk testing dan compatibility:
- `_check_face_for_duplicates()`: Single face check (calls batch method internally)
- `_get_embedding_by_milvus_id()`: Single embedding retrieval

## Performance Benefits

1. **Reduced Network Roundtrips**: 
   - Sebelum: N queries untuk N faces
   - Sekarang: 3 batch queries total (embeddings, search, duplicates)

2. **Better Resource Utilization**: 
   - Milvus batch search lebih efisien
   - Database connection pooling lebih optimal

3. **Consistent ID Tracking**:
   - Tidak ada pencampuran hasil antar faces
   - Milvus ID sebagai reliable identifier

## Usage

Method utama `process_fraud_detection_batch()` tetap sama, optimasi terjadi internal:

```python
# Same interface, optimized internally
stats = fraud_detection_service.process_fraud_detection_batch()
```

## Monitoring

Tambahan logging untuk tracking batch operations:
- `batch_embeddings_retrieved`: Track embedding batch retrieval
- `batch_search_completed`: Track vector search performance  
- `batch_duplicate_check_completed`: Track overall batch performance

## Error Handling

- Individual face errors tidak mengganggu batch
- Graceful fallback untuk faces dengan missing embeddings
- Retry logic tetap berfungsi per face