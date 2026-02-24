#!/bin/bash
set -e

# 1. Define the Flask App path for the CLI
export FLASK_APP="app.create_app:create_app('$FLASK_ENV')"

# 2. Use the env variable, or default to production
CONFIG_MODE=${FLASK_ENV:-production}

echo "Running in $CONFIG_MODE mode..."

# 3. Run migrations using the full path to the venv python
/app/.venv/bin/python -m flask db upgrade

# 4. Start Gunicorn
echo "Starting Gunicorn..."
exec /app/.venv/bin/python -m gunicorn --bind 0.0.0.0:8000 \
    "app.create_app:create_app('$CONFIG_MODE', start_scheduler=True)"