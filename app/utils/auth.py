import logging
import traceback
import uuid

import jwt
from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token

from app.extensions import db
from app.models.allowed_refresh_token import AllowedRefreshToken
from app.models.user import User

_logger = logging.getLogger(__name__)


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
                f"Refresh token JTI '{jti}' for user {identity} not "
                "found in allowlist (revoked or invalid)."
            )
            # Treat non-existence in allowlist as an invalid token scenario.
            raise jwt.InvalidTokenError(
                "Refresh token is not allowed (revoked or invalid)."
            )

        # 3. If decoding passed and JTI is allowed, return the user identity
        _logger.debug(
            f"Refresh token verified successfully for JTI '{jti}', user {identity}."
        )
        return int(identity), jti

    except jwt.ExpiredSignatureError as e:
        # Log expiry specifically
        payload_info = jwt.decode(
            encoded_token, options={"verify_signature": False, "verify_exp": False}
        )
        _logger.info(
            f"Refresh token has expired (signature level). "
            f"JTI: {payload_info.get('jti', 'N/A')}, "
            f"User: {payload_info.get('sub', 'N/A')}"
        )

        raise e

    except jwt.InvalidTokenError as e:
        # Catch other decoding errors or the explicit raises from above
        _logger.warning(f"Invalid refresh token encountered: {e}")
        raise e  # Re-raise the original exception

    except Exception as e:
        # Catch unexpected errors
        _logger.error(
            f"Unexpected error during refresh token verification: {e}",
            exc_info=True,
        )
        # Wrap unexpected errors in InvalidTokenError for consistent handling
        raise jwt.InvalidTokenError(f"Refresh token verification failed: {e}") from e


def create_temporary_user():
    """Creates and returns a guest User"""
    # Needs database interaction
    try:
        user = User()
        db.session.add(user)
        db.session.commit()
        _logger.debug(f"Created temporary user {user.id}")
        return user
    except Exception:
        _logger.exception("Failed to create temporary user")
        # Ensure rollback in case of error during commit
        db.session.rollback()
        return None


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
                f"Old refresh token JTI {old_jti_to_revoke} "
                f"not found for revocation during rotation (user {identity})."
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
            f"Successfully generated tokens and "
            f"added refresh JTI {jti} for user {identity}."
        )
        return access_token, refresh_token

    except Exception as e:
        # If any step failed, roll back the DB session
        db.session.rollback()
        _logger.error(
            "Failed to generate tokens or add to allowlist for identity "
            f"{identity}: {e}\n{traceback.format_exc()}",
            exc_info=True,
        )

        # Return None for both on any failure
        return None, None
