# Docker GPU Setup untuk InsightFace

Panduan lengkap untuk menjalankan Dedup Service dengan GPU support menggunakan Docker.

## Optimizations Applied

✅ **InsightFace Only** - Fokus pada InsightFace, dlib dependencies dihapus  
✅ **GPU Accelerated** - CUDA 12.1 + cuDNN8 + ONNX Runtime GPU  
✅ **Lightweight Build** - Removed cmake, build-essential, git (tidak diperlukan)  
✅ **Simple Logging** - Logs ke stdout, gunakan `docker logs` untuk monitoring  
✅ **Model Caching** - InsightFace models di-cache di host `~/.insightface/`

## Prerequisites

### 1. NVIDIA Driver
Pastikan NVIDIA driver sudah terinstall di host machine:
```bash
nvidia-smi
```

Jika belum terinstall, install NVIDIA driver:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y nvidia-driver-535  # atau versi terbaru

# Reboot setelah install
sudo reboot
```

### 2. NVIDIA Container Toolkit
Install NVIDIA Container Toolkit untuk Docker GPU support:

```bash
# Setup repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 3. Verifikasi GPU Support
Test apakah Docker bisa menggunakan GPU:
```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

Jika berhasil, Anda akan melihat output dari `nvidia-smi`.

## Build dan Run

### 1. Build Docker Image
```bash
docker build -t dedup-service:gpu .
```

### 2. Run Containers dengan GPU

#### Setup Custom Docker Network (untuk Milvus connectivity)
```bash
docker network create dedup-network
```

#### Environment Files Setup
Buat 4 environment files untuk masing-masing scheduler instance:

```bash
# .env.scheduler-0 (Scheduler 0 dengan API endpoint)
SCHEDULER_ID=0
FRAUD_DETECTOR_TOTAL_SCHEDULERS=4
DB_SERVER=<your-mssql-host>
DB_PORT=1433
DB_NAME=enrollment_db
DB_USERNAME=sa
DB_PASSWORD=<your-password>
MILVUS_HOST=<your-milvus-host>
MILVUS_PORT=19530
MILVUS_USER=devuser
MILVUS_PASSWORD=<your-password>
FRAUD_DETECTOR_ENABLED=true
FRAUD_DETECTOR_INTERVAL_SECONDS=30
FRAUD_DETECTOR_BATCH_SIZE=1000
FRAUD_DETECTOR_TOP_K=5
FRAUD_DETECTOR_THRESHOLD=0.7

# .env.scheduler-1, .env.scheduler-2, .env.scheduler-3 (sama, hanya ubah SCHEDULER_ID)
# Copy .env.scheduler-0 dan ganti SCHEDULER_ID untuk masing-masing instance
```

#### Run 4 Scheduler Instances

**Scheduler 0 (API endpoint + fraud detection worker):**
```bash
docker run -d \
  --name dedup-scheduler-0 \
  --gpus all \
  -p 8000:8000 \
  --env-file .env.insightface_ip \
  --env-file .env.scheduler-0 \
  --network milvus \
  -v ~/.insightface:/root/.insightface \
  --restart unless-stopped \
  dedup-service:gpu
```

**Scheduler 1 (Background fraud detection worker):**
```bash
docker run -d \
  --name dedup-scheduler-1 \
  --gpus all \
  --env-file .env.insightface_ip \
  --env-file .env.scheduler-1 \
  --network milvus \
  -v ~/.insightface:/root/.insightface \
  --restart unless-stopped \
  dedup-service:gpu
```

**Scheduler 2 (Background fraud detection worker):**
```bash
docker run -d \
  --name dedup-scheduler-2 \
  --gpus all \
  --env-file .env.insightface_ip \
  --env-file .env.scheduler-2 \
  --network milvus \
  -v ~/.insightface:/root/.insightface \
  --restart unless-stopped \
  dedup-service:gpu
