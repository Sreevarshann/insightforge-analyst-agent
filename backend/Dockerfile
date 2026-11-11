# InsightForge API. Runs as a non-root user; the SQL sandbox uses bubblewrap when the
# container runtime allows user namespaces, otherwise it reports the "rlimits" level.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends bubblewrap && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev
RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown app /data
USER app
ENV INSIGHTFORGE_DATA_DIR=/data INSIGHTFORGE_API_HOST=0.0.0.0
EXPOSE 8111
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8111/api/health')"
CMD ["uv", "run", "--no-sync", "uvicorn", "insightforge.main:app", "--host", "0.0.0.0", "--port", "8111"]
