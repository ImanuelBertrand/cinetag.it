from typing import List, Dict

from icalendar import Calendar, Event


def create_ics_file(events: List[Dict[str, str]]) -> bytes:
    cal = Calendar()
    cal.name = "Calendar"
    for event in events:
        ical_event = Event()
        ical_event.name = event["name"]
        ical_event.begin = event["begin"]
        ical_event.end = event["end"]
        cal.add_component(ical_event)
    return cal.to_ical()