```

**Scheduler 3 (Background fraud detection worker):**
```bash
docker run -d \
  --name dedup-scheduler-3 \
  --gpus all \
  --env-file .env.insightface_ip \
  --env-file .env.scheduler-3 \
  --network milvus \
  -v ~/.insightface:/root/.insightface \
  --restart unless-stopped \
  dedup-service:gpu
```

### Penjelasan Parameters:
- `--gpus all`: Gunakan semua GPU yang tersedia
- `-p 8000:8000`: Hanya expose port 8000 pada scheduler-0 (API endpoint)
- `--env-file .env.insightface_ip`: Load base/global environment variables
- `--env-file .env.scheduler-{0,1,2,3}`: Load scheduler-specific environment variables (override base)
- `--network dedup-network`: Koneksi ke custom Docker network untuk komunikasi dengan Milvus/MSSQL
- `-v ~/.insightface:/root/.insightface`: Cache model InsightFace (model ~600MB akan di-download sekali)
- `--restart unless-stopped`: Auto-restart jika crash

#### Konfigurasi Koneksi Milvus/MSSQL
Update `.env.scheduler-*` dengan host/port yang sesuai:
- **Docker network local**: Gunakan service/container name (e.g., `milvus:19530`)
- **Docker network external**: Gunakan IP/hostname dan port yang accessible dari host
- **MSSQL**: Sesuaikan `DB_SERVER`, `DB_PORT`, kredensial

Contoh untuk Milvus di container terpisah dengan network `dedup-network`:
```bash
MILVUS_HOST=milvus  # gunakan container name
MILVUS_PORT=19530
```

> **Note**: Log output langsung ke stdout/stderr, gunakan `docker logs` untuk melihat log.

## Verifikasi GPU Usage

### 1. Check GPU di dalam container
```bash
# Masuk ke container scheduler-0 (contoh)
docker exec -it dedup-scheduler-0 bash

# Check GPU
nvidia-smi

# Test Python ONNX Runtime GPU
python3 -c "import onnxruntime as ort; print('Available providers:', ort.get_available_providers())"
```

Output yang diharapkan harus include `CUDAExecutionProvider`.

### 2. Monitor GPU Usage
```bash
# Di host machine
watch -n 1 nvidia-smi

# Atau
nvidia-smi dmon
```

Saat service melakukan face detection/embedding extraction, Anda akan melihat GPU usage meningkat di semua container.

### 3. Check Application Logs (Multiple Containers)
```bash
# Log dari scheduler-0 (dengan API endpoint)
docker logs -f dedup-scheduler-0

# Log dari scheduler-1 (worker)
docker logs -f dedup-scheduler-1

# Kombinasi log dari semua scheduler (gunakan docker-compose atau dashboard tool)
# Cari log yang menunjukkan:
# - "scheduler_configured scheduler_id=0 total_schedulers=4"
# - "fraud_detection_batch_started scheduler_id=0"
# - "onnxruntime_providers ... gpu_available=True"
```

### 4. Check Scheduler Distribution
```bash
# Verify modulo distribution dengan log
docker logs dedup-scheduler-0 | grep "modulo_filter_applied"
docker logs dedup-scheduler-1 | grep "modulo_filter_applied"
docker logs dedup-scheduler-2 | grep "modulo_filter_applied"
docker logs dedup-scheduler-3 | grep "modulo_filter_applied"

