"""Timezone-aware datetime handling.

The backend never accepts or returns naive datetimes: every datetime input is
rejected unless it carries a timezone, and all datetimes are normalized to UTC.
"""

import datetime as dtm
from typing import Annotated, Any

from pydantic import BeforeValidator

NAIVE_DATETIME_ERROR = "Datetime must be timezone-aware, e.g. '2026-07-30T19:00:00+03:00'"


def to_utc_aware(value: Any) -> dtm.datetime:
    """Reject naive datetimes and convert timezone-aware input to UTC."""
    if isinstance(value, dtm.datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(NAIVE_DATETIME_ERROR)
        return value.astimezone(dtm.UTC)
    if isinstance(value, str):
        raw = value.replace("Z", "+00:00")
        try:
            parsed = dtm.datetime.fromisoformat(raw)
        except ValueError:
            raise ValueError("Input should be a valid datetime, e.g. '2026-07-30T19:00:00+03:00'")
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(NAIVE_DATETIME_ERROR)
        return parsed.astimezone(dtm.UTC)
    return value  # let pydantic produce the standard type error


TZAwareDateTime = Annotated[dtm.datetime, BeforeValidator(to_utc_aware)]
