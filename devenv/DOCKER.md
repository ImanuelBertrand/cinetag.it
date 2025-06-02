# Docker Setup for cinetagit

This file provides instructions for setting up and using the Docker environment for cinetagit.

This directory contains the Docker setup for the cinetagit application. It includes:

- A docker-compose.yml file for orchestrating the services
- A Dockerfile for building the application image
- Configuration files and scripts for initializing and managing the Docker environment

## Prerequisites

- Docker
- Docker Compose

## Services

The Docker setup includes the following services:

1. **app**: The Flask application
2. **db**: MariaDB database
3. **redis**: Redis cache
4. **mailhog**: Mail testing service

## Getting Started

### 1. Start the Docker containers

You can start the Docker containers in one of two ways:

From the project root directory:
```bash
./devenv/docker-start.sh
```

Or by changing to the devenv directory first:
```bash
cd devenv
./docker-start.sh
```

Both methods will start all the services in detached mode.

### 2. Initialize the database with migrations

You can initialize the database using migrations in one of two ways:

From the project root directory:
```bash
./devenv/docker-init-db.sh
```

Or by changing to the devenv directory first:
```bash
cd devenv
./docker-init-db.sh
```

This will run all database migrations to create and update the necessary database tables. The migration-based approach ensures that your database schema is always up-to-date with the latest changes.

### 3. Working with migrations

cinetagit now uses Flask-Migrate (based on Alembic) for database migrations. A new script has been added to help you work with migrations:

```bash
# Apply all migrations (same as docker-init-db.sh)
./devenv/docker-migrate.sh

# Create a new migration
./devenv/docker-migrate.sh migrate -m "Description of changes"

# Show migration history
./devenv/docker-migrate.sh history

# Downgrade to the previous version
./devenv/docker-migrate.sh downgrade
```

This script allows you to run any Flask migration command inside the Docker container.

### 4. Access the application

The application will be available at http://localhost:5000

### 5. Access MailHog

MailHog provides a web interface for viewing emails sent by the application. It's available at http://localhost:8025

## Stopping the Docker containers

You can stop the Docker containers in one of two ways:

From the project root directory:
```bash
./devenv/docker-stop.sh
```

Or by changing to the devenv directory first:
```bash
cd devenv
./docker-stop.sh
```

This will stop all the services.

## Deleting All Docker Containers

If you need to completely remove all Docker containers for the CineTagIt project, you can use the provided script:

From the project root directory:
```bash
./devenv/docker-delete-containers.sh
```

Or by changing to the devenv directory first:
```bash
cd devenv
./docker-delete-containers.sh
```

This script will:
1. Stop all running containers
2. Remove all containers associated with the CineTagIt project

Use this when you want to clean up your Docker environment completely.

## Running Tests

You can run the tests in the Docker environment using the provided script:

From the project root directory:
```bash
./devenv/docker-run-tests.sh
```

Or by changing to the devenv directory first:
```bash
cd devenv
./docker-run-tests.sh
```

This script will:
1. Rebuild the Docker image to ensure all dependencies are installed
2. Start the Docker environment
3. Run the tests inside the Docker container
4. Stop the Docker environment

For more information about the tests and how to run specific tests, see the [tests/README.md](../tests/README.md) file.

## Configuration

1. Copy the template configuration file:
   ```bash
   cp devenv/docker-config.example.yaml devenv/docker-config.yaml
   ```

2. Edit the configuration file to add your TMDB API token and other sensitive information:
   ```bash
   # Edit the file with your preferred text editor
   # For example:
   nano devenv/docker-config.yaml
   ```

The Docker environment uses a specific configuration file located at `devenv/docker-config.yaml`. This file contains configuration values specific to the Docker environment, such as database connection details and mail server settings.

## Known Issues

- None currently. The database is automatically initialized with the correct schema using migrations.

## Troubleshooting

If you encounter any issues with the Docker setup, try the following:

1. Check the logs of the services:

   From the devenv directory:
   ```bash
   docker-compose -p cinetagit logs app
   docker-compose -p cinetagit logs db
   docker-compose -p cinetagit logs redis
   docker-compose -p cinetagit logs mailhog
   ```

2. Restart the services:

   From the devenv directory:
   ```bash
   docker-compose -p cinetagit restart
   ```

3. Rebuild the services:

   From the devenv directory:
   ```bash
   docker-compose -p cinetagit build
   ```

4. Remove the volumes and start from scratch:

   ```bash
   # From the devenv directory:
   docker-compose -p cinetagit down -v
   ./docker-start.sh
   ./docker-init-db.sh

   # Or from the project root:
   cd devenv && docker-compose -p cinetagit down -v
   ./devenv/docker-start.sh
   ./devenv/docker-init-db.sh
   ```
