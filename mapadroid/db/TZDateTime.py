import datetime
from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator
from loguru import logger


class TZDateTime(TypeDecorator):
    def process_literal_param(self, value, dialect):
        pass

    @property
    def python_type(self):
        pass

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not value.tzinfo:
                logger.debug2("Missing tzinfo, assuming naive datetime - converting to utc")
                #raise TypeError("tzinfo is required")
            value = value.astimezone(datetime.timezone.utc).replace(
                tzinfo=None
            )

        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value
