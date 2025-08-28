# Multi-stage build for HashWrap Celery Worker with Hashcat
FROM python:3.11-slim-bullseye as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Download and prepare hashcat
WORKDIR /tmp
RUN wget https://hashcat.net/files/hashcat-6.2.6.tar.gz \
    && tar -xzf hashcat-6.2.6.tar.gz \
    && cd hashcat-6.2.6 \
    && make \
    && make install PREFIX=/opt/hashcat

# Production stage
FROM nvidia/cuda:12.0-runtime-ubuntu22.04 as production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    libpq5 \
    libmagic1 \
    tini \
    ocl-icd-opencl-dev \
    pocl-opencl-icd \
    clinfo \
    mesa-opencl-icd \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy hashcat from builder
COPY --from=builder /opt/hashcat /opt/hashcat
ENV PATH="/opt/hashcat/bin:$PATH"

# Create symbolic link for python3
RUN ln -s /usr/bin/python3.11 /usr/bin/python3 && \
    ln -s /usr/bin/python3.11 /usr/bin/python

# Create non-root user for security
RUN groupadd --gid 1001 hashwrap \
    && useradd --uid 1001 --gid hashwrap --shell /bin/bash --create-home hashwrap

# Create application directories
RUN mkdir -p /app /data/uploads /data/results /data/wordlists /data/rules /logs /tmp/hashcat \
    && chown -R hashwrap:hashwrap /app /data /logs /tmp/hashcat

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=hashwrap:hashwrap . /app/

# Copy parent backend app for shared modules
COPY --chown=hashwrap:hashwrap ../backend/app /app/backend/app

# Copy wordlists and rules from parent directory
COPY --chown=hashwrap:hashwrap ../wordlists /data/wordlists/
COPY --chown=hashwrap:hashwrap ../rules /data/rules/

# Switch to non-root user
USER hashwrap

# Set environment variables for CUDA and OpenCL
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENV CUDA_VISIBLE_DEVICES=0,1,2,3

# Create OpenCL device info at startup
RUN echo '#!/bin/bash\nclinfo > /tmp/hashcat/opencl_devices.txt 2>/dev/null || echo "No OpenCL devices found" > /tmp/hashcat/opencl_devices.txt' > /tmp/hashcat/check_opencl.sh \
    && chmod +x /tmp/hashcat/check_opencl.sh

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=30s --retries=3 \
    CMD python -c "from celery import Celery; c = Celery(); c.control.inspect().active()" || exit 1

# Use tini as init system for proper signal handling
ENTRYPOINT ["tini", "--"]

# Default command (can be overridden)
CMD ["python", "-m", "celery", "-A", "celery_app", "worker", "--loglevel=info", "--concurrency=2", "--queues=hashcat,default"]