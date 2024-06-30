from flask import Flask, g, request
from flask_jwt_extended import (
    create_access_token,
    set_access_cookies,
    decode_token,
)

from app.config import config_by_name
from app.extensions import init_extensions, babel
from app.models import User
from app.services.user_service import get_current_user


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
