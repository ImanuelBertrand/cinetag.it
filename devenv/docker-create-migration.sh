#!/bin/bash

# Script to create a clean migration by:
# 1. Resetting the database (removing volumes)
# 2. Recreating a fresh database with existing migrations
# 3. Creating a new migration based on the difference between current models and the fresh DB

# Exit on error
set -e

# Get the directory of this script
SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR"

# Check if a migration message was provided
if [ -z "$1" ]; then
  echo "Error: Migration message is required."
  echo "Usage: ./docker-create-migration.sh \"Description of changes\""
  exit 1
fi

MIGRATION_MESSAGE="$1"

echo "=== Stopping containers and removing volumes ==="
docker-compose -p cinetagit down -v

echo "=== Starting Docker environment ==="
./docker-start.sh

echo "=== Initializing database with existing migrations ==="
./docker-init-db.sh

echo "=== Creating new migration based on differences between models and DB ==="
./docker-migrate.sh migrate -m "$MIGRATION_MESSAGE"

echo "=== Migration creation complete ==="
echo "Your new migration has been created with the message: \"$MIGRATION_MESSAGE\""
echo "You can find it in the migrations directory."