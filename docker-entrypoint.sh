#!/bin/bash
# Railway entrypoint — ensures PORT is available and starts the app
export PORT="${PORT:-8000}"
echo "Starting TrueFans NEWSLETTERS on port $PORT"
exec python /app/start.py
