# All dependencies and base images are locked; writes at runtime stay in /data and /tmp.
FROM node:22-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS webui
WORKDIR /webui
COPY webui/package*.json ./
RUN npm ci
COPY webui/ ./
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends potrace libfreetype6 libbrotli1 zlib1g \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.12.7
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY packages/core/ packages/core/
COPY packages/service/ packages/service/
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config libbrotli-dev zlib1g-dev \
    && uv sync --locked --no-dev --package glyphlab-service --extra qa \
    && useradd --uid 10001 --create-home app \
    && mkdir -p /data && chown 10001:10001 /data \
    && uv cache clean \
    && apt-get purge -y --auto-remove build-essential pkg-config libbrotli-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=webui /webui/dist /app/webui-dist
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    GLYPHLAB_DATA_DIR=/data GLYPHLAB_WEBUI_DIST=/app/webui-dist GLYPHLAB_ENVIRONMENT=prod \
    XDG_CACHE_HOME=/tmp/cache
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')"]
ENTRYPOINT ["python", "-m", "glyphlab_service.entry"]
