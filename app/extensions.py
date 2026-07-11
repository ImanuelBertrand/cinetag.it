import base64

from apscheduler.executors.pool import ThreadPoolExecutor
from flask import current_app, request
from flask_apscheduler import APScheduler
from flask_assets import Bundle, Environment
from flask_babel import Babel
from flask_bcrypt import Bcrypt
from flask_caching import Cache
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


def rate_limit_key() -> str:
    """Per-client key for rate limiting.

    Behind nginx (which sets X-Real-IP to the real client address and appends to
    X-Forwarded-For), the socket address is always the proxy, so read the
    forwarded headers first. Falls back to the socket address for direct access,
    development, and tests.
    """
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address()


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
# Default limits bound overall per-IP request volume (this also caps how fast a
# cookieless client can spin up guest users, since guest creation runs on every
# unauthenticated request). Sensitive POST endpoints add stricter limits of
# their own. Storage / enable flag / limits come from config.
limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=["600 per minute", "5000 per hour"],
    headers_enabled=True,
)


@limiter.request_filter
def _exempt_high_frequency_endpoints() -> bool:
    """Skip rate limiting for cacheable, high-frequency static assets so normal
    browsing never trips the limiter."""
    return request.endpoint in {
        "static",
        "html.get_poster",
        "html.service_worker",
    }


def get_locale():
    # loading the authenticated users language
    # doesn't work yet because of circular imports.
    return request.accept_languages.best_match(["en", "de"])


def obfuscate_email(email: str) -> str:
    return base64.b64encode(email.encode("utf-8")).decode("utf-8")[::-1]


def _register_jwt_key_callbacks(manager: JWTManager) -> None:
    """Stamp new tokens with the current kid; route decoding to primary or
    fallback key based on the token's kid. Lets us rotate JWT_SECRET_KEY
    without invalidating live sessions (see app/utils/jwt_keys.py)."""

    @manager.additional_headers_loader
    def _add_kid(_identity):
        return {"kid": current_app.config.get("JWT_KEY_ID", "primary")}

    @manager.decode_key_loader
    def _select_decode_key(jwt_header, _jwt_payload):
        current_kid = current_app.config.get("JWT_KEY_ID", "primary")
        fallback = current_app.config.get("JWT_SECRET_KEY_FALLBACK")
        if jwt_header.get("kid") == current_kid or not fallback:
            return current_app.config["JWT_SECRET_KEY"]
        return fallback


def init_extensions(app) -> None:
    """
    Initialize the Flask extensions with the application instance.
    """
    db.init_app(app)
    mail.init_app(app)
    jwt_manager.init_app(app)
    _register_jwt_key_callbacks(jwt_manager)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    babel.init_app(app, locale_selector=get_locale)
    assets_env.init_app(app)
    limiter.init_app(app)

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
