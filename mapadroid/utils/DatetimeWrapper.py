import datetime


class DatetimeWrapper:
    @staticmethod
    def now(tz=None) -> datetime.datetime:
        if not tz:
            tz = datetime.timezone.utc
        return datetime.datetime.now(tz)

    @staticmethod
    def fromtimestamp(t, tz=None) -> datetime.datetime:
        if not tz:
            tz = datetime.timezone.utc
        return datetime.datetime.fromtimestamp(t, tz)
