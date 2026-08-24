import re
from datetime import UTC, datetime, timedelta, timezone

from atpx.support.clock import compact, moment, stamp, today

_AWARE = datetime(2026, 8, 25, 3, 4, 5, 678901, tzinfo=timezone(timedelta(hours=9)))


def test_moment_is_timezone_aware_utc() -> None:
    assert moment().tzinfo is UTC


def test_stamp_renders_utc_with_an_explicit_z_suffix() -> None:
    value = stamp()
    assert value.endswith("Z")
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(0)


def test_stamp_converts_an_offset_instant_to_utc() -> None:
    assert stamp(_AWARE) == "2026-08-24T18:04:05.678901Z"


def test_stamps_order_lexicographically_like_the_clock() -> None:
    earlier, later = stamp(_AWARE), stamp(_AWARE + timedelta(microseconds=1))
    assert earlier < later


def test_compact_is_filename_safe_and_utc() -> None:
    assert compact(_AWARE) == "20260824T180405678901Z"
    assert re.fullmatch(r"\d{8}T\d{12}Z", compact())


def test_today_is_the_utc_date() -> None:
    assert today() == moment().date().isoformat()
