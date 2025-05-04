#!/bin/bash

# Run the database initialization script inside the Docker container
echo "Initializing database..."
cd $(dirname "$0") && docker-compose -p CineTagIt exec app python docker-init-db.py

echo "Database initialization complete."
