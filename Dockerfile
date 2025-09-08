FROM python:3.12-slim

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
COPY demo_event_mesh.py .
COPY verify_phase2.py .
COPY models.yaml .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install pytest pytest-asyncio && \
    pip install -e .

# Run tests by default
CMD ["python", "-m", "pytest", "tests/", "-v", "--tb=short"]