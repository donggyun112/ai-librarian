# Use Python 3.12 slim image
FROM python:3.12-slim

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and set permissions
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Install dependencies
COPY --chown=appuser:appuser uv.lock pyproject.toml ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY --chown=appuser:appuser . .

# Install the project itself
RUN uv sync --frozen --no-dev

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8080
ENV HOST=0.0.0.0

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys, urllib.request, urllib.error; \
    from urllib.error import URLError, HTTPError; \
    import socket; \
    URL = 'http://localhost:8080/health'; \
    TIMEOUT = 5; \
    try: \
    with urllib.request.urlopen(URL, timeout=TIMEOUT) as resp: \
    status = resp.getcode(); \
    sys.exit(0 if 200 <= status < 400 else 1); \
    except (HTTPError, URLError, socket.timeout, Exception): \
    sys.exit(1)" || exit 1


ENTRYPOINT ["sh", "-c", "exec uv run uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8080}"]

