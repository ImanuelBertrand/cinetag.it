import logging
import traceback

import jwt
from crawlerdetect import CrawlerDetect
from flask import Flask, g, make_response, request
from flask_jwt_extended import (
    get_jwt_identity,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)

from app.cli import register_cli
from app.config import config_by_name
from app.extensions import init_extensions
from app.models.allowed_refresh_token import AllowedRefreshToken  # noqa F401
from app.models.misc_data import MiscData  # noqa F401
from app.models.movie import Movie  # noqa F401
from app.models.movie_language_info import MovieLanguageInfo  # noqa F401
from app.models.movie_region_info import MovieRegionInfo  # noqa F401
from app.models.notification import Notification  # noqa F401
from app.models.notification_channel import NotificationChannel  # noqa F401
from app.models.send_confirmation_mails import SentConfirmationMails  # noqa F401
from app.models.tmdb_language import TmdbLanguage  # noqa F401
from app.models.tmdb_region import TmdbRegion  # noqa F401
from app.models.user import User  # noqa F401
from app.models.user_calendar import UserCalendar  # noqa F401
from app.models.user_email import UserEmailQueue  # noqa F401
from app.models.user_movie import UserMovie  # noqa F401
from app.scheduler import setup_cron_jobs
from app.utils.auth import (
    create_temporary_user,
    generate_new_tokens,
    verify_refresh_token_and_get_identity,
)

_logger = logging.getLogger(__name__)


# --- Define public endpoints (adjust as needed) ---
# Consider moving this to configuration
PUBLIC_ENDPOINTS = {
    "static",  # Flask's static file serving
    "html.service_worker",  # The service worker js file
    "html.get_poster",  # Serving posters likely doesn't need login
}


def create_app(config_name, start_scheduler=False):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    config_class = config_by_name[config_name]
    config_instance = config_class()
    app.config.from_object(config_instance)
    config_class.init_app(app)

    init_extensions(app)

    # Register CLI commands
    register_cli(app)

    # === Request Hooks (New Auth Logic) ===
    @app.before_request
    def unified_auth_check():
        """
        Authentication middleware that runs before each request.

        This function implements CineTagIt's unique user authentication flow:

        1. First, it tries to authenticate the user using JWT tokens
           (access token or refresh token)
        2. If no valid tokens are found and the endpoint requires authentication,
           it automatically creates a temporary anonymous user account
        3. This allows visitors to use the application without
           explicitly registering first

        The temporary user becomes permanent when the user registers
        by setting an email and password through the registration process.

        This approach provides a seamless experience for users,
        allowing them to try the application before committing to registration,
        while maintaining data continuity when they do register.
        """
        g.current_user = None  # Ensure g.current_user is reset at start of request
        g.new_access_token = None  # Ensure reset
        g.new_refresh_token = None  # Ensure reset

        # 1. Check Endpoint Type
        endpoint = request.endpoint
        if endpoint in PUBLIC_ENDPOINTS:
            return None

        # 2. Check for Bot
        if CrawlerDetect(request.headers).isCrawler():
            _logger.info("Bot detected, skipping auth.")
            return None

        # 3. Attempt Access Token Auth
        try:
            verify_jwt_in_request(optional=True)  # Verify JWT token (expiry, etc.)
            user_id = get_jwt_identity()
            if user_id:
                with app.app_context():  # Ensure context for DB query
                    user = User.query.get(user_id)
                if user:
                    g.current_user = user
                else:
                    _logger.warning(f"Access token identity {user_id} not found in DB.")
        except jwt.ExpiredSignatureError:
            pass  # Access token expired, fallback to the refresh token logic below
        except jwt.InvalidTokenError as e:
            _logger.warning(
                f"Invalid access token encountered for endpoint {endpoint}: {e}"
            )
        except Exception as e:
            # Catch other potential verification errors
            _logger.error(
                "Error verifying JWT access token for endpoint "
                f"{endpoint}: {e}\n{traceback.format_exc()}"
            )

        refresh_token_cookie = request.cookies.get("refresh_token_cookie")

        if g.current_user:
            # Migrate users only having a valid
            # access token to the refresh token logic
            if not refresh_token_cookie:
                _logger.debug(f"Migrating user {g.current_user} to refresh tokens")
                try:
                    (
                        g.new_access_token,
                        g.new_refresh_token,
                    ) = generate_new_tokens(g.current_user.id)
                except Exception as e:
                    _logger.error(
                        f"Error generating tokens during refresh cookie "
                        f"restoration: {e}\n{traceback.format_exc()}",
                        exc_info=True,
                    )
                    g.new_access_token = None
                    g.new_refresh_token = None
            return None

        # 4. Attempt Refresh Token Auth
        # Try refresh if access tkn expired or if access tkn was missing/invalid
        if refresh_token_cookie:
            try:
                (
                    refreshed_user_id,
                    old_jti,
                ) = verify_refresh_token_and_get_identity(refresh_token_cookie)
                if refreshed_user_id:
                    with app.app_context():  # Ensure context for DB query
                        user = User.query.get(refreshed_user_id)
                    if user:
                        (
                            g.new_access_token,
                            g.new_refresh_token,
                        ) = generate_new_tokens(refreshed_user_id, old_jti)
                        g.current_user = user
                        _logger.debug(
                            f"User {user.id} authenticated via refresh token."
                        )
                        return None  # Authenticated via refresh, proceed
                    _logger.warning(
                        f"User identity {refreshed_user_id} "
                        f"from valid refresh token not found in DB."
                    )
                        # Fall through to invalid token handling
                else:
                    _logger.warning(
                        "Refresh token deemed invalid by verification helper "
                        "(e.g., revoked)."
                    )
                    # Fall through to invalid token handling

            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
                _logger.warning(f"Refresh token verification failed: {e}")
            except Exception as e:
                _logger.warning(
                    f"Refresh token verification failed: {e}\n{traceback.format_exc()}"
                )

        if g.current_user:
            return None

        # 5. Handle Guest User / Unauthenticated for Protected Route
        try:
            # Create temporary user within app context for DB access
            with app.app_context():
                temp_user = create_temporary_user()
            if not temp_user:
                raise Exception(
                    f"Failed to create guest user object, result is falsy: {temp_user}"
                )
            (
                g.new_access_token,
                g.new_refresh_token,
            ) = generate_new_tokens(temp_user.id)
            g.current_user = temp_user
            return None  # Proceed with guest user
        except Exception as e:
            _logger.exception(
                f"Failed to create temporary user for endpoint {endpoint}: {e}"
            )  # Use exception logger
            # Consider redirecting to an error page or login
            return make_response("Server error creating guest session", 500)

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

        except Exception as e:
            _logger.error(
                f"Error setting new token cookies: {e}\n{traceback.format_exc()}"
            )
        finally:
            # Ensure g attributes are cleaned up even if response setting fails
            g.pop("new_access_token", None)
            g.pop("new_refresh_token", None)
        return response

    from app.routes.api import api as api_blueprint
    from app.routes.html import html as html_blueprint

    app.register_blueprint(html_blueprint)
    app.register_blueprint(api_blueprint, url_prefix="/api")

    if start_scheduler:
        _logger.info("Starting scheduler in server mode")
        setup_cron_jobs()
    else:
        _logger.info("Skipping scheduler initialization (not in server mode)")

    @app.context_processor
    def inject_context():
        # g.current_user is set (or None) by before_request
        return {"current_user": g.get("current_user")}

    return app
