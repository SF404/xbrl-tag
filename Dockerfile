FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Install system build deps required for some Python wheels
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev curl ca-certificates \
    libblas3 liblapack3 libopenblas-dev libomp-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy project files (after installs to leverage cache)
COPY . .

# Upgrade pip first
RUN python -m pip install --upgrade pip

# Install heavy / tricky packages explicitly (torch first from PyTorch index)
# Install everything in as few pip calls as reasonable to reduce image layers.
RUN python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.8.0+cpu \
 && python -m pip install --no-cache-dir \
    "fastapi[standard]" \
    pydantic-settings \
    psycopg2-binary \
    SQLAlchemy \
    sentence-transformers \
    openpyxl \
    faiss-cpu \
    langchain \
    langchain-community \
    alembic

# Create non-root user and adjust ownership (do this AFTER pip install to keep installs system-wide)
RUN useradd --create-home --shell /bin/bash app \
 && chown -R app:app /app

USER app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
