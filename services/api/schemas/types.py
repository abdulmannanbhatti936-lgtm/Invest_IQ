"""Shared field types for API schemas."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator


def _as_utc(value: datetime) -> datetime:
    # Naive values in the database were written with datetime.utcnow(), so they are UTC.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# Every datetime the API returns is timezone-aware UTC and serialises with a trailing "Z",
# so clients never have to guess the timezone (the web app shows Asia/Karachi time).
UTCDateTime = Annotated[datetime, AfterValidator(_as_utc)]
