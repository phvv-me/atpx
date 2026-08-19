import tempfile
from collections.abc import Mapping
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from atpx import Node, NodeStore, Status
from atpx.study import ResultsIndex

from ..support import node_text

_HEADINGS = {
    Status.VERIFIED: "## Verified (Lean-checked)",
    Status.VALIDATED: "## Validated (rigorous machine certificate)",
    Status.SKETCHED: "## Sketched (refuter-survived, usable)",
    Status.IN_PROGRESS: "## In progress / open",
    Status.OPEN: "## In progress / open",
    Status.REFUTED: "## Refuted",
    Status.KNOWN: "## Known (already in the literature)",
    Status.ABANDONED: "## Abandoned",
}

nodes_strategy = st.dictionaries(
    keys=st.from_regex(r"node-[a-z]{1,8}", fullmatch=True),
    values=st.tuples(
        st.sampled_from(Status),
        st.dates().map(lambda d: d.isoformat()),
    ),
    min_size=1,
    max_size=6,
)


def build_store(nodes: Mapping[str, tuple[Status, str]]) -> NodeStore:
    store = NodeStore(Path(tempfile.mkdtemp()))
    for slug, (status, date) in nodes.items():
        directory = store.path / slug
        directory.mkdir()
        (directory / "node.md").write_text(
            node_text(status, date=date, summary=f"summary of {slug}", title=slug)
        )
    return store


@given(nodes_strategy)
def test_every_node_lands_once_under_its_heading(nodes: dict[str, tuple[Status, str]]) -> None:
    store = build_store(nodes)
    text = ResultsIndex(store.path / "INDEX.md").render(store.nodes())
    for slug, (status, _) in nodes.items():
        entries = [line for line in text.splitlines() if line.startswith(f"- [[{slug}]]")]
        assert len(entries) == 1
        assert f"summary of {slug}." in entries[0]
        section = text.split(_HEADINGS[status], 1)[1].split("\n##", 1)[0]
        assert f"- [[{slug}]]" in section


@given(nodes_strategy)
def test_sections_sort_by_date_descending_then_name(
    nodes: dict[str, tuple[Status, str]],
) -> None:
    store = build_store(nodes)
    text = ResultsIndex(store.path / "INDEX.md").render(store.nodes())
    by_name = dict(nodes)
    listed = [
        line.split("]]")[0].removeprefix("- [[")
        for line in text.splitlines()
        if line.startswith("- [[")
    ]
    for heading in dict.fromkeys(_HEADINGS.values()):
        group = [n for n in listed if _HEADINGS[by_name[n][0]] == heading]
        assert group == sorted(sorted(group), key=lambda n: by_name[n][1], reverse=True)


def test_preamble_and_footer_survive_regeneration(root: Path) -> None:
    store = NodeStore(root / "research" / "math")
    index = ResultsIndex(store.path / "INDEX.md")
    text = index.render(store.nodes())
    assert text.startswith("---\ndate: 2026-06-10\n---")
    assert "Preamble prose." in text
    assert text.endswith("Footer prose.\n\nLinks: [[Research]].\n")
    assert "- [[dep]], a settled dep." in text
    assert "## In progress / open" in text


def test_rendering_is_idempotent(root: Path) -> None:
    store = NodeStore(root / "research" / "math")
    index = ResultsIndex(store.path / "INDEX.md")
    first = index.render(store.nodes())
    index.path.write_text(first)
    assert index.render(store.nodes()) == first


def test_a_missing_index_gets_a_minimal_preamble(tmp_path: Path) -> None:
    note = tmp_path / "note" / "node.md"
    note.parent.mkdir()
    note.write_text(node_text(Status.SKETCHED, summary="s", title="note"))
    text = ResultsIndex(tmp_path / "Fresh Index.md").render([Node(note)])
    assert text.startswith("# Fresh Index\n")
    assert "- [[note]], s." in text
