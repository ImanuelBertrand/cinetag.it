#!/bin/bash

# Stop and remove existing containers first
echo "Stopping and removing existing containers..."
cd $(dirname "$0")
docker-compose -p cinetagit down

# Remove any orphaned containers
echo "Removing any orphaned containers..."
docker-compose -p cinetagit down --remove-orphans

./docker-start.sh

