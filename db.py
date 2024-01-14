import pytz
import discord
import sqlite3
import contextlib
from datetime import datetime, timezone

from constants import EventType


class Event():
    est = pytz.timezone("US/Eastern")
    dt_str = r"%Y-%m-%d %H:%M:%S"

    def __init__(self, country, event_type, event_number, start_time, desc):
        self.country = country
        self.event_type = event_type
        self.event_number = event_number
        self.start_datetime = datetime.fromisoformat(start_time)
        self.desc = desc

    def __str__(self):
        return f"{self.country}: {self.event_string()}: {self.time_str()}"

    def event_string(self):
        if self.event_type == EventType.RACE:
            return "Grand Prix"
        if self.event_type == EventType.QUALI:
            return "Qualifying"
        if self.event_type == EventType.SPRINT:
            return "Sprint Race"
        if self.event_type == EventType.PRACTICE:
            return f"FP{self.event_number+1}"
        if self.event_type == EventType.SPRINT_QUALI:
            return f"Sprint Shootout"

    def to_est(self):
        return self.start_datetime.astimezone(self.est)

    def time_str(self):
        return self.to_est().strftime(self.dt_str)

    def already_happened(self):
        return datetime.now(timezone.utc) > self.start_datetime

    def to_embed(self, title):
        embed = discord.Embed(title=title, description=self.desc)
        embed.add_field(name="Location", value=self.country, inline=False)
        embed.add_field(name="Event Type", value=self.event_string(), inline=False)
        embed.add_field(name="Time", value=self.time_str(), inline=False)
        embed.set_thumbnail(url="https://as2.ftcdn.net/v2/jpg/02/12/87/95/1000_F_212879543_suVXunCpY8AvZ9QAIpmfCiUTH9J63fEm.jpg")
        return embed

    @staticmethod
    def from_db(row):
        return Event(*row)


def next_event(db_file, event_type):
    select = "SELECT country, event_type, event_number, start_time, desc"
    from_ = "FROM races"
    where = [ "WHERE start_time > datetime()" ]
    limit = "LIMIT 1"

    args = []
    if event_type != EventType.ANY:
        where.append(f"event_type = ?")
        args.append(event_type)

    query = f"{select} {from_} {' AND '.join(where)} {limit}"

    with contextlib.closing(sqlite3.connect(db_file)) as conn:
        with conn as cur:
            result = cur.execute(query, args).fetchone()

    if result:
        return Event.from_db(result)
    return None


def upcoming_events(db_file, event_type):
    select = "SELECT country, event_type, event_number, start_time, desc"
    from_ = "FROM races"
    where = [ "WHERE start_time > datetime()" ]

    args = []
    if event_type != EventType.ANY:
        where.append(f"event_type = ?")
        args.append(event_type)

    query = f"{select} {from_} {' AND '.join(where)}"

    with contextlib.closing(sqlite3.connect(db_file)) as conn:
        with conn as cur:
            results = cur.execute(query, args).fetchall()

    if results:
        return [Event.from_db(result) for result in results]
    return None
