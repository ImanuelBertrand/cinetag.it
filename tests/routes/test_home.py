from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.user import User
from app.models.user_movie import UserMovie


def _login(client, app, user):
    """Authenticate the test client as the given user via an access token."""
    with app.app_context():
        token = create_access_token(identity=str(user.id))
    client.set_cookie("access_token_cookie", token)


def test_home_new_guest_sees_marketing_page(client) -> None:
    """A fresh guest without tags gets the demonstrative landing page."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Start tagging" in response.data
    assert b"Create an account" in response.data
    assert b"movie-container" in response.data
    assert b"Your releases in the next 30 days" not in response.data


def test_home_registered_user_sees_dashboard(
    client, app, test_user, test_movies
) -> None:
    """A registered user lands on the dashboard, not the marketing pitch."""
    _login(client, app, test_user)
    response = client.get("/")
    assert response.status_code == 200
    assert b"Your releases in the next 30 days" in response.data
    # Fixture approves movies releasing within the next few days
    assert b"release-list" in response.data
    assert b'class="approve"' in response.data
    # No marketing pitch, no guest banner
    assert b"Start tagging" not in response.data
    assert b"browsing as a guest" not in response.data


def test_home_guest_with_tags_sees_dashboard_and_banner(
    client, app, test_movies
) -> None:
    """A guest who has tagged movies gets the dashboard with a register nudge."""
    with app.app_context():
        guest = User(display_name=None, email=None, region="US", language="en")
        db.session.add(guest)
        db.session.commit()
        db.session.add(UserMovie(user_id=guest.id, movie_id=10, decision="approve"))
        db.session.commit()
        db.session.refresh(guest)

    _login(client, app, guest)
    response = client.get("/")
    assert response.status_code == 200
    assert b"Your releases in the next 30 days" in response.data
    assert b"browsing as a guest" in response.data
