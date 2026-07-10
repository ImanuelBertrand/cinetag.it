from unittest.mock import patch

from app.extensions import db
from app.models.notification_channel import NotificationChannel
from app.models.user import User


def test_profile_save_display_name(client, app, test_user):
    """Test that display_name is saved correctly in the profile."""
    user_id = test_user.id

    with (
        patch("app.routes.html.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        # Fetch the user within the request context to avoid session conflicts
        user = db.session.get(User, user_id)
        assert user is not None
        mock_get_user.return_value = user

        # Define new profile data
        new_display_name = "Updated Display Name"
        new_language = "de"
        new_region = "DE"

        # Simulate POST request to /profile
        response = client.post(
            "/profile",
            data={
                "display_name": new_display_name,
                "language": new_language,
                "region": new_region,
                "email": user.email,
                "current_password": "",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200

        # Verify changes in the database
        db.session.expire_all()
        updated_user = db.session.get(User, user_id)
        assert updated_user is not None

        assert updated_user.language == new_language
        assert updated_user.region == new_region
        assert updated_user.display_name == new_display_name


def test_profile_save_variants(client, app, test_user):
    """Test various profile save variants."""
    user_id = test_user.id

    with (
        patch("app.routes.html.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        user = db.session.get(User, user_id)
        assert user is not None
        mock_get_user.return_value = user

        # 1. Change only display name
        new_name = "Only Name Change"
        client.post(
            "/profile",
            data={
                "display_name": new_name,
                "language": user.language,
                "region": user.region,
                "email": user.email,
            },
        )
        db.session.expire_all()
        updated_user = db.session.get(User, user_id)
        assert updated_user is not None
        assert updated_user.display_name == new_name

        # 2. Change only language
        new_lang = "fr"
        client.post(
            "/profile",
            data={
                "display_name": new_name,
                "language": new_lang,
                "region": updated_user.region,
                "email": updated_user.email,
            },
        )
        db.session.expire_all()
        updated_user = db.session.get(User, user_id)
        assert updated_user is not None
        assert updated_user.language == new_lang

        # 3. Change only region
        new_reg = "GB"
        client.post(
            "/profile",
            data={
                "display_name": new_name,
                "language": updated_user.language,
                "region": new_reg,
                "email": updated_user.email,
            },
        )
        db.session.expire_all()
        updated_user = db.session.get(User, user_id)
        assert updated_user is not None
        assert updated_user.region == new_reg


def test_notification_email_days_validation(client, app, test_user):
    """The days field accepts comma lists (incl. spaces/0) and rejects junk."""
    user_id = test_user.id

    with (
        patch("app.routes.html.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        user = db.session.get(User, user_id)
        assert user is not None
        mock_get_user.return_value = user

        # Valid: leading zero and a space before a comma (regex-typo regression)
        response = client.post(
            "/profile/notifications",
            data={
                "email_enabled": "1",
                "email_days": "0, 1 ,3",
                "email_with_maybe": "1",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        db.session.expire_all()
        channel = NotificationChannel.query.filter_by(
            user_id=user_id, mode="email"
        ).first()
        assert channel is not None
        assert channel.days_in_advance == [0, 1, 3]

        # Invalid: semicolon-separated is rejected with a feedback message
        response = client.post(
            "/profile/notifications",
            data={"email_enabled": "1", "email_days": "1;3"},
            follow_redirects=True,
        )
        assert b"comma-separated list of numbers" in response.data
