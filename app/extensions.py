from flask import request
from flask_babel import Babel
from flask_bcrypt import Bcrypt
from flask_caching import Cache
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

# Initialize extensions
db = SQLAlchemy()
mail = Mail()
jwt = JWTManager()
bcrypt = Bcrypt()
migrate = Migrate()
cache = Cache()
babel = Babel()
csrf = CSRFProtect()


def get_locale():
    # You can get the user's locale from the request or user settings
    return request.accept_languages.best_match(["en", "de"])


def init_extensions(app):
    """
    Initialize the Flask extensions with the application instance.
    """
    db.init_app(app)
    mail.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    babel.init_app(app, locale_selector=get_locale)
    csrf.init_app(app)

    with app.app_context():
        db.create_all()
