# ─────────────────────────────────────────────────────────────────────────────
# backend/Dockerfile — multi-stage build for the FastAPI prediction server
# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: install dependencies (cached layer; rebuilds only if requirements change)
# Stage 2: copy source code into a minimal runtime image

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /install

# Install OS build deps required by some Python packages (Prophet needs pystan)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/deps -r requirements.txt


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Security: run as non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install/deps /usr/local

# Copy application source
COPY main.py .
# The ml/ directory must be volume-mounted or the model loaded from S3.
# We don't COPY ml/artifacts here to avoid baking credentials/models into the image.

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

# Health check — Kubernetes liveness probe targets /health
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
