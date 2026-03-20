from unittest.mock import patch

from app.extensions import db
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
