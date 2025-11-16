# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy package configuration files
COPY pyproject.toml requirements.txt ./

# Install Python dependencies
# Try pyproject.toml first, fallback to requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    (pip install --no-cache-dir -e . || pip install --no-cache-dir -r requirements.txt)

# Copy source code
COPY src/ ./src/
COPY tests/ ./tests/

# Create necessary directories
RUN mkdir -p /app/logs /app/sessions

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash newsbot && \
    chown -R newsbot:newsbot /app
USER newsbot

# Expose port (if needed for health checks)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the application
CMD ["python", "-m", "src.main"]

