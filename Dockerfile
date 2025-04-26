# Dockerfile

    FROM python:3.12-slim-bookworm AS builder

    ENV PYTHONUNBUFFERED=1 \
        PYTHONDONTWRITEBYTECODE=1 \
        UV_CACHE_DIR=/tmp/uv-cache \
        VENV_PATH=/opt/venv
    

    RUN python3 -m venv ${VENV_PATH}
    ENV PATH="${VENV_PATH}/bin:$PATH"
    

    RUN pip install --upgrade pip && pip install uv
    

    WORKDIR /install
    

    COPY pyproject.toml uv.lock* ./
    

    RUN uv pip install --no-cache --group type --group dev

    COPY pyproject.toml .
    RUN uv pip install -r pyproject.toml
    COPY . .

    
    

    FROM python:3.12-slim-bookworm AS runtime
    
    ENV PYTHONUNBUFFERED=1 \
        PYTHONDONTWRITEBYTECODE=1 \
        APP_LOG_LEVEL=INFO \
        VENV_PATH=/opt/venv \
        PYTHONPATH=/app:/app/app
    

    RUN groupadd --system appgroup && useradd --system --gid appgroup --no-create-home appuser
    

    RUN mkdir -p /app && chown -R appuser:appgroup /app
    WORKDIR /app
    

    COPY --from=builder --chown=appuser:appgroup ${VENV_PATH} ${VENV_PATH}
    
    COPY --chown=appuser:appgroup app/ ./app/

    COPY --chown=appuser:appgroup api.py ./api.py

    RUN mkdir -p /app/app/logs && chown appuser:appgroup /app/app/logs
    
    
    ENV PATH="${VENV_PATH}/bin:$PATH" \
        # Point Pydantic Settings to the .env file location inside the container
        # This should be the path where docker-compose mounts the root .env file
        ENV_FILE="/app/.env"
    
    RUN apt-get update && \
        apt-get install -y --no-install-recommends curl && \
        rm -rf /var/lib/apt/lists/*
    
    USER appuser
    
    EXPOSE 8000
    
    HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
        CMD curl -f http://localhost:8000/health || exit 1
    
    CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "api:app", "-b", "0.0.0.0:8000"]
    
    