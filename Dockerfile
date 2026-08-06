# Use official Python 3.10 slim image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=7860

# Install system dependencies & Node.js 20
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python packages
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy full repository
COPY . /app

# Build Next.js frontend
WORKDIR /app/frontend
ENV NEXT_PUBLIC_API_URL="http://localhost:8000"
RUN npm ci || npm install \
    && npm run build

# Make start script executable
WORKDIR /app
RUN chmod +x /app/start.sh

# Expose Hugging Face Space port
EXPOSE 7860

# Start application
CMD ["/app/start.sh"]
