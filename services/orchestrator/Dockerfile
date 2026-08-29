FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

# Copy shared code first (for caching)
COPY shared/ /app/shared/
COPY pyproject.toml /app/

# Install Python dependencies
RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx pydantic numpy scipy \
    networkx scikit-learn structlog orjson

# Copy service code
COPY services/orchestrator/ /app/service/

EXPOSE 8000

CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8000"]
