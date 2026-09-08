# K6 Load Testing untuk Dedup Service

Load testing scripts untuk face search API menggunakan k6.

## Prerequisites

Install k6:
```bash
# Ubuntu/Debian
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6

# MacOS
brew install k6

# Docker
docker pull grafana/k6:latest
```

## Test Scripts

### 1. Simple Smoke Test (Recommended untuk mulai)
Test sederhana dengan 5 VUs selama 30 detik:

```bash
# Run dengan dummy image
k6 run k6-simple-test.js

# Run dengan real image
k6 run --env TEST_IMAGE_PATH=/path/to/face.jpg k6-simple-test.js

# Run dengan custom URL
k6 run --env BASE_URL=http://localhost:8000 k6-simple-test.js
```

**What it tests:**
- ✅ Health check endpoint
- ✅ Provider info endpoint
- ✅ Face search endpoint
- ✅ Response time < 3s
- ✅ Error rate < 5%

### 2. Load Test (Progressive ramp-up)
Test dengan progressive load 10 → 20 VUs:

```bash
k6 run k6-load-test.js
```

**Test stages:**
1. Ramp up to 10 VUs (30s)
2. Stay at 10 VUs (1m)
3. Ramp up to 20 VUs (30s)
4. Stay at 20 VUs (1m)
5. Ramp down to 0 (30s)

**Thresholds:**
- 95% requests < 2s
- Error rate < 10%

## Using Real Test Images

Untuk test yang lebih realistis, gunakan image wajah asli:

```bash
# Single image
k6 run --env TEST_IMAGE_PATH=./test-images/face1.jpg k6-simple-test.js

# Test dengan multiple images (TODO: implement)
# k6 run --env TEST_IMAGES_DIR=./test-images k6-load-test.js
```

## Output Explanation

```
✓ health check OK
✓ provider info OK
✓ search endpoint responds

checks.........................: 100.00% ✓ 150  ✗ 0
data_received..................: 45 kB   1.5 kB/s
data_sent......................: 15 kB   500 B/s
http_req_blocked...............: avg=1ms    min=0s   med=0s   max=10ms  p(95)=2ms
http_req_connecting............: avg=0.5ms  min=0s   med=0s   max=5ms   p(95)=1ms
http_req_duration..............: avg=500ms  min=50ms med=400ms max=2s   p(95)=1.5s
  { expected_response:true }...: avg=500ms  min=50ms med=400ms max=2s   p(95)=1.5s
http_req_failed................: 0.00%   ✓ 0    ✗ 50
http_req_receiving.............: avg=1ms    min=0s   med=0s   max=5ms   p(95)=2ms
http_req_sending...............: avg=1ms    min=0s   med=0s   max=5ms   p(95)=2ms
http_req_tls_handshaking.......: avg=0s     min=0s   med=0s   max=0s    p(95)=0s
http_req_waiting...............: avg=498ms  min=48ms med=398ms max=1.99s p(95)=1.49s
http_reqs......................: 50      1.666667/s
iteration_duration.............: avg=3s     min=2.5s med=3s    max=4s    p(95)=3.5s
iterations.....................: 50      1.666667/s
vus............................: 5       min=5  max=5
vus_max........................: 5       min=5  max=5
```

**Key metrics:**
- `http_req_duration`: Response time (target: p95 < 2-3s)
- `http_req_failed`: Error rate (target: < 5-10%)
- `http_reqs`: Total requests
- `checks`: Test assertions passed

## Docker Usage

Jika tidak mau install k6:

```bash
# Simple test
docker run --rm -i --network host \
  -v $(pwd):/scripts \
  grafana/k6:latest run /scripts/k6-simple-test.js

# With real image
docker run --rm -i --network host \
  -v $(pwd):/scripts \
  -v $(pwd)/test-images:/test-images \
  -e TEST_IMAGE_PATH=/test-images/face1.jpg \
  grafana/k6:latest run /scripts/k6-simple-test.js

# Load test
docker run --rm -i --network host \
  -v $(pwd):/scripts \
  grafana/k6:latest run /scripts/k6-load-test.js
```

**Note:** `--network host` agar container bisa akses `localhost:8000`

## Tips

### 1. Monitoring GPU saat load test
Buka terminal terpisah dan jalankan:
```bash
watch -n 1 nvidia-smi
```

### 2. Monitor Docker logs
```bash
docker logs -f dedup-service
```

### 3. Adjust test parameters
Edit `options` di script:
```javascript
export const options = {
  vus: 10,          // Number of virtual users
  duration: '1m',   // Test duration
  iterations: 100,  // Or use iterations instead of duration
};
```

### 4. Custom scenarios
```javascript
export const options = {
  scenarios: {
    spike_test: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 50 },  // Spike to 50
        { duration: '30s', target: 50 },  // Stay at 50
        { duration: '10s', target: 0 },   // Drop to 0
      ],
    },
  },
};
```

## Expected Results

### CPU Mode
- Response time: 1-3s per request
- Throughput: ~5-10 req/s
- GPU usage: 0%

### GPU Mode (InsightFace)
- Response time: 0.2-1s per request
- Throughput: ~20-50 req/s
- GPU usage: 60-90%

### With Milvus + 1M embeddings
- Search time: 50-200ms
- Total response: 0.5-1.5s

## Troubleshooting

### Error: connection refused
Service belum running atau port salah:
```bash
# Check service
curl http://localhost:8000/health

# Change port
k6 run --env BASE_URL=http://localhost:8001 k6-simple-test.js
```

### Too many errors
Service overloaded, kurangi VUs atau tambah think time:
```javascript
sleep(2); // Increase sleep dari 1 ke 2 detik
```

### GPU not utilized
Check apakah InsightFace menggunakan GPU:
```bash
docker exec -it dedup-service python3 -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

## Next Steps

Untuk production load testing yang lebih advanced:
- Grafana dashboard untuk visualisasi realtime
- Cloud load testing (k6 Cloud)
- Distributed load testing (multiple k6 instances)
- Custom metrics dan tags

## References

- [k6 Documentation](https://k6.io/docs/)
- [k6 Examples](https://k6.io/docs/examples/)
- [Test Types](https://k6.io/docs/test-types/introduction/)
