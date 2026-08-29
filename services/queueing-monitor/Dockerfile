FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*
COPY shared/ /app/shared/
COPY pyproject.toml /app/
RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx pydantic numpy scipy networkx scikit-learn structlog orjson
COPY services/queueing-monitor/ /app/service/
EXPOSE 8014
CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8014"]
