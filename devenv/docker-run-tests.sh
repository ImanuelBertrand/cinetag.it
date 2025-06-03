#!/bin/bash

# Script to run tests in the Docker environment
# This script will:
# 1. Rebuild the Docker image to ensure all dependencies are installed
# 2. Start the Docker environment
# 3. Run the tests inside the Docker container
# 4. Stop the Docker environment

# Exit on error
set -e

# Get the directory of this script
SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR"

echo "=== Rebuilding Docker image ==="
./docker-reset.sh

echo "=== Starting Docker environment ==="
./docker-start.sh

echo "=== Initializing main database ==="
./docker-init-db.sh

echo "=== Initializing test database ==="
./docker-init-test-db.sh

echo "=== Running tests ==="
# Run pytest inside the Docker container
# The -v flag makes pytest output verbose
# The -s flag allows print statements to be displayed
# The --no-header flag suppresses the pytest header
# The --no-summary flag suppresses the pytest summary
docker compose -p cinetagit exec -e FLASK_ENV=testing -e CONFIG_FILE=/app/devenv/docker-config-test.yaml app python -m pytest -v tests/

# Capture the exit code of the tests
TEST_EXIT_CODE=$?

# Exit with the same code as the tests
exit $TEST_EXIT_CODE
