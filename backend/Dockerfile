# Multi-stage build for HashWrap FastAPI Backend
FROM python:3.11-slim-bullseye as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim-bullseye as production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    libmagic1 \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd --gid 1001 hashwrap \
    && useradd --uid 1001 --gid hashwrap --shell /bin/bash --create-home hashwrap

# Create application directories
RUN mkdir -p /app /data/uploads /data/results /logs \
    && chown -R hashwrap:hashwrap /app /data /logs

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=hashwrap:hashwrap . /app/

# Create read-only root filesystem preparation
RUN mkdir -p /tmp/app-tmp \
    && chown hashwrap:hashwrap /tmp/app-tmp

# Switch to non-root user
USER hashwrap

# Security: Set read-only root filesystem
# Writable directories: /tmp, /data, /logs
VOLUME ["/data", "/logs"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# Use tini as init system for proper signal handling
ENTRYPOINT ["tini", "--"]

# Run application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--access-log", "--log-config", "logging.conf"]