import os
import yaml


class Config:
    def __init__(self, config_file="config.yaml"):
        self.load_config(config_file)

    def load_config(self, config_file):
        with open(config_file, "r") as file:
            config_data = yaml.safe_load(file)
        for key, value in config_data.items():
            setattr(self, key, value)

    @staticmethod
    def init_app(app):
        pass

    # Shared configuration settings
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
    CACHE_TYPE = os.environ.get(
        "CACHE_TYPE", "simple"
    )  # Can be "memcached", "redis", etc.

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        db_type = os.environ.get("DB_TYPE", "sqlite")  # default to sqlite
        if db_type == "mariadb":
            return (
                os.environ.get("DATABASE_URI")
                or "mysql+pymysql://user:password@localhost/db_name"
            )
        elif db_type == "sqlite":
            return os.environ.get("DATABASE_URI") or "sqlite:///app.db"
        else:
            raise ValueError("Unsupported database type.")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {"development": DevelopmentConfig, "production": ProductionConfig}
