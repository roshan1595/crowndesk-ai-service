# CrownDesk V2 - AI Service Dockerfile

FROM python:3.11-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --only main --no-root

# Copy application code
COPY src ./src

# Add src to Python path
ENV PYTHONPATH=/app/src

EXPOSE 8000

# Run the application
CMD ["uvicorn", "ai_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
