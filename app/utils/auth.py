import logging
import uuid

import jwt
from crawlerdetect import CrawlerDetect
from flask import Flask, current_app, g, make_response, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    verify_jwt_in_request,
)

from app.extensions import db
from app.models.allowed_refresh_token import AllowedRefreshToken
from app.models.user import User

_logger = logging.getLogger(__name__)


PUBLIC_ENDPOINTS = {
    "static",  # Flask's static file serving
    "html.service_worker",  # The service worker js file
    "html.get_poster",  # Serving posters likely doesn't need login
}


def decode_refresh_token(encoded_token: str) -> dict:
    secret = current_app.config["JWT_SECRET_KEY"]
    algo = current_app.config.get("JWT_ALGORITHM", "HS256")

    return jwt.decode(encoded_token, secret, algorithms=[algo])


def verify_refresh_token_and_get_identity(
    encoded_token: str,
) -> tuple[int, str] | None:
    """
    Verifies the refresh token's signature, expiry using PyJWT, and checks
    if its JTI is present in the AllowedRefreshToken database table (allowlist).

    Args:
        encoded_token: The JWT refresh token string received from the client.

    Returns:
        The user identity (int) if the token is valid and allowed server-side.

    Raises:
        jwt.ExpiredSignatureError: If the token's signature has expired
                                   based on JWT 'exp' claim.
        Jwt.InvalidTokenError: If the token is invalid
                               (bad signature, missing claims,
                               JTI not found in allowlist,
                               or other decoding issues).
    """
    try:
        # 1. Decode JWT (verify signature and expiry using PyJWT)
        payload = decode_refresh_token(encoded_token)

        identity = payload.get("sub")
        jti = payload.get("jti")  # JTI (JWT ID) is crucial for revocation check

        if not identity:
            # Ensure identity ('sub' claim) exists
            raise jwt.InvalidTokenError("Refresh token missing 'sub' claim.")
        if not jti:
            # Ensure JTI claim exists for allowlist check
            raise jwt.InvalidTokenError("Refresh token missing 'jti' claim.")

        # 2. Check server-side allowlist using the JTI
        # This requires the DB session to be active
        if not AllowedRefreshToken.is_token_allowed(jti, identity):
            _logger.warning(
                "Refresh token JTI '%s' for user %s not "
                "found in allowlist (revoked or invalid).",
                jti,
                identity,
            )
            # Treat non-existence in allowlist as an invalid token scenario.
            raise jwt.InvalidTokenError(
                "Refresh token is not allowed (revoked or invalid)."
            )

    except jwt.ExpiredSignatureError:
        # Log expiry specifically
        payload_info = jwt.decode(
            encoded_token, options={"verify_signature": False, "verify_exp": False}
        )
        _logger.info(
            "Refresh token has expired (signature level). JTI: %s, User: %s",
            payload_info.get("jti", "N/A"),
            payload_info.get("sub", "N/A"),
        )

        raise

    except jwt.InvalidTokenError as e:
        # Catch other decoding errors or the explicit raises from above
        _logger.warning("Invalid refresh token encountered: %s", e)
        raise  # Re-raise the original exception

    except Exception as e:
        # Catch unexpected errors
        _logger.exception("Unexpected error during refresh token verification")
        # Wrap unexpected errors in InvalidTokenError for consistent handling
        raise jwt.InvalidTokenError(f"Refresh token verification failed: {e}") from e
    else:
        # 3. If decoding passed and JTI is allowed, return the user identity
        _logger.debug(
            "Refresh token verified successfully for JTI '%s', user %s.", jti, identity
        )
        return int(identity), jti


def create_temporary_user():
    """Creates and returns a guest User"""
    # Needs database interaction
    try:
        user = User()
        db.session.add(user)
        db.session.commit()
    except Exception:
        _logger.exception("Failed to create temporary user")
        # Ensure rollback in case of error during commit
        db.session.rollback()
        return None
    else:
        _logger.debug("Created temporary user %s", user.id)
        return user


