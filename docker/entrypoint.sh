#!/bin/bash
set -e

# 1. Define the Flask App path for the CLI
export FLASK_APP="wsgi.py"

# 2. Use the env variable, or default to production
CONFIG_MODE=${FLASK_ENV:-production}

echo "Running in $CONFIG_MODE mode..."

# 3. Always use the venv interpreter by absolute path. Resolving `python` via
# PATH silently falls through to the base image's bare interpreter whenever
# /venv/bin/python is missing or unreadable, surfacing as a baffling
# "No module named flask" instead of the actual problem.
PYTHON=${VENV_PYTHON:-/venv/bin/python}
if [ ! -x "$PYTHON" ]; then
    echo "FATAL: venv interpreter $PYTHON is missing or not executable." >&2
    ls -la "$PYTHON" >&2 || true
    exit 1
fi

# 4. Run migrations
"$PYTHON" -m flask db upgrade

# 5. Start Gunicorn
GUNICORN_WORKERS=${GUNICORN_WORKERS:-2}
GUNICORN_THREADS=${GUNICORN_THREADS:-8}

RELOAD_ARGS=()
if [ "$CONFIG_MODE" = "development" ]; then
    RELOAD_ARGS+=(--reload)
fi

echo "Starting Gunicorn (workers=$GUNICORN_WORKERS, threads=$GUNICORN_THREADS)..."
exec "$PYTHON" -m gunicorn \
    --bind 0.0.0.0:8000 \
    --worker-class gthread \
    --workers "$GUNICORN_WORKERS" \
    --threads "$GUNICORN_THREADS" \
    "${RELOAD_ARGS[@]}" \
    "wsgi:app"
