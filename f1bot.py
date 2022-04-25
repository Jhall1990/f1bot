import sys
import yaml
import discord
from discord.ext import tasks
import calendar
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler


#############
# Constants #
#############
# The location of the calendar file
CALENDAR = "calendar.ics"

# The location of the config file
CONFIG = "config.yaml"

# The location of the discord token file
TOKEN_FILE = "token"

# The location of the log file.
LOG_FILE = "f1bot.log"

# The id of the channel alerts should be sent to.
F1_CHANNEL = 961730240630108191

# How often to check to see if we should send alerts.
EVENT_INTERVAL = 60


###########
# Logging #
###########
def setup_logger(logfile):
    """
    Configure the logger, we use a rotating logger so the file doesn't get too big.
    The max size is 5MB and we keep 2 backups, which honeslty too many, but whatever
    it's 15MB.
    """
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO)
    logger = logging.getLogger(__name__)
    handler = RotatingFileHandler(
        logfile,
        mode='a',
        maxBytes=5*1024*1024, 
        backupCount=2,
        delay=0
    )
    logger.addHandler(handler)


setup_logger(LOG_FILE)


class Command():
    def __init__(self, parts):
        self.prefix = parts[1]
        self.args = parts[2::]


class F1BotClient(discord.Client):
    def __init__(self, events):
        super().__init__()
        self.cmd_string = "!f1"
        self.events = events
        self.config = {}
        self.handled = set()
        self.update_config()

    async def on_ready(self):
        """
        Called when the discord bot has connected to the server.
        """
        print(f"{self.user} has connected!")
        self.do_alerts.start()

    def update_config(self):
        """
        Update the client config with the latest info in the config file.
        This allows us to update the config without having to restart the bot.
        """
        logging.info("Updating config")
        with open(CONFIG, "r") as cfg_file:
            self.config = yaml.safe_load(cfg_file.read())

    ##################
    # Alert Handling #
    ##################
    @tasks.loop(seconds=EVENT_INTERVAL)
    async def do_alerts(self):
        """
        Main loop, runs every EVENT_INTERVAL and checks to see if we should
        send a notification for each event.
        """
        self.update_config()

        for event in self.events:
            await self.maybe_notify(event)
        self.cleanup()

    async def send_notify(self, event, when):
        """
        Send the event notification to the f1 channel.
        """
        channel = self.get_channel(F1_CHANNEL)
        await channel.send(embed=self.create_message(event, when))

    async def maybe_notify(self, event):
        """
        See if we should notify for a given event. First we see if the event already
        happened, if it did we do nothing. Then we check the event start time against
        the notify times for the event type from the config file.
        """
        logging.info(f"Seeing if we should alert for event {event}")

        # See if the event already happened, do nothing if it has.
        if event.already_happened():
            logging.info(f"Event {event} already occured, nothing to do")
            return False

        # Get datetime objects for the current event type.
        notify_times = self.config.get("events", {}).get(event.event_string().lower())
        alert_times = self.get_event_dts(notify_times)

        for alert_time, notify_time in zip(alert_times, notify_times):
            # See if we already handled this alert
            if (notify_time, event) in self.handled:
                logging.info(f"Already notified for event {event} at {notify_time}m prior")
                continue

            if alert_time > event.to_est():
                logging.info(f"Sending notification for event {event} at {notify_time}m prior")
                self.handled.add((notify_time, event))
                await self.send_notify(event, notify_time)

    def create_message(self, event, when):
        """
        Create an embed object for the event notification
        """
        title = f"{event.event_string()} starts in {self.normalize_time(when)}"
        embed = discord.Embed(title=title, description=event.desc)
        embed.add_field(name="Location", value=event.location, inline=False)
        embed.add_field(name="Event Type", value=event.event_string(), inline=False)
        embed.add_field(name="Time", value=event.timestr(), inline=False)
        embed.set_thumbnail(url="https://as2.ftcdn.net/v2/jpg/02/12/87/95/1000_F_212879543_suVXunCpY8AvZ9QAIpmfCiUTH9J63fEm.jpg")
        return embed

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

    def get_event_dts(self, notify_times):
        """
        Create datetime objects for each notify time. The datetime object is the current
        time + the notify time as a timedelta. We use these to compare to a given event
        to see if we should notify.
        """
        dts = []
        for time_ in notify_times:
            dts.append(calendar.Event.est.localize(datetime.today()) + timedelta(minutes=time_))
        return dts

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
        for thing in to_remove:
            self.handled.remove(thing)

    ###################
    # Command Handlng #
    ###################
    async def on_message(self, message):
        """
        Called when a message is sent to the bot. We only handle a simple
        ping command which just verifies the bot is up and working.
        """
        # Ignore messages from the bot
        if message.author == self.user:
            return

        parts = message.content.split()
        if parts and parts[0] == self.cmd_string:
            cmd = Command(parts)
            response = self.message_handler(cmd)
            await message.channel.send(response)
        return

    def message_handler(self, command):
        """
        Message handler, maps commands to their handler function.
        Then calls the function and returns its output.
        """
        handlers = {
            "ping": self.handle_ping,
        }

        handler = handlers.get(command.prefix)

        if handler:
            return handler(command)
        return "Command not supported"

    def handle_ping(self, command):
        """
        Simple ping command, respond "pong", just to make sure bot is up and working.
        """
        return "pong"


####################
# Helper Functions #
####################
def test_event(event_type, location, desc, offset):
    """
    Adds a test event with the given attributes. Useful as F1 events only happen
    every week or so.
    """
    event_date = datetime.today() + timedelta(minutes=offset)
    return calendar.Event(event_type, location, event_date, desc)


def get_token(path):
    """
    Read the discord token and return its contents. Exit if we can't read the file
    or if there is no token in the file.
    """
    try:
        with open(path, "r") as token_file:
            token = token_file.read().strip()
    except FileNotFoundError:
        sys.exit("No discord token file found")

    if not token:
        sys.exit("No discord token found")
    return token


if __name__ == "__main__":
    token = get_token(TOKEN_FILE)
    events = calendar.get_events(CALENDAR)
    client = F1BotClient(events)
    client.run(token)