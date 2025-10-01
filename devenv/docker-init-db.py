"""
Initialize the database for the Docker environment.
This script creates all the tables in the database
using SQLAlchemy's create_all() method.
"""

import os
import sys

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set the CONFIG_FILE environment variable to use the Docker configuration
os.environ["CONFIG_FILE"] = "/app/devenv/docker-config.yaml"

# Import the application
from flask_migrate import upgrade

from app.create_app import create_app


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
