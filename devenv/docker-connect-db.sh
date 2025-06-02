#!/bin/bash

# Script to connect to the MariaDB container for CineTagIt

# Check if the container is running
if ! docker ps | grep -q "cinetagit-db"; then
  echo "Error: MariaDB container (cinetagit-db) is not running."
  echo "Please start the containers first with ./devenv/docker-start.sh"
  exit 1
fi

# Connect to the MariaDB container
echo "Connecting to MariaDB container..."
docker exec -it cinetagit-db mariadb -u cinetagit -ppassword cinetagit

# Note: In a production environment, it's better to avoid hardcoding passwords
# and instead use environment variables or a secure password store.