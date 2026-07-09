from datetime import UTC, datetime, timedelta

from flask_jwt_extended import create_access_token


def _login(client, app, user):
    """Authenticate the test client as the given user via an access token."""
    with app.app_context():
        token = create_access_token(identity=str(user.id))
    client.set_cookie("access_token_cookie", token)


def test_releases_list_view_default(client, app, test_user, test_movies) -> None:
    """/releases defaults to the list view and renders tagged releases."""
    _login(client, app, test_user)
    response = client.get("/releases")
    assert response.status_code == 200
    assert b"release-list" in response.data
    # Fixture approves movies 1, 3, 5 — all upcoming
    assert b'class="approve"' in response.data
    assert b"fullcalendar" not in response.data


def test_releases_calendar_view(client, app, test_user) -> None:
    """/releases?view=calendar renders the calendar container and its scripts."""
    _login(client, app, test_user)
    response = client.get("/releases?view=calendar")
    assert response.status_code == 200
    assert b'id="calendar"' in response.data
    assert b"fullcalendar" in response.data
    assert b"release-list" not in response.data


def test_releases_invalid_view_falls_back_to_list(client, app, test_user) -> None:
    """Unknown view values fall back to the list view."""
    _login(client, app, test_user)
    response = client.get("/releases?view=bogus")
    assert response.status_code == 200
    assert b"release-list" in response.data


def test_releases_view_toggle_present(client, app, test_user) -> None:
    """Both view toggles are rendered with the active one marked."""
    _login(client, app, test_user)
    response = client.get("/releases")
    assert response.status_code == 200
    assert b'class="chip active">List<' in response.data
    assert b"view=calendar" in response.data


def test_old_release_routes_redirect(client, app, test_user) -> None:
    """The pre-merge URLs permanently redirect to the merged page."""
    _login(client, app, test_user)

    response = client.get("/release-dates")
    assert response.status_code == 301
    assert "/releases" in response.headers["Location"]
    assert "view=list" in response.headers["Location"]

    response = client.get("/calendar")
    assert response.status_code == 301
    assert "/releases" in response.headers["Location"]
    assert "view=calendar" in response.headers["Location"]


def test_user_events_api_includes_decision_classnames(
    client, app, test_user, test_movies
) -> None:
    """Calendar events carry their decision as a FullCalendar class name."""
    _login(client, app, test_user)
    start = datetime.now(UTC).date().isoformat()
    end = (datetime.now(UTC) + timedelta(days=40)).date().isoformat()
    response = client.get(f"/api/user/events?start={start}&end={end}")
    assert response.status_code == 200
    events = response.get_json()
    assert len(events) > 0
    for event in events:
        assert event["classNames"] == [event["decision"]]
