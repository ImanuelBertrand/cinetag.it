import base64

import pymysql
from apscheduler.executors.pool import ThreadPoolExecutor
from flask import request
from flask_apscheduler import APScheduler
from flask_assets import Environment, Bundle
from flask_babel import Babel
from flask_bcrypt import Bcrypt
from flask_caching import Cache
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

pymysql.install_as_MySQLdb()

# Initialize extensions
db = SQLAlchemy()
mail = Mail()
jwt_manager = JWTManager()
bcrypt = Bcrypt()
migrate = Migrate()
cache = Cache()
babel = Babel()
assets_env = Environment()
scheduler = APScheduler()


def get_locale():
    # loading the authenticated users language
    # doesn't work yet because of circular imports.
    return request.accept_languages.best_match(["en", "de"])


def obfuscate_email(email: str) -> str:
    return base64.b64encode(email.encode("utf-8")).decode("utf-8")[::-1]


def init_extensions(app):
    """
    Initialize the Flask extensions with the application instance.
    """
    db.init_app(app)
    mail.init_app(app)
    jwt_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    babel.init_app(app, locale_selector=get_locale)
    assets_env.init_app(app)

    app.config.update(
        # rest of the config
        SCHEDULER_EXECUTORS={
            "default": ThreadPoolExecutor(1),
            "concurrent": ThreadPoolExecutor(5),
        },
    )
    scheduler.init_app(app)

    app.jinja_env.filters["obfuscate_email"] = obfuscate_email

    # Configure Flask-Assets
    if "scss_all" not in assets_env:
        scss = Bundle("src/style.scss", filters="libsass", output="dist/style.css")
        assets_env.register("scss_all", scss)

    with app.app_context():
        db.create_all()
