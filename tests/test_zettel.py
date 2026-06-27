import tempfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx.roles import Status
from atpx.zettel import Vault, Zettel

from .conftest import zettel_text

statuses = st.sampled_from(Status)
prose = (
    st.text(
        alphabet=st.characters(categories=("Lu", "Ll", "Nd", "Zs"), max_codepoint=0x2000),
        min_size=1,
        max_size=60,
    )
    .map(str.strip)
    .filter(bool)
)


def written(text: str) -> Zettel:
    path = Path(tempfile.mkdtemp()) / "Note.md"
    path.write_text(text)
    return Zettel(path)


@given(statuses, prose, prose)
def test_frontmatter_roundtrips(status: Status, summary: str, body: str) -> None:
    note = written(zettel_text(status, summary=summary, blueprint="research/math/x/", body=body))
    assert note.status is status
    assert note.summary == summary
    assert note.blueprint == "research/math/x/"
    assert note.date == "2026-06-10"
    assert note.is_math_node


@given(statuses, statuses)
def test_set_status_changes_one_field_only(before: Status, after: Status) -> None:
    note = written(zettel_text(before, summary="s"))
    body_before = note.text.split("---", 2)[2]
    note.set_status(after)
    assert note.status is after
    assert note.summary == "s"
    assert note.text.split("---", 2)[2] == body_before


@given(st.lists(prose, min_size=1, max_size=4))
def test_append_log_keeps_order_inside_the_log_section(messages: list[str]) -> None:
    note = written(zettel_text() + "\n## Proof\n\nargument\n")
    for i, message in enumerate(messages):
        note.append_log(f"- [prover/t 2026-06-12] {i} {message}")
    log = note.text.split("## Log", 1)[1].split("## Proof", 1)[0]
    appended = [line for line in log.splitlines() if line.startswith("- [prover/t 2026-06-12]")]
    assert appended == [f"- [prover/t 2026-06-12] {i} {m}" for i, m in enumerate(messages)]
    assert "## Proof\n\nargument" in note.text


def test_append_log_creates_a_missing_log_section() -> None:
    note = written(zettel_text(log=None))
    note.append_log("- [refuter/numeric 2026-06-12] none found.")
    assert note.text.rstrip().endswith("- [refuter/numeric 2026-06-12] none found.")
    assert "## Log" in note.text


def test_set_status_inserts_when_the_field_is_missing() -> None:
    note = written(zettel_text(status=None))
    assert note.status is None and not note.is_math_node
    note.set_status(Status.OPEN)
    assert note.status is Status.OPEN


def test_set_status_opens_a_block_on_a_plain_note() -> None:
    """A note with no frontmatter fences gains one rather than raising on the write."""
    note = written("# Just Prose\n\nNo fences here.\n")
    note.set_status(Status.OPEN)
    assert note.status is Status.OPEN
    assert "Just Prose" in note.text  # the original body survives


def test_set_status_tolerates_a_missing_closing_fence() -> None:
    """An unclosed frontmatter block edits in place instead of crashing on `index`.

    The read path (`frontmatter`) already treats every line after the opening fence as
    frontmatter, so the write path must edit the same malformed note without raising.
    """
    note = written("---\nstatus: open\ntitle: half written\n")
    note.set_status(Status.VERIFIED)
    assert note.status is Status.VERIFIED
    assert note.frontmatter["title"] == "half written"


def test_a_plain_note_has_no_frontmatter() -> None:
    note = written("# Just Prose\n\nNo fences here.\n")
    assert note.frontmatter == {}
    assert note.status is None


def test_malformed_frontmatter_lines_are_skipped() -> None:
    note = written("---\nstatus: open\nnota bene\n---\n#math #proof\n\n# T\n")
    assert note.frontmatter == {"status": "open"}


def test_an_unclosed_fence_reads_to_the_end() -> None:
    note = written("---\nstatus: open\ndate: 2026-06-12")
    assert note.frontmatter == {"status": "open", "date": "2026-06-12"}


def test_links_are_unique_and_ordered() -> None:
    note = written(zettel_text(body="Uses [[A]] then [[B]] then [[A]] again."))
    assert note.links == ["A", "B"]


def test_vault_statuses_and_frontier(root: Path) -> None:
    vault = Vault(root / "vault" / "Zettelkasten")
    assert vault.statuses() == {
        "open": ["Demo Node"],
        "in_progress": ["Blocked"],
        "sketched": ["Dep"],
    }
    frontier = vault.frontier()
    assert [node["node"] for node in frontier] == ["Demo Node"]
    assert frontier[0]["deps"] == {"Dep": "sketched"}


def test_vault_find_misses_loudly(root: Path) -> None:
    vault = Vault(root / "vault" / "Zettelkasten")
    assert vault.find("Dep").name == "Dep"
    with pytest.raises(KeyError, match="Demo Node"):
        vault.find("Nowhere")


def test_log_lines_parse_into_entries() -> None:
    note = written(
        zettel_text(
            log="- [prover/start 2026-06-10] opened.\n"
            "- [refuter/boundary-ties 2026-06-11] survived [[X]].\n"
            "interleaved prose is skipped"
        )
    )
    entries = note.log
    assert [(e.who, e.tag, e.date) for e in entries] == [
        ("prover", "start", "2026-06-10"),
        ("refuter", "boundary-ties", "2026-06-11"),
    ]
    assert str(entries[1]) == "- [refuter/boundary-ties 2026-06-11] survived [[X]]."


def test_a_note_without_a_log_has_no_entries() -> None:
    assert written(zettel_text(log=None)).log == []
