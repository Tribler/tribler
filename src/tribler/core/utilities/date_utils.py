import datetime
from contextlib import contextmanager
from unittest.mock import patch


class FrozenDateTime(datetime.datetime):
    UTC_NOW = datetime.datetime.utcnow()

    @classmethod
    def move_to(cls, iso_date: str):
        cls.UTC_NOW = datetime.datetime.fromisoformat(iso_date)

    @classmethod
    def utcnow(cls):
        return cls.UTC_NOW


@contextmanager
def freeze_time(iso_date_time: str) -> FrozenDateTime:
    FrozenDateTime.move_to(iso_date_time)

    with patch('datetime.datetime', FrozenDateTime):
        yield FrozenDateTime
