#!/bin/bash
# Run insightface provider on port 8001
echo "Starting insightface provider (IP) on port 8001..."
source /home/david/Documents/2026/talaud/dedup-service/.venv/bin/activate
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$(python3 -c "import nvidia.cudnn; print(nvidia.cudnn.__path__[0])")/lib
uvicorn app.main:app --host 0.0.0.0 --port 8002 --env-file .env.insightface_ip
