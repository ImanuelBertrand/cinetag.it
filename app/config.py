import os


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
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
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
    JWT_CSRF_CHECK_FORM = True

    CACHE_TYPE = os.environ.get(
        "CACHE_TYPE", "flask_caching.backends.simplecache.SimpleCache"
    )
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URI") or "sqlite:///app.db"

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
    TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original/"

    CACHE_REDIS_URL = os.environ.get("CACHE_REDIS_URL")
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", "300"))


class DevelopmentConfig(Config):
    JWT_COOKIE_SECURE = False
    DEBUG = True


class ProductionConfig(Config):
    JWT_COOKIE_SECURE = True
    DEBUG = False


class TestingConfig(Config):
    JWT_COOKIE_SECURE = False
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SERVER_NAME = None
    # Disable scheduler for testing
    SCHEDULER_API_ENABLED = False
    SCHEDULER_ENABLED = False
    JWT_COOKIE_CSRF_PROTECT = False
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "your-extremely-long-and-secure-secret-key-that-is-very-long-for",
    )
    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY",
        "your-even-longer-and-even-more-secure-jwt-secret-key-that-is-very-long",
    )


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
