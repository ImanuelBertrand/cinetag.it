#!/bin/bash

# Stop the Docker containers
echo "Stopping Docker containers..."
cd $(dirname "$0")
docker-compose -p CineTagIt down

echo "Docker containers have been stopped."
