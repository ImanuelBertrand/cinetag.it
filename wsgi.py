import os

from app.create_app import create_app

# 1. Get the environment (default to production for safety)
env = os.getenv("FLASK_ENV", "production")

# 2. Check if we are running as a server (Gunicorn) or a CLI (Migrate)
# This prevents the scheduler from starting during a database migration!
is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")

# 3. Create the app instance
app = create_app(env, start_scheduler=is_gunicorn)
