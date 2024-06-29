from flask_caching import Cache
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# Initialize extensions
db = SQLAlchemy()
mail = Mail()
jwt = JWTManager()
migrate = Migrate()
cache = Cache()


def init_extensions(app):
    """
    Initialize the Flask extensions with the application instance.
    """
    db.init_app(app)
    mail.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)

    with app.app_context():
        db.create_all()
