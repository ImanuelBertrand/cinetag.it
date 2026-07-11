import os
from urllib.parse import urlparse, urlunparse


def _build_test_db_uri() -> str | None:
    """Always return a URI pointing at a dedicated test database.

    Priority:
    1. TEST_DATABASE_URI env var (explicit override)
    2. DATABASE_URI env var with the db name suffixed with '_test'

    Never falls back to DATABASE_URI as-is — that would risk wiping dev/prod.
    """
    if test_uri := os.environ.get("TEST_DATABASE_URI"):
        return test_uri
    if base_uri := os.environ.get("DATABASE_URI"):
        parsed = urlparse(base_uri)
        # parsed.path is e.g. '/cinetagit_db' → append '_test'
        return urlunparse(parsed._replace(path=parsed.path + "_test"))
    return None


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in ("yes", "true", "t", "1")


class Config:
    @staticmethod
    def init_app(app) -> None:
        pass

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = parse_bool(os.environ.get("MAIL_USE_TLS", "True"))
    MAIL_USE_SSL = parse_bool(os.environ.get("MAIL_USE_SSL", "False"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SECRET_KEY_FALLBACK = os.environ.get("SECRET_KEY_FALLBACK")
    SECRET_KEY_ID = os.environ.get("SECRET_KEY_ID", "primary")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    JWT_SECRET_KEY_FALLBACK = os.environ.get("JWT_SECRET_KEY_FALLBACK")
    JWT_KEY_ID = os.environ.get("JWT_KEY_ID", "primary")
    JWT_TOKEN_LOCATION = ("headers", "cookies")
    JWT_ACCESS_COOKIE_NAME = "access_token_cookie"
    JWT_ACCESS_COOKIE_PATH = "/"
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", "3600"))
    JWT_REFRESH_TOKEN_EXPIRES = int(
        os.environ.get("JWT_REFRESH_TOKEN_EXPIRES", "604800")
    )
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_REFRESH_COOKIE_PATH = "/"
    JWT_ACCESS_CSRF_HEADER_NAME = "X-CSRF-TOKEN"
    # Refresh CSRF uses a distinct field name so forms can carry both tokens
    # at once and submissions still validate when the access token has expired
    # and the request falls through to the refresh-token auth path.
    JWT_REFRESH_CSRF_FIELD_NAME = "csrf_refresh_token"
    JWT_CSRF_CHECK_FORM = True
    # Defence-in-depth behind the existing CSRF double-submit: don't send auth
    # cookies on cross-site navigations.
    JWT_COOKIE_SAMESITE = "Lax"

    CACHE_TYPE = os.environ.get(
        "CACHE_TYPE", "flask_caching.backends.simplecache.SimpleCache"
    )
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URI")

    COUNT_TOP_SELECT_OPTION = 5

    DEFAULT_REGION = os.environ.get("DEFAULT_REGION", "US")
    DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "en")
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
    SERVER_NAME = os.environ.get("SERVER_NAME")
    APPLICATION_ROOT = os.environ.get("APPLICATION_ROOT", "/")
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "https")

    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    APP_DIR = os.path.join(ROOT_DIR, "app")
    STORAGE_DIR = os.path.join(ROOT_DIR, "storage")
    POSTER_DIR = os.path.join(STORAGE_DIR, "posters")
    # Cached poster files unused (not accessed or modified) for longer than this
    # are pruned by a scheduled job. The cache self-heals on the next request.
    POSTER_CACHE_RETENTION_DAYS = int(
        os.environ.get("POSTER_CACHE_RETENTION_DAYS", "30")
    )
    TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original/"
    STATIC_VERSION = os.environ.get("STATIC_VERSION", "dev")

    CACHE_REDIS_URL = os.environ.get("CACHE_REDIS_URL")
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", "300"))

    # Rate limiting (Flask-Limiter). Redis ships alongside the app, so default
    # to it with no extra configuration — a shared store keeps limits consistent
    # across gunicorn workers. Uses logical DB 1 to stay isolated from the cache
    # (DB 0), so clearing the cache can't wipe rate-limit counters. An explicit
    # RATELIMIT_STORAGE_URI overrides (e.g. "memory://" for a Redis-less run).
    RATELIMIT_ENABLED = parse_bool(os.environ.get("RATELIMIT_ENABLED", "True"))
    RATELIMIT_STORAGE_URI = os.environ.get(
        "RATELIMIT_STORAGE_URI", "redis://redis:6379/1"
    )
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_HEADERS_ENABLED = True

    BACKUP_ENABLED = parse_bool(os.environ.get("BACKUP_ENABLED", "True"))
    BACKUP_MIN_INTERVAL_HOURS = float(
        os.environ.get("BACKUP_MIN_INTERVAL_HOURS", "23.5")
    )
    BACKUP_KEEP_DAYS = int(os.environ.get("BACKUP_KEEP_DAYS", "14"))
    BACKUP_KEEP_WEEKS = int(os.environ.get("BACKUP_KEEP_WEEKS", "4"))
    BACKUP_COMPRESSION = int(os.environ.get("BACKUP_COMPRESSION", "6"))


