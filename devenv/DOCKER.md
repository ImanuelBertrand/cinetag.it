# Docker Setup for CineTagIt

This file provides instructions for setting up and using the Docker environment for CineTagIt.

This directory contains the Docker setup for the CineTagIt application. It includes:

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

### 2. Initialize the database

You can initialize the database in one of two ways:

From the project root directory:
```bash
./devenv/docker-init-db.sh
```

Or by changing to the devenv directory first:
```bash
cd devenv
./docker-init-db.sh
```

This will create all the necessary database tables.

### 3. Access the application

The application will be available at http://localhost:5000

### 4. Access MailHog

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

- There is no database migration setup yet, so the DB will remain empty after initialization. You'll need to manually add data or implement migrations.

## Troubleshooting

If you encounter any issues with the Docker setup, try the following:

1. Check the logs of the services:

   From the devenv directory:
   ```bash
   docker-compose -p CineTagIt logs app
   docker-compose -p CineTagIt logs db
   docker-compose -p CineTagIt logs redis
   docker-compose -p CineTagIt logs mailhog
   ```

2. Restart the services:

   From the devenv directory:
   ```bash
   docker-compose -p CineTagIt restart
   ```

3. Rebuild the services:

   From the devenv directory:
   ```bash
   docker-compose -p CineTagIt build
   ```

4. Remove the volumes and start from scratch:

   ```bash
   # From the devenv directory:
   docker-compose -p CineTagIt down -v
   ./docker-start.sh
   ./docker-init-db.sh

   # Or from the project root:
   cd devenv && docker-compose -p CineTagIt down -v
   ./devenv/docker-start.sh
   ./devenv/docker-init-db.sh
   ```