# Setiap scheduler hanya memproses faces dengan (enrollment_id % 4) == SCHEDULER_ID
# Contoh:
# - Scheduler-0: processes faces dengan id % 4 == 0
# - Scheduler-1: processes faces dengan id % 4 == 1
# - Scheduler-2: processes faces dengan id % 4 == 2
# - Scheduler-3: processes faces dengan id % 4 == 3
```

## Quick Start: Deploy 4 Schedulers

### Step 1: Build Image
```bash
docker build -t dedup-service:gpu .
```

### Step 2: Create Docker Network
```bash
docker network create dedup-network
```

### Step 3: Create Environment Files
```bash
# Create base template
cat > .env.scheduler-base << 'EOF'
APP_NAME=dedup-service
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
DB_SERVER=milvus  # Update sesuai MSSQL host
DB_PORT=1433
DB_NAME=enrollment_db
DB_SCHEMA=enrollment
DB_USERNAME=sa
DB_PASSWORD=YourStrongPassword123
MILVUS_HOST=milvus  # Update sesuai Milvus host
MILVUS_PORT=19530
MILVUS_USER=devuser
MILVUS_PASSWORD=YourMilvusPassword123
FRAUD_DETECTOR_ENABLED=true
FRAUD_DETECTOR_INTERVAL_SECONDS=30
FRAUD_DETECTOR_BATCH_SIZE=1000
FRAUD_DETECTOR_TOP_K=5
FRAUD_DETECTOR_THRESHOLD=0.7
FRAUD_DETECTOR_TOTAL_SCHEDULERS=4
EOF

# Generate 4 scheduler env files
for i in 0 1 2 3; do
  cp .env.scheduler-base .env.scheduler-$i
  echo "FRAUD_DETECTOR_SCHEDULER_ID=$i" >> .env.scheduler-$i
done
```

### Step 4: Run 4 Schedulers
```bash
# Scheduler 0 (API endpoint)
docker run -d \
  --name dedup-scheduler-0 \
  --gpus all \
  -p 8000:8000 \
  --env-file .env.insightface_ip \
  --env-file .env.scheduler-0 \
  --network dedup-network \
  -v ~/.insightface:/root/.insightface \
  --restart unless-stopped \
  dedup-service:gpu

# Schedulers 1-3 (background workers)
for i in 1 2 3; do
  docker run -d \
    --name dedup-scheduler-$i \
    --gpus all \
    --env-file .env.insightface_ip \
    --env-file .env.scheduler-$i \
    --network dedup-network \
    -v ~/.insightface:/root/.insightface \
    --restart unless-stopped \
    dedup-service:gpu
done
```

### Step 5: Verify Deployment
```bash
# Check containers running
docker ps | grep dedup-scheduler

# Check logs
docker logs dedup-scheduler-0

# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs
```

---

## Troubleshooting

### Scheduler Connectivity Issues

**Problem**: Containers tidak bisa connect ke Milvus atau MSSQL

**Solution**:
1. Verifikasi network connectivity:
   ```bash
   # Test dari container
   docker exec dedup-scheduler-0 bash -c "nc -zv milvus 19530"
   docker exec dedup-scheduler-0 bash -c "sqlcmd -S DB_SERVER -U sa"
   ```

2. Update `.env.scheduler-*` dengan IP/host yang accessible:
   ```bash
   # Jika services di container terpisah dengan Docker network
   MILVUS_HOST=milvus  # atau service name
   DB_SERVER=mssql     # atau service name
   
   # Jika services di server eksternal
   MILVUS_HOST=192.168.1.100
   DB_SERVER=192.168.1.101
   ```

3. Check DNS resolution di container:
   ```bash
   docker exec dedup-scheduler-0 nslookup milvus  # atau hostname lain
   ```

### Scheduler Distribution Not Working

**Problem**: Semua scheduler memproses faces yang sama, bukan di-distribute

**Solution**:
1. Verifikasi SCHEDULER_ID di setiap container:
   ```bash
   docker exec dedup-scheduler-0 env | grep FRAUD_DETECTOR
   docker exec dedup-scheduler-1 env | grep FRAUD_DETECTOR
   docker exec dedup-scheduler-2 env | grep FRAUD_DETECTOR
   docker exec dedup-scheduler-3 env | grep FRAUD_DETECTOR
   ```

2. Check logs untuk modulo filter:
   ```bash
   docker logs dedup-scheduler-0 | grep "modulo_filter"
   docker logs dedup-scheduler-1 | grep "modulo_filter"
   ```

3. Verifikasi settings:
   ```bash
   docker exec dedup-scheduler-0 python -c "from app.config.settings import settings; print(f'ID={settings.fraud_detector_scheduler_id}, Total={settings.fraud_detector_total_schedulers}')"
   ```

### GPU atau Port Conflicts

**Problem**: Port sudah terpakai, atau GPU error

**Solution**:
```bash
# Check port 8000 usage
netstat -tuln | grep 8000

