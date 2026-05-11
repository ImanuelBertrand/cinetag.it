#!/bin/bash
set -e

# 1. Define the Flask App path for the CLI
export FLASK_APP="wsgi.py"

# 2. Use the env variable, or default to production
CONFIG_MODE=${FLASK_ENV:-production}

echo "Running in $CONFIG_MODE mode..."

# 3. Run migrations using the full path to the venv python
python -m flask db upgrade

# 4. Start Gunicorn
GUNICORN_WORKERS=${GUNICORN_WORKERS:-1}
GUNICORN_THREADS=${GUNICORN_THREADS:-8}
echo "Starting Gunicorn (workers=$GUNICORN_WORKERS, threads=$GUNICORN_THREADS)..."
exec python -m gunicorn \
    --bind 0.0.0.0:8000 \
    --worker-class gthread \
    --workers "$GUNICORN_WORKERS" \
    --threads "$GUNICORN_THREADS" \
    "wsgi:app"
