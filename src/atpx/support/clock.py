from datetime import UTC, datetime


def moment() -> datetime:
    """The current instant on the one timezone-aware UTC clock every atpx stamp reads."""
    return datetime.now(UTC)


def stamp(instant: datetime | None = None) -> str:
    """An ISO 8601 UTC timestamp carrying an explicit `Z` suffix.

    Microseconds are always rendered, so every stamp has one fixed shape and
    plain string comparison orders stamps the same way the clock does.

    instant: a timezone-aware moment to render, the current one when None.
    """
    reading = (instant or moment()).astimezone(UTC)
    return reading.isoformat(timespec="microseconds").replace("+00:00", "Z")


def compact(instant: datetime | None = None) -> str:
    """A filename-safe UTC stamp, `YYYYmmddTHHMMSSffffffZ`.

    instant: a timezone-aware moment to render, the current one when None.
    """
    return (instant or moment()).astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def today() -> str:
    """The current UTC date, ISO 8601."""
    return moment().date().isoformat()
