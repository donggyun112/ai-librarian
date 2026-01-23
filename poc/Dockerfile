# Stage 1: Builder
# Install dependencies and build tools
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install system dependencies required for building (e.g. C extensions)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first to cache this layer
COPY uv.lock pyproject.toml ./

# Install dependencies into a virtual environment
# We use --no-install-project because we only want dependencies here; 
# the source code will be copied in the runner stage.
RUN uv sync --frozen --no-install-project --no-dev


# Stage 2: Runner
# Final minimal image
FROM python:3.12-slim

WORKDIR /app

# Install runtime system dependencies if any (none for now, but kept clean)
# Note: gcc and uv are NOT installed here to reduce size and improve security.

# Create a non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Copy the virtual environment from the builder stage
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
# Add venv bin to PATH (optional if using direct path in ENTRYPOINT, but good practice)
ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8080
ENV HOST=0.0.0.0

# Expose port 8080
EXPOSE 8080

# Use the python executable from the venv directly
# This avoids needing 'uv' in the final image
ENTRYPOINT ["sh", "-c", "exec /app/.venv/bin/uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
