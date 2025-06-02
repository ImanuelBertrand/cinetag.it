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

logging.getLogger(__name__).info(f"Starting application in {config_name} mode")


# Create an instance of the Flask application
# Only start the scheduler when running as a server, not for CLI commands like 'flask db stamp head'
application = create_app(config_name, start_scheduler=True)

if __name__ == "__main__":
    # In development mode, bind to all interfaces (0.0.0.0)
    # In production mode, bind only to localhost (127.0.0.1) for security
    host = "0.0.0.0" if config_name == "development" else "127.0.0.1"
    application.run(host=host)
