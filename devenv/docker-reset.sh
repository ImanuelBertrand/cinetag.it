#!/bin/bash

# Script to completely reset the Docker environment for CineTagIt
# This script will:
# 1. Stop all running containers
# 2. Remove all containers, networks, and volumes
# 3. Optionally remove all locally built images
# 4. Optionally restart the Docker environment

# Exit on error
set -e

# Get the directory of this script
SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR"

# Parse command line arguments
REMOVE_IMAGES=false
RESTART=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --remove-images)
      REMOVE_IMAGES=true
      shift
      ;;
    --restart)
      RESTART=true
      shift
      ;;
    --help)
      echo "Usage: ./docker-reset.sh [OPTIONS]"
      echo "Options:"
      echo "  --remove-images  Remove all locally built images"
      echo "  --restart        Restart the Docker environment after reset"
      echo "  --help           Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Stop and remove existing containers, networks, and volumes
echo "=== Stopping and removing containers, networks, and volumes ==="
if [ "$REMOVE_IMAGES" = true ]; then
  echo "Also removing locally built images..."
  docker-compose -p cinetagit down -v --rmi local
else
  docker-compose -p cinetagit down -v
fi

# Remove any orphaned containers
echo "=== Removing any orphaned containers ==="
docker-compose -p cinetagit down --remove-orphans

echo "=== Docker environment has been completely reset ==="

# Restart if requested
if [ "$RESTART" = true ]; then
  echo "=== Restarting Docker environment ==="
  ./docker-start.sh
fi
