# Use NVIDIA CUDA runtime image (lighter than devel, sufficient for inference)
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    CUDA_VISIBLE_DEVICES=0 \
    INSIGHTFACE_WARMUP_IMAGE_PATH=/app/warmup/face.jpg \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libgomp1 \
    libgl1-mesa-glx \
    libcudnn9-cuda-12 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies with no cache
RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y onnxruntime onnxruntime-gpu && \
    pip install --no-cache-dir onnxruntime-gpu==1.23.2

# Copy application code
COPY . .

# Warmup image location for full InsightFace startup warmup
RUN mkdir -p /app/warmup

# Copy warmup image for startup full-pipeline inference (optional, improves first-request latency)
COPY warmup/ /app/warmup/

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]