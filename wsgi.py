import logging
import os

from app.create_app import create_app

os.chdir(os.path.dirname(__file__))

# Determine the configuration to use (development, production, etc.)
config_name = os.getenv("FLASK_ENV", "production")

log_dir = os.path.join(os.path.dirname(__file__), "app/logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO if config_name == "production" else logging.DEBUG,
    filename=os.path.join(log_dir, "app.log"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)


# Create an instance of the Flask application
application = create_app(config_name)

if __name__ == "__main__":
    application.run()
