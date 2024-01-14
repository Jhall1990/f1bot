import os
import sys
import pytz
import yaml
import discord
import hashlib
import argparse
import subprocess
from discord import app_commands
from discord.ext import tasks
from datetime import datetime, timedelta, timezone

import db
import standings as points
import convert_calendar
from constants import EventType, StandingsType


###########
# Helpers #
###########
def event_choices():
    choices = [
        EventType.ANY,
        EventType.RACE,
        EventType.QUALI,
        EventType.SPRINT,
        EventType.PRACTICE,
        EventType.SPRINT_QUALI,
    ]
    return [app_commands.Choice(name=c, value=c) for c in choices]


def standings_choices():
    choices = [
        StandingsType.DRIVER,
        StandingsType.CONSTRUCTOR,
    ]
    return [app_commands.Choice(name=c, value=c) for c in choices]


##########
# Client #
##########
class F1Bot(discord.Client):
    # How often, in seconds, to check to see if alerts should be sent
    event_interval = 60

    # Where to save the downloaded calendar
    calendar_file = "calendar.ics"

    # Where to download the calendar file from
    calendar_url = "https://files-f1.motorsportcalendars.com/f1-calendar_p1_p2_p3_qualifying_sprint_gp.ics"

    def __init__(self, db_file, guild, channel, config_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = discord.app_commands.CommandTree(self)
        self.db_file = db_file
        self.guild = discord.Object(id=guild)
        self.channel = int(channel)
        self.config_path = config_path
        self.events = []
        self.handled = set()
        self.config = {}

    async def setup_hook(self):
        self.tree.copy_global_to(guild=self.guild)
        await self.tree.sync(guild=self.guild)

    async def on_ready(self):
        points.cache()
        self.events = db.upcoming_events(self.db_file, EventType.ANY)
        self.do_alerts.start()
        self.update_calendar_file.start()
        self.update_standings_cache.start()
        print("Ready!")

    #########
    # Tasks #
    #########
    @tasks.loop(seconds=event_interval)
    async def do_alerts(self):
        """
        Main loop, runs every EVENT_INTERVAL and checks to see if we should
        send a notification for each event.
        """
        self.update_config()

        for event in self.events:
            await self.maybe_notify(event)
        self.cleanup()

    @tasks.loop(hours=24)
    async def update_calendar_file(self):
        """
        Download the latest calendar file.
        """
        command = ["wget", "-O", self.calendar_file, self.calendar_url]
        try:
            out = subprocess.check_output(command, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            print(f"Failed to update calendar file\nstdout: {out}\nerr: {err}")

        tmp_db_file = f"tmp.{self.db_file}"
        convert_calendar.convert(self.calendar_file, tmp_db_file)

        with open(self.db_file, "rb") as f:
            existing_hash = hashlib.md5(f.read()).hexdigest()

        with open(tmp_db_file, "rb") as f:
            new_hash = hashlib.md5(f.read()).hexdigest()

        if existing_hash != new_hash:
            os.rename(tmp_db_file, self.db_file)
            print("Updated calendar file")
        else:
            os.remove(tmp_db_file)

    @tasks.loop(hours=1)
    async def update_standings_cache(self):
        points.cache()


    ##################
    # Alert Handling #
    ##################
    def update_config(self):
        """
        Update the client config with the latest info in the config file.
        This allows us to update the config without having to restart the bot.
        """
        with open(self.config_path, "r") as cfg_file:
            self.config = yaml.safe_load(cfg_file.read())

    async def maybe_notify(self, event):
        """
        See if we should notify for a given event. First we see if the event already
        happened, if it did we do nothing. Then we check the event start time against
        the notify times for the event type from the config file.
        """
        # Get datetime objects for the current event type.
        notify_times = self.config.get("events", {}).get(event.event_type)
        alert_times = self.get_event_dts(notify_times)

        for alert_time, notify_time in zip(alert_times, notify_times):
            # See if we already handled this alert
            if (notify_time, event) in self.handled:
                continue

            if alert_time > event.to_est():
                self.handled.add((notify_time, event))
                await self.send_notify(event, notify_time)

    def get_event_dts(self, notify_times):
        """
        Create datetime objects for each notify time. The datetime object is the current
        time + the notify time as a timedelta. We use these to compare to a given event
        to see if we should notify.
        """
        dts = []
        for time_ in notify_times:
            dts.append(datetime.now(timezone.utc) + timedelta(minutes=time_))
        return dts

    async def send_notify(self, event, when):
        """
        Send the event notification to the f1 channel.
        """
        channel = self.get_channel(self.channel)
        title = f"{event.event_string()} starts in {self.normalize_time(when)}"
        await channel.send(embed=event.to_embed(title))

    def normalize_time(self, when):
        """
        Create a string in the form X hours Y minutes based on the input when.
        Hours will only be included if it's > 0.
        """
        hours = when // 60
        when -= hours * 60
        minutes = when
        norm = ""

        if hours and hours == 1:
            norm += f"{hours} hour "
        elif hours:
            norm += f"{hours} hours "

        if minutes and minutes == 1:
            norm += f"{minutes} minute"
        elif minutes:
            norm += f"{minutes} minutes"
        return norm

    def cleanup(self):
        """
        After alerting we keep the events in a handled set, to avoid
        this set growing indefinitely we remove events once they
        have occured.
        """
        to_remove = []
        for when, event in self.handled:
            if event.already_happened():
                to_remove.append((when, event))
        for remove in to_remove:
            self.handled.remove(remove)


####################
# F1 Command Group #
####################
class F1Command(app_commands.Group):
    ################
    # Ping command #
    ################
    @app_commands.command(name="ping")
    async def ping_command(self, interaction):
        await interaction.response.send_message("pong")

    ################
    # Next command #
    ################
    @app_commands.command(name="next")
    @app_commands.choices(event=event_choices())
    async def next_command(self, interaction, event: app_commands.Choice[str]):
        next_event = db.next_event(self.db_file, event.value)
        
        if next_event:
            title = f"Next {next_event.event_string()}"
            await interaction.response.send_message(embed=next_event.to_embed(title))

        err = f"No {event.value}'s left on the calendar"
        if event.value == EventType.ANY:
            err = "No events left on calendar"
        await interaction.response.send_message(err)

    #####################
    # Standings command #
    #####################
    @app_commands.command(name="standings")
    @app_commands.choices(standings=standings_choices())
    async def standings_command(self, interaction, standings: app_commands.Choice[str]):
        if standings.value == StandingsType.DRIVER:
            result = points.get_driver_standings()
        elif standings.value == StandingsType.CONSTRUCTOR:
            result = points.get_constructor_standings()

        await interaction.response.send_message(f"```\n{result}```")

    ####################
    # Calendar command #
    ####################
    @app_commands.command(name="calendar")
    @app_commands.choices(event=event_choices())
    async def calendar_command(self, interaction, event: app_commands.Choice[str]):
        events = db.upcoming_events(self.db_file, event.value)

        if not events:
            err = f"No {event.value}'s left on the calendar"
            if event.value == EventType.ANY:
                err = "No events left on calendar"
            return await interaction.response.send_message(err)

        events_str = []
        events_str_len = 0
        trim_message = "[message too long, trimmed to fit]"

        for event in events:
            event_str = str(event)
            if events_str_len + len(event_str) + 1 > 2000:
                events_str.pop()
                events_str.append(trim_message)
                break

            event_str = str(event)
            events_str.append(event_str)
            events_str_len += len(event_str) + 1

        message = "\n".join(events_str)
        print(len(message))
        await interaction.response.send_message(f"```\n{message}```")

    ####################
    # Foksmash command #
    ####################
    @app_commands.command(name="foksmash")
    async def foksmash_command(self, interaction):
        await interaction.response.send_message("https://www.youtube.com/watch?v=5h4FDy9Eqzs")

    ###################
    # Everything else #
    ###################
    def __init__(self, db_file, *args, **kwargs):
        super().__init__(name="f1", *args, **kwargs)
        self.db_file = db_file


##############
# Arg Parser #
##############
ap = argparse.ArgumentParser()
ap.add_argument("-t", "--token", help="discord bot token", required=True)
ap.add_argument("-g", "--guild", help="discord guild id", required=True)
ap.add_argument("-c", "--channel", help="discord channel to send alerts to", required=True)
ap.add_argument("-C", "--config", help="Path to alert config", required=True)
ap.add_argument("-d", "--db", help="Path to race db file", required=True)
args = ap.parse_args()


##########
# "Main" #
##########
client = F1Bot(args.db, args.guild, args.channel, args.config, intents=discord.Intents.default())
client.tree.add_command(F1Command(args.db))
client.run(args.token)
