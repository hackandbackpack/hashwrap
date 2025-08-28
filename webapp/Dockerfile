# Simple Dockerfile for HashWrap Web Interface
FROM python:3.11-slim

# Install system dependencies including hashcat
RUN apt-get update && apt-get install -y \
    hashcat \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p data/uploads data/results wordlists

# Create basic wordlist if none exists
RUN echo -e "password\n123456\npassword123\nadmin\nletmein\nwelcome\nmonkey\n1234567890\nqwerty\nabc123\nPassword1\nadmin123\nroot\ntoor\npass" > wordlists/common-passwords.txt

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/login || exit 1

# Start both web app and worker
CMD python -c "import threading; \
    from app_fixed import app; \
    from hashcat_worker import SimpleHashcatWorker; \
    worker = SimpleHashcatWorker(); \
    worker_thread = threading.Thread(target=worker.start, daemon=True); \
    worker_thread.start(); \
    app.run(host='0.0.0.0', port=5000, debug=False)"