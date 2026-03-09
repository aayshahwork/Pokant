# ── Stage 1: build dependencies ───────────────────────────────────────────
FROM python:3.10-slim AS builder

WORKDIR /build

# System packages needed to compile Python extensions.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into an isolated prefix so we can copy only
# the site-packages into the final image (keeps the layer small).
COPY pyproject.toml ./
# Fallback requirements file generated from Poetry for non-Poetry builds.
COPY requirements*.txt* ./

RUN pip install --upgrade pip \
    && pip install --prefix=/install \
        anthropic \
        "browser-use>=1.0.0" \
        playwright \
        pydantic \
        "pydantic-settings" \
        click \
        rich \
        python-dotenv \
        pillow \
        fastapi \
        "uvicorn[standard]" \
        celery \
        redis \
        asyncpg \
        boto3 \
        aioboto3 \
        aiohttp \
        httpx \
        requests \
        langchain-anthropic


# ── Stage 2: runtime image ─────────────────────────────────────────────────
FROM python:3.10-slim AS runtime

# Labels for container registries and tooling.
LABEL org.opencontainers.image.title="ComputerUse API" \
      org.opencontainers.image.description="One API to automate any web workflow" \
      org.opencontainers.image.version="0.1.0"

WORKDIR /app

# Runtime system dependencies: Playwright needs these shared libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
        # Playwright Chromium dependencies
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        # Fonts (prevents blank pages on headless renders)
        fonts-liberation \
        # Process utilities used by Playwright
        ca-certificates \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the builder stage.
COPY --from=builder /install /usr/local

# Install Playwright browser binaries.  Only Chromium is needed;
# skipping Firefox and WebKit saves ~300 MB of image size.
RUN playwright install chromium \
    && playwright install-deps chromium

# Create a non-root user so the container doesn't run as root.
RUN groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid appuser --no-create-home appuser

# Copy application source.
COPY computeruse/ ./computeruse/
COPY backend/     ./backend/

# Create runtime directories with correct ownership.
RUN mkdir -p sessions replays \
    && chown -R appuser:appuser /app

USER appuser

# FastAPI will listen on this port; must match docker-compose and any
# reverse-proxy configuration.
EXPOSE 8000

# Health check so orchestrators know when the container is ready.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:8000/health || exit 1

# Default command: start the API server.
# Workers (Celery) override this in docker-compose.yml.
CMD ["uvicorn", "backend.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info"]
