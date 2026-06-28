FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install deps first — this layer is cached until requirements.txt changes
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source as a proper Python package (imports use `from backend.xxx`)
COPY backend/ ./backend/

# Persistent data lives in a named volume mounted here at runtime
RUN mkdir -p data

EXPOSE 8000

# Give the LLM up to 90s to load before declaring unhealthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