# Stop conflicting containers
docker stop $(docker ps -q)

# Change port untuk scheduler-0
docker run -d \
  --name dedup-scheduler-0 \
  -p 8001:8000  # Map 8001->8000 jika 8000 busy
  ...
```

### Schedulers Stop/Crash Loop

**Problem**: Container crash atau restart terus-menerus

**Solution**:
1. Check logs dengan verbose:
   ```bash
   docker logs -f dedup-scheduler-0
   ```

2. Increase memory if needed:
   ```bash
   docker run -d \
     --name dedup-scheduler-0 \
     --gpus all \
     -m 8g  # Increase dari 4g ke 8g
     ...
   ```

### GPU tidak terdeteksi di container

**Problem**: `CUDAExecutionProvider` tidak ada di available providers

**Solution**:
1. Verifikasi NVIDIA driver:
   ```bash
   nvidia-smi
   ```

2. Verifikasi NVIDIA Container Toolkit:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
   ```

3. Rebuild image dengan `--no-cache`:
   ```bash
   docker build --no-cache -t dedup-service:gpu .
   ```

### CUDA Out of Memory

**Problem**: GPU memory habis saat processing batch

**Solution**:
1. Kurangi batch size di `.env.scheduler-*`:
   ```
   FRAUD_DETECTOR_BATCH_SIZE=500  # dari 1000 ke 500
   ```

2. Kurangi jumlah schedulers atau redistribute GPU
3. Monitor GPU memory:
   ```bash
   nvidia-smi --query-gpu=memory.used,memory.total --format=csv -l 1
   ```

2. Batasi jumlah worker Uvicorn (di Dockerfile atau runtime):
   ```bash
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
   ```

3. Monitor GPU memory:
   ```bash
   nvidia-smi --query-gpu=memory.used,memory.total --format=csv -l 1
   ```

### InsightFace model download lambat

**Problem**: Model download lambat saat pertama kali start

**Solution**:
Model akan di-cache di volume `~/.insightface`. Setelah pertama kali download, start berikutnya akan lebih cepat.

Atau pre-download model:
```bash
# Di host machine
mkdir -p ~/.insightface/models
cd ~/.insightface/models

# Download model buffalo_l (default model)
wget https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip
unzip buffalo_l.zip
```

### Permission issues dengan model cache

**Problem**: Permission denied saat download/cache model InsightFace

**Solution**:
```bash
# Beri permission ke cache directory
mkdir -p ~/.insightface
chmod -R 755 ~/.insightface/

# Atau jalankan container dengan user ID yang sesuai
docker run --user $(id -u):$(id -g) ...
```

## Performance Tuning

### 1. Optimize InsightFace Detection Size
Di `app/core/biometrics/insightface.py`, adjust `det_size`:
```python
self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))  # Default
# Untuk lebih cepat: det_size=(320, 320)
# Untuk lebih akurat: det_size=(1024, 1024)
```

### 2. Optimize Milvus Settings
Di `.env.insightface_ip`:
```bash
# Untuk search lebih cepat (trade-off accuracy)
MILVUS_INSIGHTFACE_HNSW_M=8
MILVUS_INSIGHTFACE_HNSW_EF_CONSTRUCTION=100

# Untuk accuracy lebih tinggi (trade-off speed)
MILVUS_INSIGHTFACE_HNSW_M=32
MILVUS_INSIGHTFACE_HNSW_EF_CONSTRUCTION=400
```

