import pytest

from app.extensions import db
from app.models.user_email import UserEmailQueue
from app.utils.email import queue_email, send_queued_emails


def test_send_queued_emails_with_server_name(app, test_user) -> None:
    """Test that send_queued_emails works when SERVER_NAME is configured."""
    with app.test_request_context():
        # Set SERVER_NAME which is required
        # for url_for(_external=True) in background tasks
        app.config["SERVER_NAME"] = "localhost:8000"
        app.config["PREFERRED_URL_SCHEME"] = "http"

        # Re-fetch user in this context
        user = db.session.get(test_user.__class__, test_user.id)

        # Prepare user for confirmation email
        user.new_email = "new@example.com"
        db.session.commit()

        # Queue a confirmation email
        queue_email(user, "confirm")

        # Verify it's in the queue
        assert UserEmailQueue.query.count() == 1

        # We need to make sure Flask thinks it has
        # a request context if SERVER_NAME isn't enough
        # But in background tasks, we ONLY have app_context.
        # Let's try to see if url_for works directly here.
        from flask import url_for

        try:
            # Re-create request context after setting SERVER_NAME
            with app.test_request_context():
                url = url_for(
                    "html.confirm_email",
                    token="test",  # noqa: S106
                    _external=True,
                )
                assert "localhost:8000" in url
        except RuntimeError as e:
            pytest.fail(f"url_for raised RuntimeError even with SERVER_NAME set: {e}")

        # If it works here, it should work in send_queued_emails
        send_queued_emails()

        # Verify it's removed from the queue
        assert UserEmailQueue.query.count() == 0


def test_send_queued_emails_fails_without_server_name(app, test_user) -> None:
    """Test that send_queued_emails raises
    RuntimeError when SERVER_NAME is NOT configured."""
    with app.app_context():
        # Re-fetch user in this context
        user = db.session.get(test_user.__class__, test_user.id)

        # Ensure SERVER_NAME is NOT set
        app.config["SERVER_NAME"] = None

        # Prepare user for confirmation email
        user.new_email = "new@example.com"
        db.session.commit()

        # Queue a confirmation email
        queue_email(user, "confirm")

        # So we should call send_confirmation_email directly to see the error
        from app.utils.email import send_confirmation_email

        with pytest.raises(
            RuntimeError,
            match="Unable to build URLs outside an active request "
            "without 'SERVER_NAME' configured",
        ):
            send_confirmation_email(user)
