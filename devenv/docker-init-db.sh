#!/bin/bash

# Run the database migration script inside the Docker container
echo "Running database migrations..."
echo "This will create or update the database schema based on the latest migrations."
cd $(dirname "$0") && docker-compose -p cinetagit exec app python /app/devenv/docker-init-db.py

echo "Database migrations complete."
echo "If you need to create new migrations, use: flask db migrate -m 'Description of changes'"
