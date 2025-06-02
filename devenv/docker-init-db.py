"""
Initialize the database for the Docker environment.
This script runs database migrations using Flask-Migrate to set up or update the database schema.
"""

import os

# Set the CONFIG_FILE environment variable to use the Docker configuration
os.environ["CONFIG_FILE"] = "../devenv/docker-config.yaml"

# Import the application
from app.create_app import create_app
from flask_migrate import upgrade


def init_db():
    """Initialize the database by running migrations."""
    print("Initializing database...")

    # Create the Flask application with the development configuration
    app = create_app("development")

    # Push an application context
    with app.app_context():
        # Run database migrations
        upgrade()
        print("Database migrations applied successfully.")


if __name__ == "__main__":
    init_db()
