# Recipe for packaging the FastAPI backend into a container.
# Build from the project root:  docker build -f backend/Dockerfile -t job-api .
# Run:                          docker run -p 8000:8000 --env-file .env job-api

# 1. Start from a small Linux image with Python installed
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/models

WORKDIR /app

# 2. System library needed by the embedding model's runtime (onnxruntime)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 3. Install Python libraries first (this layer is cached, so code changes rebuild fast)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 4. Download the embedding model now, so the first request doesn't have to
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/app/models')"

# 5. Copy our code
COPY backend/ backend/

# 6. Don't run as the all-powerful root user (security best practice)
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# 7. Start the API. Render tells us which port to use via $PORT.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
