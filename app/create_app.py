import logging
import os

from flask import Flask, g
from flask_jwt_extended import (
    create_access_token,
    set_access_cookies,
)

from app.config import config_by_name
from app.extensions import init_extensions
from app.models import *  # noqa F401 (not used, but required to create tables)
from app.scheduler import setup_cron_jobs

log_dir = os.path.join(os.path.dirname(__file__), "logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    filename=os.path.join(log_dir, "app.log"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)


def create_app(config_name):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    config_class = config_by_name[config_name]
    config_instance = config_class()
    app.config.from_object(config_instance)
    config_class.init_app(app)

    # Initialize extensions
    init_extensions(app)

    # Register blueprints
    from app.routes.html import html as html_blueprint
    from app.routes.api import api as api_blueprint

    app.register_blueprint(html_blueprint)
    app.register_blueprint(api_blueprint, url_prefix="/api")

    setup_cron_jobs()

    @app.context_processor
    def inject_context():
        result = {}
        if hasattr(g, "current_user") and g.current_user:
            result["current_user"] = g.current_user
        else:
            result["current_user"] = None

        return result

    @app.after_request
    def set_cookie(response):
        if hasattr(g, "current_user") and g.current_user:
            access_token = create_access_token(identity=g.current_user.id)
            set_access_cookies(response, access_token)
        return response

    return app
