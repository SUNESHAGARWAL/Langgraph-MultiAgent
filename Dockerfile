# Multi-Agent Orchestrator Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install the package
RUN pip install -e .

# Create directories
RUN mkdir -p /app/data/logs /app/data/vector_stores /app/data/sessions /app/data/cache

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Expose port for FastAPI (if we add it)
EXPOSE 8000

# Run the application
CMD ["python", "src/main.py"]
