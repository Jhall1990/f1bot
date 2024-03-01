import constants

import sys
import sqlite3
import argparse
from icalendar import Calendar


def get_event_info(category):
    if category.lower().startswith("fp"):
        return constants.EventType.PRACTICE, int(category[-1]) - 1
    elif category.lower() == "qualifying":
        return constants.EventType.QUALI, 0
    elif category.lower() == "grand prix":
        return constants.EventType.RACE, 0
    elif category.lower() == "sprint":
        return constants.EventType.SPRINT, 0
    elif category.lower() == "sprint shootout":
        return constants.EventType.SPRINT_QUALI, 0
    else:
        raise Exception(f"Unknown category: {category}")


class Event():
    def __init__(self, country, event_type, event_number, start_time, desc):
        self.country = country
        self.event_type = event_type
        self.event_number = event_number
        self.start_time = start_time
        self.desc = desc

    def to_db(self):
        return f'("{self.country}", "{self.event_type}", {self.event_number}, "{self.start_time}", "{self.desc}")'

    @staticmethod
    def from_ics(event):
        country = str(event.get("LOCATION").strip())
        cats = get_event_info(str(event.get("CATEGORIES").cats[0]))
        event_type = cats[0]
        if len(cats) > 1:
            event_number = cats[1]
        else:
            event_number = 0

        start_time = event.get("DTSTART").dt
        desc = str(event.get("SUMMARY"))
        return Event(country, event_type, event_number, start_time, desc)



def read_calendar(calendar):
    """
    Reads all the events from an ics file.
    """
    events = []
    with open(calendar, "rb") as f:
        cal = Calendar.from_ical(f.read())

    for event in cal.walk():
        if event.name == "VEVENT" and event.get("SUMMARY") != "Formula 1 in your calendar!":
            events.append(Event.from_ics(event))
    return events


def create_db(db_file, events):
    con = sqlite3.connect(db_file)
    cur = con.cursor()

    # Create the table
    query = "CREATE TABLE races(country, event_type, event_number, start_time, desc)"
    cur.execute(query)

    insert_query = "INSERT INTO races VALUES"

    for event in events:
        query = f"{insert_query} {event.to_db()}"
        cur.execute(query)
    con.commit()


def convert(calendar, db):
    events = read_calendar(calendar)
    create_db(db, events)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--calendar", help="The input calendar file", required=True)
    ap.add_argument("-d", "--db", help="The output db file", required=True)
    args = ap.parse_args()
    convert(args.calendar, args.db)
