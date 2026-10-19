# syntax=docker/dockerfile:1
# margin in one image: the HTTP API, which also serves the built web UI on the same port.
#
#   docker compose up        then open http://localhost:8000   (see compose.yaml)
#
# The model is not inside the image: by default it is Ollama (or LM Studio...) running on the
# host, or a hosted provider set up on the Settings page.

# ---- 1. the web UI ----------------------------------------------------------------------
FROM node:22-bookworm-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
# empty: the UI calls the API on its own address, because the API serves it
ENV VITE_API_URL=""
RUN npx vite build

# ---- 2. the Python packages (installed, not editable, so no sources are needed later) -----
FROM python:3.12-slim-bookworm AS python
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY packages/ packages/
COPY agents/ agents/
RUN uv sync --frozen --no-dev --all-packages --no-editable

# ---- 3. runtime -------------------------------------------------------------------------
FROM python:3.12-slim-bookworm
# git: the detector reads commit history and clones GitHub repositories.
# safe.directory: folders mounted from the host belong to another user id.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && git config --system safe.directory '*' \
 && useradd --create-home --uid 10001 margin \
 && mkdir -p /data /workspace && chown margin:margin /data

COPY --from=python /app/.venv /app/.venv
COPY --from=ui /ui/dist /app/ui
COPY docker/entrypoint.sh /usr/local/bin/margin-entrypoint

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    MARGIN_API_HOST=0.0.0.0 \
    MARGIN_API_UI_DIR=/app/ui \
    MARGIN_API_CORS_ORIGINS=[] \
    MARGIN_ENV_FILE= \
    MARGIN_CONFIG_FILE=/data/settings.json \
    MARGIN_CACHE_DIR=/data/cache

USER margin
WORKDIR /workspace
EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
ENTRYPOINT ["margin-entrypoint"]
CMD ["margin-api"]