### 3. Optimize Batch Processing
Di `.env.insightface_ip`:
```bash
# Sesuaikan dengan GPU memory Anda
FRAUD_DETECTOR_BATCH_SIZE=100  # Untuk GPU 8GB+
FRAUD_DETECTOR_BATCH_SIZE=50   # Untuk GPU 4GB
FRAUD_DETECTOR_BATCH_SIZE=25   # Untuk GPU 2GB
```

## Monitoring dan Maintenance

### Health Check
```bash
# Check health endpoint
curl http://localhost:8000/health

# Check API documentation
open http://localhost:8000/docs
```

### Logs
```bash
# Application logs
docker logs -f dedup-service

# Logs dengan timestamp
docker logs -f -t dedup-service

# Last 100 lines
docker logs --tail 100 dedup-service
```

### Resource Usage
```bash
# Container stats
docker stats dedup-service

# GPU stats
nvidia-smi dmon -s pucvmet
```

## Container Management (Multiple Instances)

### Stop All Schedulers
```bash
for i in 0 1 2 3; do
  docker stop dedup-scheduler-$i
done
```

### Start All Schedulers
```bash
for i in 0 1 2 3; do
  docker start dedup-scheduler-$i
done
```

### Restart All Schedulers
```bash
for i in 0 1 2 3; do
  docker restart dedup-scheduler-$i
done
```

### Remove All Schedulers (dan network)
```bash
# Stop dan remove containers
for i in 0 1 2 3; do
  docker rm -f dedup-scheduler-$i
done

# Remove network
docker network rm dedup-network
```

### View Combined Logs
```bash
# View logs dari scheduler-0 dengan timestamp
docker logs -t -f dedup-scheduler-0

# View logs dari semua scheduler (opsional, gunakan tool khusus untuk monitor)
# Saat production, gunakan: docker logs -f, ELK stack, Datadog, atau lainnya
```

### Resource Usage untuk 4 Schedulers
```bash
# Check semua container stats
docker stats dedup-scheduler-0 dedup-scheduler-1 dedup-scheduler-2 dedup-scheduler-3

# GPU utilization per container (catat GPU ID yang digunakan)
nvidia-smi dmon -s pucvmet
```

## Production Considerations

### 1. Multi-Instance Fraud Detection Setup
Untuk production, jalankan 4 concurrent scheduler instances untuk better throughput:

**Performa estimation:**
- 1000 pending fraud checks per batch cycle (30 detik)
- Dengan 4 schedulers: ~250 faces per scheduler per cycle
- Distribution: Modulo-based (enrollment_id % 4 == scheduler_id)
- GPU utilization: 4x container dapat berbagi GPU resources

### 2. Resource Limits untuk 4 Schedulers
Jalankan dengan resource limits per container:

```bash
# Scheduler 0 (API endpoint + worker)
docker run -d \
  --name dedup-scheduler-0 \
  --gpus 1 \
  --cpus="2" \
  --memory="4g" \
  --memory-swap="4g" \
  -p 8000:8000 \
  --env-file .env.insightface_ip \
  --env-file .env.scheduler-0 \
  --network dedup-network \
  -v ~/.insightface:/root/.insightface \
  --restart always \
  dedup-service:gpu

# Scheduler 1-3 (worker only)
for i in 1 2 3; do
  docker run -d \
    --name dedup-scheduler-$i \
    --gpus 1 \
    --cpus="2" \
    --memory="4g" \
    --memory-swap="4g" \
    --env-file .env.insightface_ip \
    --env-file .env.scheduler-$i \
    --network dedup-network \
    -v ~/.insightface:/root/.insightface \
    --restart always \
    dedup-service:gpu
done
```

**Resource allocation guide:**
- 1 GPU per container: Lebih stable dan predictable
- 2 CPU per container: Cukup untuk 1 fraud detection batch cycle
- 4GB mem per container: Cocok untuk batch size 1000

