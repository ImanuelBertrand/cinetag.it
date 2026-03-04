from datetime import UTC, datetime, timedelta

from icalendar import Calendar, Event


def create_ics_file(events: list[dict], calendar_name: str) -> bytes:
    """
    Create an ICS calendar file from a list of events.

    Args:
        events: List of event dictionaries with at least 'title' and 'start' keys
        calendar_name: Name of the calendar

    Returns:
        ICS file as bytes
    """
    cal = Calendar()
    cal.add("prodid", "-//CineTagIt//Movie Calendar//EN")
    cal.add("version", "2.0")
    cal.add("name", calendar_name)
    cal.add("X-WR-CALNAME", calendar_name)

    for event in events:
        ical_event = Event()
        ical_event.add("summary", event.get("title", "Movie Release"))

        start_str = event.get("start")
        if isinstance(start_str, str):
            start_date = datetime.fromisoformat(start_str)
        else:
            start_date = event.get("start", datetime.now(UTC))

        # Set the event to all day
        ical_event.add("dtstart", start_date.date())

        # End date is the same as start date for all-day events
        ical_event.add("dtend", (start_date + timedelta(days=1)).date())

        # Add URL if available
        if "url" in event:
            ical_event.add("url", event["url"])

        # Add description if available
        if "overview" in event:
            ical_event.add("description", event["overview"])

        # Add unique ID
        ical_event.add("uid", f"{event.get('id', id(event))}@cinetagit")

        cal.add_component(ical_event)

    return cal.to_ical()
