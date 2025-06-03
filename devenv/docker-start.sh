#!/bin/bash

cd $(dirname "$0")

# Start the Docker containers
echo "Starting Docker containers..."
docker compose -p cinetagit up -d

# Print information about the running containers
echo "Docker containers are running:"
docker compose -p cinetagit ps

./docker-init-db.sh

echo "You can access the application at http://localhost:5000"
echo "You can access the MailHog UI at http://localhost:8025"
echo "Note: The application may take a moment to start as it waits for the database to be ready"
