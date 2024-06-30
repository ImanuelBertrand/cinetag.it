import os
import yaml


class Config:
    def __init__(self, config_file="config.yaml"):
        self.load_config(config_file)

    def load_config(self, config_file):
        with open(config_file, "r") as file:
            config_data = yaml.safe_load(file)
        if config_data:
            for key, value in config_data.items():
                setattr(self, key, value)

    @staticmethod
    def init_app(app):
        pass

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS") is not None
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL") is not None
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")
    SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-jwt-secret-key")
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_ACCESS_COOKIE_NAME = "access_token_cookie"
    JWT_ACCESS_COOKIE_PATH = "/"
    JWT_ACCESS_TOKEN_EXPIRES = 86400 * 365
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_REFRESH_COOKIE_PATH = "/"
    JWT_ACCESS_CSRF_HEADER_NAME = "X-CSRF-TOKEN"

    CACHE_TYPE = os.environ.get("CACHE_TYPE", "simple")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URI") or "sqlite:///app.db"


class DevelopmentConfig(Config):
    JWT_COOKIE_SECURE = False
    DEBUG = True


class ProductionConfig(Config):
    JWT_COOKIE_SECURE = True
    DEBUG = False


config_by_name = {"development": DevelopmentConfig, "production": ProductionConfig}
