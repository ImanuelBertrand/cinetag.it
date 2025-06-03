#!/bin/bash

# This script runs Flask migration commands inside the Docker container
# Usage: ./docker-migrate.sh [command]
# Examples:
#   ./docker-migrate.sh upgrade                 # Apply all migrations
#   ./docker-migrate.sh migrate -m "message"    # Create a new migration
#   ./docker-migrate.sh history                 # Show migration history
#   ./docker-migrate.sh downgrade               # Downgrade to previous version

# Default to 'upgrade' if no command is provided
COMMAND=${1:-"upgrade"}
shift
ARGS="$@"

echo "Running Flask migration command: $COMMAND $ARGS"
cd $(dirname "$0") && docker compose -p cinetagit exec app flask db $COMMAND $ARGS

echo "Migration command complete."
