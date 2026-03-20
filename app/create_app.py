import logging
import os

from flask import Flask, g
from flask_jwt_extended import (
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)

from app.cli import register_cli
from app.config import config_by_name
from app.extensions import init_extensions
from app.models.allowed_refresh_token import AllowedRefreshToken  # noqa F401
from app.models.friend_request import FriendRequest  # noqa F401
from app.models.friendship import Friendship  # noqa F401
from app.models.misc_data import MiscData  # noqa F401
from app.models.movie import Movie  # noqa F401
from app.models.movie_language_info import MovieLanguageInfo  # noqa F401
from app.models.movie_region_info import MovieRegionInfo  # noqa F401
from app.models.notification import Notification  # noqa F401
from app.models.notification_channel import NotificationChannel  # noqa F401
from app.models.send_confirmation_mails import SentConfirmationMails  # noqa F401
from app.models.tmdb_genre import MovieGenre, TmdbGenre, TmdbGenreName  # noqa F401
from app.models.tmdb_language import TmdbLanguage  # noqa F401
from app.models.tmdb_region import TmdbRegion  # noqa F401
from app.models.user import User  # noqa F401
from app.models.user_calendar import UserCalendar  # noqa F401
from app.models.user_email import UserEmailQueue  # noqa F401
from app.models.user_movie import UserMovie  # noqa F401
from app.routes.api import api as api_blueprint
from app.routes.friend_api import friend_api as friend_api_blueprint
from app.routes.html import html as html_blueprint
from app.scheduler import setup_cron_jobs
from app.utils.auth import authenticate_request

_logger = logging.getLogger(__name__)


def create_app(config_name, start_scheduler=False):

    instance_path = os.environ.get("INSTANCE_PATH")
    if instance_path and not os.path.isabs(instance_path):
        instance_path = os.path.abspath(instance_path)

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        instance_path=instance_path,
    )
    config_class = config_by_name[config_name]
    app.config.from_object(config_class)
    config_class.init_app(app)

    init_extensions(app)

    # Register CLI commands
    register_cli(app)

    # === Request Hooks (Auth Logic) ===
    @app.before_request
    def authenticate():
        return authenticate_request(app)

    @app.after_request
    def manage_auth_cookies(response):
        try:
            if getattr(g, "clear_auth_cookies", False):
                unset_jwt_cookies(response)
            else:
                new_access_tkn = getattr(g, "new_access_token", None)
                new_refresh_tkn = getattr(g, "new_refresh_token", None)

                if new_access_tkn:
                    a_max_age = app.config.get("JWT_ACCESS_TOKEN_EXPIRES")
                    set_access_cookies(response, new_access_tkn, a_max_age)

                if new_refresh_tkn:
                    r_max_age = app.config.get("JWT_REFRESH_TOKEN_EXPIRES")
                    set_refresh_cookies(response, new_refresh_tkn, r_max_age)

        except Exception:
            _logger.exception("Error setting new token cookies")
        finally:
            # Ensure g attributes are cleaned up even if response setting fails
            g.pop("new_access_token", None)
            g.pop("new_refresh_token", None)
        return response

    app.register_blueprint(html_blueprint)
    app.register_blueprint(api_blueprint, url_prefix="/api")
    app.register_blueprint(friend_api_blueprint, url_prefix="/api/friends")

    if start_scheduler:
        _logger.info("Starting scheduler in server mode")
        setup_cron_jobs()
    else:
        _logger.info("Skipping scheduler initialization (not in server mode)")

    @app.context_processor
    def inject_context():
        # g.current_user is set (or None) by before_request
        return {
            "current_user": g.get("current_user"),
            "static_version": app.config.get("STATIC_VERSION", "dev"),
        }

    return app
