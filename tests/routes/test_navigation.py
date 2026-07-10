from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.friend_request import FriendRequest
from app.models.user import User


def _login(client, app, user):
    """Authenticate the test client as the given user via an access token."""
    with app.app_context():
        token = create_access_token(identity=str(user.id))
    client.set_cookie("access_token_cookie", token)


def test_nav_guest_shows_login_and_register(client) -> None:
    """A guest (temporary user, no email) sees Login/Register, not Logout."""
    response = client.get("/")
    assert response.status_code == 200
    assert b">Login<" in response.data
    assert b">Register<" in response.data
    assert b">Logout<" not in response.data


def test_nav_registered_shows_logout(client, app, test_user) -> None:
    """A registered user (has email) sees Logout, not Login/Register."""
    _login(client, app, test_user)
    response = client.get("/")
    assert response.status_code == 200
    assert b">Logout<" in response.data
    assert b">Login<" not in response.data
    assert b">Register<" not in response.data


def test_nav_primary_links_present(client) -> None:
    """The flattened primary nav renders Browse and My List as direct links."""
    response = client.get("/")
    assert response.status_code == 200
    assert b">Browse<" in response.data
    assert b">My List<" in response.data
    assert b">Releases<" in response.data
    assert b">Friends<" in response.data
    assert b">Account<" in response.data


def test_footer_links_present(client) -> None:
    """Meta/legal pages are linked from the footer."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"<footer>" in response.data
    for path in (b"/why", b"/how", b"/who", b"/imprint", b"/privacy"):
        assert path in response.data


def test_legal_links_in_account_menu(client, app, test_user) -> None:
    """Imprint/Privacy are also in the nav (footer is unreachable on
    infinite-scroll pages), for guests and registered users alike."""
    # Guest
    response = client.get("/")
    assert response.data.count(b"/imprint") >= 2  # nav + footer

    # Registered
    _login(client, app, test_user)
    response = client.get("/")
    assert response.data.count(b"/imprint") >= 2
    assert response.data.count(b"/privacy") >= 2


def test_nav_active_state_browse(client) -> None:
    """Browse link is marked active on /movies."""
    response = client.get("/movies")
    assert response.status_code == 200
    assert b'class="active">Browse<' in response.data


def test_nav_active_state_my_list(client) -> None:
    """My List link is marked active on a tag-state filter page."""
    response = client.get("/movies/pending")
    assert response.status_code == 200
    assert b'class="active">My List<' in response.data


def test_filter_chips_on_my_list_pages(client) -> None:
    """Tag-state chips render on filter pages with the current one active."""
    response = client.get("/movies/pending")
    assert response.status_code == 200
    assert b'class="chip active">\xe2\x9d\x94 To tag<' in response.data
    for path in (
        b"/movies/approved",
        b"/movies/maybe",
        b"/movies/disapproved",
        b"/movies/reviewed",
    ):
        assert path in response.data


def test_no_filter_chips_on_browse(client) -> None:
    """Browse (filter_mode=all) stays chip-free."""
    response = client.get("/movies")
    assert response.status_code == 200
    assert b"filter-chips" not in response.data


def test_friend_request_badge_for_recipient(client, app, test_user) -> None:
    """A registered recipient with a pending request sees a nav badge."""
    with app.app_context():
        sender = User(
            display_name="Sender",
            email="sender-badge@example.com",
            region="US",
            language="en",
        )
        db.session.add(sender)
        db.session.commit()
        db.session.add(
            FriendRequest(
                requester_id=sender.id, recipient_id=test_user.id, status="pending"
            )
        )
        db.session.commit()

    _login(client, app, test_user)
    response = client.get("/")
    assert response.status_code == 200
    assert b'class="nav-badge"' in response.data


def test_no_friend_request_badge_for_guest(client) -> None:
    """Guests never get a request badge (they cannot receive requests)."""
    response = client.get("/")
    assert response.status_code == 200
    assert b'class="nav-badge"' not in response.data
