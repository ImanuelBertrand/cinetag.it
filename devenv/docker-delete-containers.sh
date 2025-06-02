#!/bin/bash

# Script to delete all Docker containers for the CineTagIt project
# This script will:
# 1. Stop all running containers
# 2. Remove all containers

# Exit on error
set -e

# Get the directory of this script
SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR"

echo "=== Stopping and removing Docker containers ==="
# Stop and remove containers, networks, and images created by docker-compose
docker-compose -p cinetagit down

echo "=== Checking for any remaining containers ==="
# Get all containers with the project name (in case any weren't removed by docker-compose down)
REMAINING_CONTAINERS=$(docker ps -a --filter "name=CineTagIt" -q)

# If there are any remaining containers, remove them
if [ -n "$REMAINING_CONTAINERS" ]; then
    echo "=== Removing remaining containers ==="
    docker rm -f $REMAINING_CONTAINERS
    echo "=== All remaining containers removed ==="
else
    echo "=== No remaining containers found ==="
fi

echo "=== All Docker containers have been deleted ==="