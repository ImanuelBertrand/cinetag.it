"""Config, header and key-permission regressions from the security remediation."""

import pytest

from app.config import ProductionConfig
from app.utils.webpush import create_vapid


class _FakeApp:
    def __init__(self, config) -> None:
        self.config = config


# --- SEC-6: HTTP security headers ---


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    csp = resp.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "script-src 'self' 'nonce-" in csp


def test_csp_nonce_matches_inline_script(client):
    """The nonce in the CSP header must be the one stamped on the inline
    <script> in the page, otherwise the app's own inline JS would be blocked."""
    resp = client.get("/")
    csp = resp.headers["Content-Security-Policy"]
    # Extract nonce-XXXX from the header.
    marker = "'nonce-"
    start = csp.index(marker) + len(marker)
    nonce = csp[start : csp.index("'", start)]
    assert nonce
    assert f'nonce="{nonce}"'.encode() in resp.data


def test_hsts_absent_without_tls(client):
    # JWT_COOKIE_SECURE is False under TestingConfig, so HSTS must be omitted.
    resp = client.get("/")
    assert "Strict-Transport-Security" not in resp.headers


# --- SEC-10: SameSite auth cookies ---


def test_auth_cookies_are_samesite_lax(app):
    from flask import g
    from flask_jwt_extended import create_access_token, create_refresh_token

    with app.test_request_context("/"):
        g.new_access_token = create_access_token(identity="1")
        g.new_refresh_token = create_refresh_token(identity="1")
        resp = app.make_response("ok")
        for func in app.after_request_funcs.get(None, []):
            resp = func(resp)
        set_cookie_headers = resp.headers.getlist("Set-Cookie")
        auth_cookies = [
            h for h in set_cookie_headers if h.startswith("access_token_cookie")
        ]
        assert auth_cookies
        assert all("SameSite=Lax" in h for h in auth_cookies)


# --- SEC-12: production secret assertion ---


def test_prod_config_rejects_missing_secret():
    with pytest.raises(RuntimeError):
        ProductionConfig.init_app(
            _FakeApp({"SECRET_KEY": None, "JWT_SECRET_KEY": "x" * 40})
        )


def test_prod_config_rejects_short_secret():
    with pytest.raises(RuntimeError):
        ProductionConfig.init_app(
            _FakeApp({"SECRET_KEY": "short", "JWT_SECRET_KEY": "x" * 40})
        )


def test_prod_config_rejects_sample_secret():
    sample = "your-extremely-long-and-secure-secret-key-that-is-very-long-for"
    with pytest.raises(RuntimeError):
        ProductionConfig.init_app(
            _FakeApp({"SECRET_KEY": sample, "JWT_SECRET_KEY": "x" * 40})
        )


def test_prod_config_accepts_strong_secrets():
    # Should not raise.
    ProductionConfig.init_app(
        _FakeApp({"SECRET_KEY": "a" * 40, "JWT_SECRET_KEY": "b" * 40})
    )


# --- SEC-11: generated VAPID key is owner-only ---


def test_generated_vapid_key_is_owner_only(app, tmp_path, monkeypatch):
    key_path = tmp_path / "vapid.private.pem"
    monkeypatch.setattr("app.utils.webpush.get_vapid_key_path", lambda: str(key_path))
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    with app.app_context():
        app.config.pop("VAPID_PRIVATE_KEY", None)
        create_vapid()
    assert key_path.exists()
    assert (key_path.stat().st_mode & 0o777) == 0o600
