FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY weaver_ai/ weaver_ai/
COPY tests/ tests/
COPY agents/ agents/
COPY scripts/ scripts/
COPY examples/ examples/
COPY models.yaml .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install pytest pytest-asyncio && \
    pip install -e .

# Expose port
EXPOSE 8000

# Run the server
CMD ["python", "-m", "weaver_ai.main", "--host", "0.0.0.0", "--port", "8000"]
