from hypothesis import given
from hypothesis import strategies as st

from atpx import Status

from ..support import node_text, written

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


def test_a_node_is_named_after_its_blueprint_directory() -> None:
    node = written(node_text())
    assert node.name == "note"
    assert node.directory == node.path.parent
    assert {"math", "proof"} <= node.tags


@given(status=statuses, summary=prose, body=prose)
def test_frontmatter_roundtrips(status: Status, *, summary: str, body: str) -> None:
    node = written(node_text(status, summary=summary, body=body))
    assert node.status is status
    assert node.summary == summary
    assert node.date == "2026-06-10"


@given(before=statuses, after=statuses)
def test_set_status_changes_one_field_only(*, before: Status, after: Status) -> None:
    node = written(node_text(before, summary="s"))
    body_before = node.text.split("---", 2)[2]
    node.set_status(after)
    assert node.status is after
    assert node.summary == "s"
    assert node.text.split("---", 2)[2] == body_before


def test_set_status_inserts_when_the_field_is_missing() -> None:
    node = written(node_text(status=None))
    assert node.status is None
    node.set_status(Status.OPEN)
    assert node.status is Status.OPEN


def test_set_status_opens_a_block_on_a_plain_note() -> None:
    """A node with no frontmatter fences gains one rather than raising on the write."""
    node = written("# Just Prose\n\nNo fences here.\n")
    node.set_status(Status.OPEN)
    assert node.status is Status.OPEN
    assert "Just Prose" in node.text


def test_set_status_tolerates_a_missing_closing_fence() -> None:
    """An unclosed frontmatter block edits in place instead of crashing on `index`.

    The read path (`frontmatter`) already treats every line after the opening fence as
    frontmatter, so the write path must edit the same malformed node without raising.
    """
    node = written("---\nstatus: open\ntitle: half written\n")
    node.set_status(Status.VERIFIED)
    assert node.status is Status.VERIFIED
    assert node.frontmatter["title"] == "half written"


def test_a_plain_note_has_no_frontmatter() -> None:
    node = written("# Just Prose\n\nNo fences here.\n")
    assert node.frontmatter == {}
    assert node.status is None


def test_malformed_frontmatter_lines_are_skipped() -> None:
    node = written("---\nstatus: open\nnota bene\n---\n#math #proof\n\n# T\n")
    assert node.frontmatter == {"status": "open"}


def test_an_unclosed_fence_reads_to_the_end() -> None:
    node = written("---\nstatus: open\ndate: 2026-06-12")
    assert node.frontmatter == {"status": "open", "date": "2026-06-12"}


def test_links_are_unique_and_ordered() -> None:
    node = written(node_text(body="Uses [[a]] then [[b]] then [[a]] again."))
    assert node.links == ["a", "b"]


def test_relations_parse_from_flat_frontmatter_keys() -> None:
    text = """---
status: open
date: 2026-08-15
successor_of: response-share-form
shadows: width-law, form
---

# N
"""
    node = written(text)
    assert node.relations == {
        "successor_of": ["response-share-form"],
        "shadows": ["width-law", "form"],
    }


def test_relations_are_empty_without_typed_keys() -> None:
    assert written(node_text()).relations == {}
