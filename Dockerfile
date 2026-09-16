# SpotiFetch Dockerfile for Linux Containers
FROM python:3.11-slim

# Prevent Python from writing pyc files to disc & buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (FFmpeg, Curl, Ca-Certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Deno runtime for SpotDL / yt-dlp JS execution
RUN python -m spotdl --download-deno || true

# Copy application source code
COPY . .

# Create downloads and bin directory with proper permissions
RUN mkdir -p /app/downloads /app/bin && chmod -R 777 /app/downloads

# Expose port
EXPOSE 8000

ENV HOST=0.0.0.0
ENV PORT=8000

# Run Uvicorn server
CMD ["python", "main.py"]
