#!/bin/bash

# Script to initialize the test database
echo "Initializing test database..."

# Check if the container is running
if ! docker ps | grep -q "cinetagit-db"; then
  echo "Error: MariaDB container (cinetagit-db) is not running."
  echo "Please start the containers first with ./devenv/docker-start.sh"
  exit 1
fi

# Connect to the MariaDB container and create/configure the test database
echo "Creating test database and setting permissions..."
if ! docker exec cinetagit-db bash -c "mariadb -u root -prootpassword -e \"CREATE DATABASE IF NOT EXISTS cinetagit_test; GRANT ALL PRIVILEGES ON cinetagit_test.* TO 'cinetagit'@'%'; FLUSH PRIVILEGES;\""; then
  echo "Error: Failed to create or configure test database."
  exit 1
fi

echo "Test database initialized successfully."