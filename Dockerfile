FROM python:3.14-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only dependency file first (for better caching)
COPY pyproject.toml .

# Install Python dependencies (this layer will be cached unless dependencies change)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Copy application code (won't invalidate dependency cache)
COPY weaver_ai/ weaver_ai/
COPY agents/ agents/
COPY scripts/ scripts/
COPY models.yaml .

# Create non-root user for security
RUN useradd -m -u 1000 weaver && \
    chown -R weaver:weaver /app

USER weaver

# Expose port
EXPOSE 8000

# Add health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the server
CMD ["python", "-m", "weaver_ai.main", "--host", "0.0.0.0", "--port", "8000"]
