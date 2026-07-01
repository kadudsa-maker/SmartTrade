from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd


WARSAW_TZ = ZoneInfo("Europe/Warsaw")


def current_polish_time():

    return datetime.now(WARSAW_TZ).strftime("%H:%M:%S")


def format_polish_time(value, include_seconds=False):

    dt = to_polish_datetime(value)
    time_format = "%H:%M:%S" if include_seconds else "%H:%M"

    return dt.strftime(time_format)


def to_polish_datetime(value):

    if isinstance(value, pd.Timestamp):
        dt = value.to_pydatetime()

    elif isinstance(value, datetime):
        dt = value

    else:
        dt = _timestamp_to_datetime(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(WARSAW_TZ)


def _timestamp_to_datetime(value):

    timestamp = float(value)

    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000

    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
