from flask import Flask, request
from app.config import config_by_name
from app.extensions import init_extensions, babel


def create_app(config_name):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    config_class = config_by_name[config_name]
    app.config.from_object(config_class)
    config_class.init_app(app)

    # Initialize extensions
    init_extensions(app)

    # Register blueprints
    from app.routes.html import html as html_blueprint
    from app.routes.api import api as api_blueprint

    app.register_blueprint(html_blueprint)
    app.register_blueprint(api_blueprint, url_prefix="/api")

    return app


@babel.localeselector
def get_locale():
    # You can get the user's locale from the request or user settings
    return request.accept_languages.best_match(["en", "de", "fr"])