### 3. Multiple GPUs (untuk 4 schedulers)
Jika memiliki 4+ GPU, alokasi 1 GPU per scheduler:

```bash
# Scheduler 0 -> GPU 0
docker run -d --gpus '"device=0"' --name dedup-scheduler-0 ...

# Scheduler 1 -> GPU 1
docker run -d --gpus '"device=1"' --name dedup-scheduler-1 ...

# Scheduler 2 -> GPU 2
docker run -d --gpus '"device=2"' --name dedup-scheduler-2 ...

# Scheduler 3 -> GPU 3
docker run -d --gpus '"device=3"' --name dedup-scheduler-3 ...
```

Jika kurang GPUs, Docker akan time-share GPU resources otomatis.

### 4. Environment File Template (.env.scheduler-X)
```bash
# Application
APP_NAME=dedup-service
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database (MSSQL)
DB_SERVER=<mssql-hostname-or-ip>
DB_PORT=1433
DB_NAME=enrollment_db
DB_SCHEMA=enrollment
DB_USERNAME=sa
DB_PASSWORD=<your-strong-password>
DB_POOL_SIZE=10

# Milvus Vector DB
MILVUS_HOST=<milvus-hostname-or-ip>
MILVUS_PORT=19530
MILVUS_USER=devuser
MILVUS_PASSWORD=<your-password>
MILVUS_COLLECTION=enrollment_embeddings

# Fraud Detection (Scheduler)
FRAUD_DETECTOR_ENABLED=true
FRAUD_DETECTOR_INTERVAL_SECONDS=30
FRAUD_DETECTOR_BATCH_SIZE=1000
FRAUD_DETECTOR_TOP_K=5
FRAUD_DETECTOR_THRESHOLD=0.7
FRAUD_DETECTOR_SCHEDULER_ID=0            # Change per instance (0, 1, 2, 3)
FRAUD_DETECTOR_TOTAL_SCHEDULERS=4

# Face Recognition
FACE_RECOGNITION_PROVIDER=insightface
FACE_DETECTION_THRESHOLD=0.6
IMAGE_MAX_SIZE=1920
ALLOW_MULTIPLE_FACES=false
```

### 5. Network Configuration
Untuk production setup dengan Milvus di container terpisah:

```bash
# Option 1: All services di Docker network (recommended)
docker network create dedup-network

# Option 2: Jika Milvus/MSSQL di server berbeda
# Update .env.scheduler-* dengan IP yang accessible dari Docker
# Example:
MILVUS_HOST=192.168.1.100
MILVUS_PORT=19530
DB_SERVER=192.168.1.101
DB_PORT=1433
```

### 6. Backup Model Cache
```bash
# Backup InsightFace model cache (~600MB, untuk cepat restore)
tar czf insightface_models_backup.tar.gz ~/.insightface/

# Restore
tar xzf insightface_models_backup.tar.gz -C ~
```

### 7. Monitoring Scheduler Distribution
Verifikasi bahwa 4 schedulers bekerja dengan baik:

```bash
# Check logs dari masing-masing scheduler untuk scheduler_id
docker logs dedup-scheduler-0 | grep "scheduler_configured"
docker logs dedup-scheduler-1 | grep "scheduler_configured"
docker logs dedup-scheduler-2 | grep "scheduler_configured"
docker logs dedup-scheduler-3 | grep "scheduler_configured"

# Contoh output yang diharapkan:
# [scheduler_configured] scheduler_id=0 total_schedulers=4 modulo_enabled=true
# [scheduler_configured] scheduler_id=1 total_schedulers=4 modulo_enabled=true
# ...

# Monitor fraud detection batches
docker logs -f dedup-scheduler-0 | grep "fraud_detection_batch"
```

## References

- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- [InsightFace Documentation](https://github.com/deepinsight/insightface)
- [ONNX Runtime GPU](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html)
- [Docker GPU Support](https://docs.docker.com/config/containers/resource_constraints/#gpu)
