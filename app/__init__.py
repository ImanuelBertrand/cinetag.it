from flask import Flask
from app.config import config_by_name
from app.extensions import init_extensions


def create_app(config_name):
    app = Flask(__name__)
    config_class = config_by_name[config_name]
    app.config.from_object(config_class)
    config_class.init_app(app)

    # Initialize extensions
    init_extensions(app)

    # Register blueprints
    from app.main import main as main_blueprint

    app.register_blueprint(main_blueprint)

    from app.api import api as api_blueprint

    app.register_blueprint(api_blueprint, url_prefix="/api")

    return app
