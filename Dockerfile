FROM python:3.12-slim AS base
 
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
 
WORKDIR /app
 
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
        ca-certificates \
        libsndfile1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*
 
COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /usr/local/bin/uv
 
COPY pyproject.toml uv.lock ./
 
RUN uv sync --frozen --no-dev --no-install-project
 
COPY app ./app
COPY api_server.py main.py ./
COPY models ./models
 
RUN uv sync --frozen --no-dev
 
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser
 
ENV PATH="/app/.venv/bin:$PATH" \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    ENVIRONMENT=production
 
EXPOSE 8000
 
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${API_PORT}/healthz" || exit 1

CMD ["python", "-m", "main.py", "download-files"]
 
CMD ["sh", "-c", "exec uvicorn app.api.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]