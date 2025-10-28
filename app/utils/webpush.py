import base64
import json
import logging
import os

from cryptography.hazmat.primitives import serialization
from flask import current_app
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from app.exceptions import WebPushSubscriptionExpiredError

_logger = logging.getLogger(__name__)


def get_vapid_key_path() -> str:
    """
    Get the paths to the VAPID key files.

    Returns:
        str: Path to the private key file
    """

    # Use instance directory for storing key
    instance_path = current_app.instance_path
    return os.path.join(instance_path, "vapid.private.pem")


def get_public_key_b64(vapid_instance: Vapid) -> str:
    """Helper to extract URL-safe Base64 public key from Vapid object."""
    public_key_bytes = vapid_instance.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    # Encode raw bytes to URL-safe Base64 string (and remove padding)
    return base64.urlsafe_b64encode(public_key_bytes).rstrip(b"=").decode("utf-8")


def create_vapid() -> Vapid:
    private_key = os.environ.get("VAPID_PRIVATE_KEY")
    if private_key:
        try:
            return Vapid.from_string(private_key)
        except Exception:
            _logger.exception("Error loading VAPID key from environment")
            # Continue below

    private_key = current_app.config.get("VAPID_PRIVATE_KEY")
    if private_key:
        try:
            return Vapid.from_string(private_key)
        except Exception:
            _logger.exception("Error loading VAPID key from config")
            # Continue below

    private_key_path = get_vapid_key_path()
    if os.path.exists(private_key_path):
        return Vapid.from_file(private_key_path)

    _logger.info("Generating new VAPID key and saving to %s", private_key_path)
    vapid = Vapid()
    vapid.generate_keys()
    vapid.save_key(private_key_path)

    return vapid


def get_vapid() -> Vapid:
    """Gets the cached Vapid instance, creating it if necessary."""
    if not hasattr(current_app, "vapid"):
        print("Initializing VAPID instance for this app context.")
        current_app.vapid = create_vapid()
    return current_app.vapid


def get_vapid_public_key_for_js() -> str:
    """
    Get the VAPID public key in the format needed for JavaScript.

    Returns:
        VAPID public key in URL-safe base64 format
    """
    if not hasattr(current_app, "vapid_public_key_for_js"):
        current_app.vapid_public_key_for_js = get_public_key_b64(get_vapid())
    return current_app.vapid_public_key_for_js


def send_web_push(
    subscription_info: dict, data: dict, vapid_claims: dict | None = None
) -> bool:
    """
    Send a Web Push notification.

    Args:
        subscription_info: Push subscription information from the browser
        data: Data to send in the notification
        vapid_claims: Optional VAPID claims (defaults to using email from config)

    Returns:
        True if successful, False otherwise
    """
    email_sender = current_app.config.get("MAIL_DEFAULT_SENDER", "app@cinetag.it")
    if not vapid_claims:
        vapid_claims = {"sub": f"mailto:{email_sender}"}

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(data),
            vapid_private_key=get_vapid(),
            vapid_claims=vapid_claims,
        )
    except WebPushException as e:
        # Check if subscription is expired
        if e.response and e.response.status_code == 410:
            raise WebPushSubscriptionExpiredError(
                "Push subscription has expired or been unsubscribed",
                subscription_info=subscription_info,
            ) from None

        # Handle other errors
        _logger.exception("WebPushException")
        return False
    except Exception:
        _logger.exception("Error sending push notification")
        return False
    else:
        return True
