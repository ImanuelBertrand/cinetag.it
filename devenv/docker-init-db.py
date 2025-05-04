"""
Initialize the database for the Docker environment.
This script creates all the tables in the database using SQLAlchemy's create_all() method.
"""

import os

# Set the CONFIG_FILE environment variable to use the Docker configuration
os.environ["CONFIG_FILE"] = "../devenv/docker-config.yaml"

# Import the application
from app.create_app import create_app
from app.extensions import db


def init_db():
    """Initialize the database by creating all tables."""
    print("Initializing database...")

    # Create the Flask application with the development configuration
    app = create_app("development")

    # Push an application context
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully.")


if __name__ == "__main__":
    init_db()
