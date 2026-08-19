from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from atpx.graph import LogEntry

from ..support import node_text, written

authors = st.from_regex(r"\w+", fullmatch=True)
tags = st.from_regex(r"[\w.-]+", fullmatch=True)
messages = st.text(max_size=80).map(lambda text: "".join(text.splitlines()))
prose = (
    st.text(
        alphabet=st.characters(categories=("Lu", "Ll", "Nd", "Zs"), max_codepoint=0x2000),
        min_size=1,
        max_size=60,
    )
    .map(str.strip)
    .filter(bool)
)


@given(st.lists(prose, min_size=1, max_size=4))
def test_append_log_keeps_order_inside_the_log_section(messages: Sequence[str]) -> None:
    node = written(node_text() + "\n## Proof\n\nargument\n")
    for i, message in enumerate(messages):
        node.append_log(f"- [prover/t 2026-06-12] {i} {message}")
    log = node.text.split("## Log", 1)[1].split("## Proof", 1)[0]
    appended = [line for line in log.splitlines() if line.startswith("- [prover/t 2026-06-12]")]
    assert appended == [f"- [prover/t 2026-06-12] {i} {m}" for i, m in enumerate(messages)]
    assert "## Proof\n\nargument" in node.text


def test_append_log_creates_a_missing_log_section() -> None:
    node = written(node_text(log=None))
    node.append_log("- [refuter/numeric 2026-06-12] none found.")
    assert node.text.rstrip().endswith("- [refuter/numeric 2026-06-12] none found.")
    assert "## Log" in node.text


def test_log_lines_parse_into_entries() -> None:
    node = written(
        node_text(
            log="""- [prover/start 2026-06-10] opened.
- [refuter/boundary-ties 2026-06-11] survived [[x]].
interleaved prose is skipped"""
        )
    )
    entries = node.log
    assert [(e.who, e.tag, e.date) for e in entries] == [
        ("prover", "start", "2026-06-10"),
        ("refuter", "boundary-ties", "2026-06-11"),
    ]
    assert str(entries[1]) == "- [refuter/boundary-ties 2026-06-11] survived [[x]]."


def test_a_node_without_a_log_has_no_entries() -> None:
    assert written(node_text(log=None)).log == []


@given(who=authors, tag=tags, message=messages)
def test_any_accepted_log_entry_round_trips_through_the_parser(
    *, who: str, tag: str, message: str
) -> None:
    entry = LogEntry.today(who=who, tag=tag, message=message)
    node = written(node_text(log=str(entry)))
    assert node.log == [entry]


def test_log_entries_refuse_fields_the_parser_would_skip() -> None:
    with pytest.raises(ValidationError, match="pattern"):
        LogEntry.today(who="the refuter", tag="t", message="m")
    with pytest.raises(ValidationError, match="pattern"):
        LogEntry.today(who="refuter", tag="a tag", message="m")
    with pytest.raises(ValidationError, match="one line"):
        LogEntry.today(who="refuter", tag="t", message="one\ntwo")


def test_today_stamps_the_utc_date() -> None:
    entry = LogEntry.today(who="settle", tag="in_progress", message="")
    assert entry.date == datetime.now(UTC).date().isoformat()
