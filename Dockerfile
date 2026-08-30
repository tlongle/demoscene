# Lightweight Python Dockerfile for DEMOSCENE
FROM python:3.12-slim

# Prevent python from writing pyc files & buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEMOPALS_DB_PATH=/app/data/demopals.db
ENV ASSETS_DIR=/app/data/assets
ENV PORT=5363

WORKDIR /app

# Install system curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure data and asset storage directories exist
RUN mkdir -p /app/data/assets/demopals /app/data/assets/boxart

EXPOSE 5363

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:5363/api/stats || exit 1

CMD ["python", "start.py"]