def generate_new_tokens(
    identity: int, old_jti_to_revoke: str | None = None
) -> tuple[str | None, str | None]:
    """
    Generates new access and refresh tokens, adding the refresh token's
    JTI to the allowlist atomically. Returns (None, None) on failure.
    """
    try:
        # 1. Revoke the old token FIRST if provided
        if old_jti_to_revoke and not AllowedRefreshToken.revoke_token(
            jti=old_jti_to_revoke
        ):
            _logger.warning(
                "Old refresh token JTI %s not found "
                "for revocation during rotation (user %s).",
                old_jti_to_revoke,
                identity,
            )

        # 2. Generate JTI first
        jti = str(uuid.uuid4())

        # 3. Attempt to create BOTH tokens
        access_token = create_access_token(identity=str(identity))
        refresh_token = create_refresh_token(
            identity=str(identity), additional_claims={"jti": jti}
        )

        # 4. Basic check if creation somehow failed silently (unlikely but safe)
        if not access_token or not refresh_token:
            raise ValueError("Token creation resulted in empty token(s).")

        # 5. Get the precise expiry from the generated refresh token
        # Use the configured secret (assuming single key based on prior discussion)
        secret = current_app.config["JWT_SECRET_KEY"]
        algo = current_app.config.get("JWT_ALGORITHM", "HS256")

        # Decode only to read payload, don't re-verify expiry/signature here
        refresh_payload = jwt.decode(
            refresh_token,
            secret,
            algorithms=[algo],
            options={"verify_signature": False, "verify_exp": False},
        )
        expiry_timestamp = refresh_payload["exp"]  # Get exact expiry timestamp

        # 6. Add JTI to allowlist (uses the already active DB session)
        AllowedRefreshToken.add_token(jti, identity, expiry_timestamp)

        # 7. Commit ONLY if all previous steps succeeded
        db.session.commit()

        _logger.debug(
            "Successfully generated tokens and added refresh JTI %s for user %s.",
            jti,
            identity,
        )

    except Exception:
        # If any step failed, roll back the DB session
        db.session.rollback()
        _logger.exception(
            "Failed to generate tokens or add to allowlist for identity %s", identity
        )
    else:
        return access_token, refresh_token

    # Return None for both on any failure
    return None, None


def _authenticate_via_auth_token(app: Flask, endpoint: str):
    try:
        verify_jwt_in_request(optional=True)  # Verify JWT token (expiry, etc.)
        user_id = get_jwt_identity()
        if user_id:
            with app.app_context():  # Ensure context for DB query
                user = User.query.get(user_id)
            if user:
                g.current_user = user
            else:
                _logger.warning("Access token identity %s not found in DB.", user_id)
    except jwt.ExpiredSignatureError:
        pass  # Access token expired, fallback to the refresh token logic below
    except jwt.InvalidTokenError as e:
        _logger.warning(
            "Invalid access token encountered for endpoint %s: %s", endpoint, e
        )
    except Exception:
        # Catch other potential verification errors
        _logger.exception("Error verifying JWT access token for endpoint %s", endpoint)

    # Migrate users only having a valid access token to the refresh token logic
    refresh_token_cookie = request.cookies.get("refresh_token_cookie")
    if g.current_user and not refresh_token_cookie:
        _logger.debug("Migrating user %s to refresh tokens", g.current_user)
        try:
            (
                g.new_access_token,
                g.new_refresh_token,
            ) = generate_new_tokens(g.current_user.id)
        except Exception:
            _logger.exception(
                "Error generating tokens during refresh cookie restoration",
            )
            g.new_access_token = None
            g.new_refresh_token = None


def _authenticate_via_refresh_token(app: Flask, endpoint: str):
    refresh_token = request.cookies.get("refresh_token_cookie")
    if not refresh_token:
        return

    try:
        (
            refreshed_user_id,
            old_jti,
        ) = verify_refresh_token_and_get_identity(refresh_token)

        if not refreshed_user_id:
            _logger.warning(
                "Refresh token deemed invalid by verification helper (e.g., revoked)."
            )
            return

        with app.app_context():  # Ensure context for DB query
            user = User.query.get(refreshed_user_id)

        if not user:
            _logger.warning(
                "User identity %s from valid refresh token not found in DB. "
                "Endpoint: %s",
                refreshed_user_id,
                endpoint,
            )
            return

        (
            g.new_access_token,
            g.new_refresh_token,
        ) = generate_new_tokens(refreshed_user_id, old_jti)
        g.current_user = user
        _logger.debug("User %s authenticated via refresh token.", user.id)

    except jwt.ExpiredSignatureError, jwt.InvalidTokenError:
        _logger.warning("Refresh token verification failed.", exc_info=True)
    except Exception:
        _logger.warning("Refresh token verification failed.", exc_info=True)


def _authenticate_as_guest_user(app: Flask, endpoint: str):
    try:
        # Create temporary user within app context for DB access
        with app.app_context():
            temp_user = create_temporary_user()
        if not temp_user:
            raise Exception(
                f"Failed to create guest user object, result is falsy: {temp_user}"
            )

        (g.new_access_token, g.new_refresh_token) = generate_new_tokens(temp_user.id)

    except Exception:
        _logger.exception("Failed to create temporary user for endpoint %s", endpoint)
    else:
        g.current_user = temp_user


def authenticate_request(app: Flask):
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
    if CrawlerDetect(user_agent=request.headers.get("User-Agent")).isCrawler():
        _logger.info("Bot detected, skipping auth.")
        return None

    # 3. Attempt Access Token Auth
    _authenticate_via_auth_token(app, endpoint)

    if g.current_user:
        return None

    # 4. Attempt Refresh Token Auth
    _authenticate_via_refresh_token(app, endpoint)

    if g.current_user:
        return None

    # 5. Handle Guest User / Unauthenticated for Protected Route
    _authenticate_as_guest_user(app, endpoint)

    if g.current_user:
        return None

    return make_response("Server error creating guest session", 500)
