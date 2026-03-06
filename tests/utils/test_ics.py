from datetime import UTC, datetime

from icalendar import Calendar

from app.utils.ics import create_ics_file


def test_create_ics_file_empty_events() -> None:
    """Test that create_ics_file works with an empty events list."""
    result = create_ics_file([], "Test Calendar")

    assert isinstance(result, bytes)

    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(events) == 0


def test_create_ics_file_with_events() -> None:
    """Test that create_ics_file creates correct ICS content for events."""
    events = [
        {
            "title": "Movie Release",
            "start": "2025-06-15T00:00:00",
            "url": "https://example.com/movie/1",
            "overview": "A great movie",
            "id": 1,
        },
        {
            "title": "Another Movie",
            "start": "2025-07-20T00:00:00",
            "id": 2,
        },
    ]

    result = create_ics_file(events, "My Movie Calendar")

    assert isinstance(result, bytes)

    cal = Calendar.from_ical(result)
    cal_events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(cal_events) == 2

    summaries = {str(e.get("summary")) for e in cal_events}
    assert "Movie Release" in summaries
    assert "Another Movie" in summaries


def test_create_ics_file_calendar_name() -> None:
    """Test that calendar name is set correctly."""
    calendar_name = "Test Calendar Name"
    result = create_ics_file([], calendar_name)

    cal = Calendar.from_ical(result)
    assert str(cal.get("X-WR-CALNAME")) == calendar_name


def test_create_ics_file_event_uid() -> None:
    """Test that events have unique IDs."""
    events = [{"title": "Movie", "start": "2025-06-15T00:00:00", "id": 42}]

    result = create_ics_file(events, "My Calendar")

    cal = Calendar.from_ical(result)
    cal_events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(cal_events) == 1
    assert "42@cinetagit" in str(cal_events[0].get("uid"))


def test_create_ics_file_event_url() -> None:
    """Test that event URL is included when provided."""
    events = [
        {
            "title": "Movie",
            "start": "2025-06-15T00:00:00",
            "url": "https://example.com/movie",
        }
    ]

    result = create_ics_file(events, "My Calendar")

    cal = Calendar.from_ical(result)
    cal_events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert "https://example.com/movie" in str(cal_events[0].get("url"))


def test_create_ics_file_event_description() -> None:
    """Test that event description/overview is included when provided."""
    events = [
        {
            "title": "Movie",
            "start": "2025-06-15T00:00:00",
            "overview": "This is a great movie!",
        }
    ]

    result = create_ics_file(events, "My Calendar")

    cal = Calendar.from_ical(result)
    cal_events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert "This is a great movie!" in str(cal_events[0].get("description"))


def test_create_ics_file_start_as_datetime_object() -> None:
    """Test that create_ics_file handles datetime objects as start dates."""
    dt = datetime(2025, 6, 15, tzinfo=UTC)
    events = [{"title": "Movie", "start": dt}]

    result = create_ics_file(events, "My Calendar")

    assert isinstance(result, bytes)
    cal = Calendar.from_ical(result)
    cal_events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(cal_events) == 1
