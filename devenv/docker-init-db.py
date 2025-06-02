"""
Initialize the database for the Docker environment.
This script creates all the tables in the database using SQLAlchemy's create_all() method.
It also creates the testing database if it doesn't exist.
"""

import os
import pymysql

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

    # Create the testing database if it doesn't exist
    print("Checking if testing database exists...")
    try:
        # Connect to the MariaDB server without specifying a database
        conn = pymysql.connect(host="db", user="cinetagit", password="password")

        with conn.cursor() as cursor:
            # Check if the testing database exists
            cursor.execute("SHOW DATABASES LIKE 'cinetagit_test'")
            result = cursor.fetchone()

            if not result:
                print("Creating testing database...")
                cursor.execute("CREATE DATABASE cinetagit_test")
                print("Testing database created successfully.")
            else:
                print("Testing database already exists.")

        conn.close()
    except Exception as e:
        print(f"Error checking/creating testing database: {e}")


if __name__ == "__main__":
    init_db()
