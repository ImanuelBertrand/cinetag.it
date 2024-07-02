import os
from app.create_app import create_app

os.chdir(os.path.dirname(__file__))

# Determine the configuration to use (development, production, etc.)
config_name = os.getenv("FLASK_ENV", "production")

# Create an instance of the Flask application
application = create_app(config_name)

if __name__ == "__main__":
    application.run()
