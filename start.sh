#!/bin/bash
set -e

# Start FastAPI Backend in background on port 8000
echo "🚀 Starting FastAPI IDP Backend on port 8000..."
cd /app/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Start Next.js Frontend in foreground on Hugging Face port 7860
echo "🌐 Starting Next.js Frontend on port 7860..."
cd /app/frontend
PORT=7860 NEXT_PUBLIC_API_URL="http://localhost:8000" npm start
