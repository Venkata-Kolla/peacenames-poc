# ============================================================================
# PEACENAMES POC - DOCKERFILE
# ============================================================================
# This builds the Flask backend container.
# 
# FOR A TYPICAL SOFTWARE ENGINEER:
# Standard Python Docker image with Flask dependencies. Nothing fancy.
# ============================================================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Create upload directory
RUN mkdir -p /app/uploads

# Expose port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=backend/app.py

# Run the application
CMD ["python", "backend/app.py"]