class DevelopmentConfig(Config):
    JWT_COOKIE_SECURE = False
    DEBUG = True


# Sample/placeholder secrets that must never be used in production. Mirrors the
# hardcoded TestingConfig fallbacks so a copy-paste of those into prod is caught.
_INSECURE_SECRETS = frozenset(
    {
        "your-extremely-long-and-secure-secret-key-that-is-very-long-for",
        "your-even-longer-and-even-more-secure-jwt-secret-key-that-is-very-long",
        "changeme",
        "secret",
    }
)
_MIN_SECRET_LENGTH = 32


class ProductionConfig(Config):
    JWT_COOKIE_SECURE = True
    DEBUG = False

    @staticmethod
    def init_app(app) -> None:
        # Fail fast at boot (mirroring the TestingConfig DB-safety assertion)
        # rather than surfacing a misconfiguration lazily at request time.
        for name in ("SECRET_KEY", "JWT_SECRET_KEY"):
            value = app.config.get(name)
            if not value:
                raise RuntimeError(
                    f"{name} must be set in production. Refusing to start."
                )
            if len(value) < _MIN_SECRET_LENGTH:
                raise RuntimeError(
                    f"{name} is too short ({len(value)} chars); "
                    f"require at least {_MIN_SECRET_LENGTH}."
                )
            if value in _INSECURE_SECRETS:
                raise RuntimeError(
                    f"{name} is set to a known sample/placeholder value. "
                    "Refusing to start."
                )


class TestingConfig(Config):
    JWT_COOKIE_SECURE = False
    DEBUG = True
    TESTING = True
    SERVER_NAME = None
    # Disable scheduler for testing
    SCHEDULER_API_ENABLED = False
    SCHEDULER_ENABLED = False
    BACKUP_ENABLED = False
    JWT_COOKIE_CSRF_PROTECT = False
    # Enabled so Flask-Limiter registers its request hook (it no-ops entirely
    # when disabled at init). The conftest autouse fixture toggles
    # limiter.enabled off for the bulk of the suite and individual tests flip it
    # back on to exercise the 429 path. In-memory store keeps tests hermetic.
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://"
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "your-extremely-long-and-secure-secret-key-that-is-very-long-for",
    )
    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY",
        "your-even-longer-and-even-more-secure-jwt-secret-key-that-is-very-long",
    )
    # Always use a dedicated test database — never the dev/prod one.
    SQLALCHEMY_DATABASE_URI = _build_test_db_uri()

    @staticmethod
    def init_app(app) -> None:
        uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
        if "test" not in uri:
            raise RuntimeError(
                f"TestingConfig refuses to connect to '{uri}': the URI must "
                "contain 'test'. Set TEST_DATABASE_URI to a dedicated test database."
            )


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
