from flask import g
from flask_jwt_extended import create_access_token, create_refresh_token


def test_unset_cookies_when_clear_flag(app):
    with app.test_request_context("/"):
        g.clear_auth_cookies = True
        resp = app.make_response("ok")
        # Explicitly call the after_request hook
        for func in app.after_request_funcs.get(None, []):
            resp = func(resp)

        # Check for Set-Cookie headers that delete cookies
        set_cookie_headers = resp.headers.getlist("Set-Cookie")
        cookie_names = [h.split("=")[0] for h in set_cookie_headers]
        assert "access_token_cookie" in cookie_names
        assert "refresh_token_cookie" in cookie_names
        # Check for deletion markers: expires in the past
        assert any(
            "Expires=Thu, 01 Jan 1970 00:00:00 GMT" in h for h in set_cookie_headers
        )


def test_sets_access_and_refresh_cookies(app):
    with app.test_request_context("/"):
        access_token = create_access_token(identity="test")
        refresh_token = create_refresh_token(identity="test")
        g.new_access_token = access_token
        g.new_refresh_token = refresh_token
        resp = app.make_response("ok")
        for func in app.after_request_funcs.get(None, []):
            resp = func(resp)

        set_cookie_headers = resp.headers.getlist("Set-Cookie")
        assert any(
            f"access_token_cookie={access_token}" in h for h in set_cookie_headers
        )
        assert any(
            f"refresh_token_cookie={refresh_token}" in h for h in set_cookie_headers
        )


def test_after_request_exception_handling(app, monkeypatch):
    with app.test_request_context("/"):
        g.new_access_token = "some-token"  # noqa: S105

        # Mock set_access_cookies to raise an exception
        import flask_jwt_extended

        def mock_set_access_cookies(*a, **k):
            raise Exception("test exception")

        monkeypatch.setattr(
            flask_jwt_extended,
            "set_access_cookies",
            mock_set_access_cookies,
        )

        resp = app.make_response("ok")
        for func in app.after_request_funcs.get(None, []):
            resp = func(resp)
        # Should not raise exception because of try-except in manage_auth_cookies
        assert resp.status_code == 200
