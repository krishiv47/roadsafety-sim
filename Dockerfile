# Road Safety AI System — single-container deployment (Google Cloud Run)
FROM python:3.11-slim

# OpenCV runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole project (frontend source excluded via .dockerignore;
# the built UI in static/ is what gets served)
COPY . .

# Cloud Run routes traffic to this port (deploy with --port=8000)
EXPOSE 8000

# run.py starts the AI service (8001, internal) + simulation (8000, public)
CMD ["python3", "run.py"]
