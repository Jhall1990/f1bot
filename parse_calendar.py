import pytz
from datetime import datetime
from icalendar import Calendar, Event

import utils


# Event types
FP1 = 0
FP2 = 1
FP3 = 2
PRACTICE = 3
QUALIFYING = 4
SPRINT = 5
RACE = 6


def get_event_type(summary):
    if "practice 1" in summary.lower():
        return FP1
    elif "practice 2" in summary.lower():
        return FP2
    elif "practice 3" in summary.lower():
        return FP3
    elif "practice" in summary.lower():
        return PRACTICE
    elif "qualifying" in summary.lower():
        return QUALIFYING
    elif "sprint" in summary.lower():
        return SPRINT
    elif "race" in summary.lower():
        return RACE
    raise ValueError(f"Unknown event type {summary}")


def get_event_type_string(event_type):
    map = {
        FP1: "FP1",
        FP2: "FP2",
        FP3: "FP3",
        PRACTICE: "Practice",
        QUALIFYING: "Qualifying",
        SPRINT: "Sprint",
        RACE: "Race",
    }
    return map.get(event_type)


class Event():
    est = pytz.timezone("US/Eastern")
    def __init__(self, event_type, location, start, desc):
        self.event_type = event_type
        self.location = location
        self.start = start
        self.desc = desc

    def to_est(self):
        return self.start.astimezone(self.est)

    def is_today(self):
        return self.to_est().date() == datetime.today().date()

    def already_happened(self):
        return self.est.localize(datetime.today()) > self.to_est()

    def timestr(self):
        return self.to_est().strftime(r"%Y/%m/%d %H:%M:%S")

    def event_string(self):
        return get_event_type_string(self.event_type)

    def __str__(self):
        return f"{self.location}: {get_event_type_string(self.event_type)}: {self.timestr()}"

    @staticmethod
    def from_ics(event):
        event_type = get_event_type(str(event.get("SUMMARY")))
        location = str(event.get("LOCATION").strip())
        start = event.get("DTSTART").dt
        desc = str(event.get("SUMMARY"))
        return Event(event_type, location, start, desc)


def get_upcoming_events(events, event_type):
    tbl = utils.Table(("Location", "Date"))
    for event in events:
        if event.already_happened():
            continue
        if event.event_type == event_type:
            tbl.add_row(event.location, event.to_est())
    return tbl.output()


def get_events(calendar):
    events = []
    with open(calendar, "rb") as cal_file:
        cal = Calendar.from_ical(cal_file.read())
    for event in cal.walk():
        if event.name == "VEVENT":
            events.append(Event.from_ics(event))
    return events
