import base64
import http
import ipaddress
import json
import logging
import os
import socket
import threading
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from flask import current_app
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from app.errors import UserFeedbackError, WebPushSubscriptionExpiredError

_logger = logging.getLogger(__name__)


def validate_push_endpoint(endpoint: str | None) -> None:
    """Reject push endpoints that would let the scheduler make requests to
    internal hosts (SSRF). The endpoint is later POSTed to by the server from
    inside the network, so it must be a public HTTPS URL.

    Raises UserFeedbackError on an invalid endpoint.
    """
    if not endpoint or not isinstance(endpoint, str):
        raise UserFeedbackError("Invalid push endpoint.")

    parts = urlsplit(endpoint)
    if parts.scheme != "https":
        raise UserFeedbackError("Push endpoint must use https.")

    host = parts.hostname
    if not host:
        raise UserFeedbackError("Push endpoint has no host.")

    # Resolve every address the host maps to and reject if any is non-public.
    # (A hostname that resolves to a mix of public and private addresses is
    # still treated as unsafe.)
    try:
        addrinfos = socket.getaddrinfo(
            host, parts.port or 443, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror as exc:
        raise UserFeedbackError("Push endpoint host cannot be resolved.") from exc

    addresses = {info[4][0] for info in addrinfos}
    if not addresses:
        raise UserFeedbackError("Push endpoint host cannot be resolved.")

    for addr in addresses:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            raise UserFeedbackError("Push endpoint host is invalid.") from None
        if not _is_public_ip(ip):
            raise UserFeedbackError("Push endpoint resolves to a disallowed address.")


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Whether an address is safe to POST to from inside the network."""
    return not any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    )


# Serialises VAPID lazy init across threads. Without it, concurrent first
# requests could each call create_vapid(); when no key is pre-configured that
# generates fresh keypairs and races on disk, leaving threads with split keys.
_vapid_init_lock = threading.Lock()


def get_vapid_key_path() -> str:
    """
    Get the paths to the VAPID key files.

    Returns:
        str: Path to the private key file
    """

    # Use instance directory for storing key
    instance_path = current_app.instance_path
    try:
        if not os.path.exists(instance_path):
            os.makedirs(instance_path, exist_ok=True)
    except Exception:
        _logger.exception("Error creating instance directory: %s", instance_path)
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
    # save_key writes with the default umask (often world-readable); tighten the
    # EC private key to owner-only immediately.
    try:
        os.chmod(private_key_path, 0o600)
    except OSError:
        _logger.exception("Could not chmod VAPID key file %s", private_key_path)

    return vapid


def get_vapid() -> Vapid:
    """Gets the cached Vapid instance, creating it if necessary."""
    extensions = current_app.extensions
    if "vapid" not in extensions:
        with _vapid_init_lock:
            if "vapid" not in extensions:
                _logger.debug("Initializing VAPID instance for this app context.")
                extensions["vapid"] = create_vapid()
    return extensions["vapid"]


def get_vapid_public_key_for_js() -> str:
    """
    Get the VAPID public key in the format needed for JavaScript.

    Returns:
        VAPID public key in URL-safe base64 format
    """
    extensions = current_app.extensions
    if "vapid_public_key_for_js" not in extensions:
        with _vapid_init_lock:
            if "vapid_public_key_for_js" not in extensions:
                extensions["vapid_public_key_for_js"] = get_public_key_b64(get_vapid())
    return extensions["vapid_public_key_for_js"]


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

    if isinstance(subscription_info, str):
        try:
            subscription_info = json.loads(subscription_info)
        except json.JSONDecodeError:
            _logger.exception("Failed to parse subscription_info JSON")
            return False

    # Re-validate at send time: the endpoint was checked at subscription, but
    # DNS could have been repointed at an internal host since (SSRF).
    try:
        validate_push_endpoint(subscription_info.get("endpoint"))
    except UserFeedbackError:
        _logger.warning("Refusing to send push to disallowed endpoint")
        return False

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(data),
            vapid_private_key=get_vapid(),
            vapid_claims=vapid_claims,
        )
    except WebPushException as e:
        # Check if subscription is expired
        if e.response and e.response.status_code == http.HTTPStatus.GONE:
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
