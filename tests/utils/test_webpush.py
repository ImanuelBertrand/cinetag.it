import base64
import os
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid

from app.utils.webpush import (
    create_vapid,
    get_public_key_b64,
    get_vapid,
    get_vapid_public_key_for_js,
)


def _make_vapid_key_string() -> str:
    """Generate a valid VAPID private key string (DER, base64url-encoded)."""
    v = Vapid()
    v.generate_keys()
    der = v.private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.urlsafe_b64encode(der).rstrip(b"=").decode()


# ---------------------------------------------------------------------------
# create_vapid
# ---------------------------------------------------------------------------


def test_create_vapid_from_env(app) -> None:
    """create_vapid() uses VAPID_PRIVATE_KEY from the environment."""
    key_str = _make_vapid_key_string()
    with app.app_context(), patch.dict(os.environ, {"VAPID_PRIVATE_KEY": key_str}):
        vapid = create_vapid()
    assert isinstance(vapid, Vapid)
    assert vapid.public_key is not None


def test_create_vapid_from_config(app) -> None:
    """create_vapid() falls back to VAPID_PRIVATE_KEY in app config."""
    key_str = _make_vapid_key_string()
    with app.app_context():
        app.config["VAPID_PRIVATE_KEY"] = key_str
        # Ensure env var is absent so the config path is exercised
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VAPID_PRIVATE_KEY", None)
            vapid = create_vapid()
    assert isinstance(vapid, Vapid)
    assert vapid.public_key is not None


def test_create_vapid_from_file(app, tmp_path) -> None:
    """create_vapid() loads the key from a PEM file when no env/config key is set."""
    pem_path = str(tmp_path / "vapid.private.pem")
    # Generate and save a key to the temp file
    v = Vapid()
    v.generate_keys()
    v.save_key(pem_path)

    with app.app_context():
        os.environ.pop("VAPID_PRIVATE_KEY", None)
        app.config.pop("VAPID_PRIVATE_KEY", None)
        with patch("app.utils.webpush.get_vapid_key_path", return_value=pem_path):
            vapid = create_vapid()

    assert isinstance(vapid, Vapid)
    assert vapid.public_key is not None


def test_create_vapid_generates_and_saves_key(app, tmp_path) -> None:
    """create_vapid() generates a new key and saves it when no source exists."""
    pem_path = str(tmp_path / "vapid.private.pem")

    with app.app_context():
        os.environ.pop("VAPID_PRIVATE_KEY", None)
        app.config.pop("VAPID_PRIVATE_KEY", None)
        with patch("app.utils.webpush.get_vapid_key_path", return_value=pem_path):
            vapid = create_vapid()

    assert isinstance(vapid, Vapid)
    assert vapid.public_key is not None
    assert os.path.exists(pem_path), "Private key file should have been written"
    # A second call should load the saved file without generating again
    with (
        app.app_context(),
        patch("app.utils.webpush.get_vapid_key_path", return_value=pem_path),
    ):
        vapid2 = create_vapid()
    pub1 = get_public_key_b64(vapid)
    pub2 = get_public_key_b64(vapid2)
    assert pub1 == pub2, "Reloaded key should match the generated key"


# ---------------------------------------------------------------------------
# get_vapid
# ---------------------------------------------------------------------------


def test_get_vapid_returns_vapid_instance(app) -> None:
    """get_vapid() returns a Vapid instance and stores it in app.extensions."""
    with app.app_context():
        app.extensions.pop("vapid", None)
        with patch("app.utils.webpush.create_vapid") as mock_create:
            mock_create.return_value = Vapid()
            mock_create.return_value.generate_keys()
            vapid = get_vapid()

    assert isinstance(vapid, Vapid)
    mock_create.assert_called_once()


def test_get_vapid_caches_in_extensions(app) -> None:
    """get_vapid() stores the instance in app.extensions and reuses it."""
    with app.app_context():
        app.extensions.pop("vapid", None)
        with patch("app.utils.webpush.create_vapid") as mock_create:
            v = Vapid()
            v.generate_keys()
            mock_create.return_value = v

            first = get_vapid()
            second = get_vapid()

    assert first is second
    mock_create.assert_called_once()  # create_vapid called only once


# ---------------------------------------------------------------------------
# get_vapid_public_key_for_js
# ---------------------------------------------------------------------------


def test_get_vapid_public_key_for_js_returns_base64_string(app) -> None:
    """get_vapid_public_key_for_js() returns a non-empty URL-safe base64 string."""
    with app.app_context():
        app.extensions.pop("vapid", None)
        app.extensions.pop("vapid_public_key_for_js", None)
        v = Vapid()
        v.generate_keys()
        with patch("app.utils.webpush.get_vapid", return_value=v):
            key = get_vapid_public_key_for_js()

    assert isinstance(key, str)
    assert len(key) > 0
    # Must be valid URL-safe base64 (with padding restored)
    padded = key + "=" * (-len(key) % 4)
    decoded = base64.urlsafe_b64decode(padded)
    assert len(decoded) == 65  # Uncompressed P-256 point


def test_get_vapid_public_key_for_js_caches_in_extensions(app) -> None:
    """get_vapid_public_key_for_js() caches its result in app.extensions."""
    with app.app_context():
        app.extensions.pop("vapid", None)
        app.extensions.pop("vapid_public_key_for_js", None)
        v = Vapid()
        v.generate_keys()
        with patch("app.utils.webpush.get_vapid", return_value=v) as mock_get:
            first = get_vapid_public_key_for_js()
            second = get_vapid_public_key_for_js()

    assert first == second
    mock_get.assert_called_once()  # get_vapid called only once
