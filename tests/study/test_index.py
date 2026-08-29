import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import Node, NodeStore, Status
from atpx.study import BlankIndexError, LedgerIndex

from ..support import node_text, raced

nodes_strategy = st.dictionaries(
    keys=st.from_regex(r"node-[a-z]{1,8}", fullmatch=True),
    values=st.sampled_from(Status),
    min_size=1,
    max_size=6,
)


def build_store(
    nodes: Mapping[str, Status], depends: Mapping[str, str] | None = None
) -> NodeStore:
    store = NodeStore(Path(tempfile.mkdtemp()))
    for slug, status in nodes.items():
        directory = store.path / slug
        directory.mkdir()
        front = {"depends": f"[{depends[slug]}]"} if depends and slug in depends else None
        (directory / "node.md").write_text(
            node_text(status, summary=f"summary of {slug}", title=slug, front=front)
        )
    return store


@given(nodes_strategy)
def test_every_node_lands_once_in_the_table(nodes: dict[str, Status]) -> None:
    store = build_store(nodes)
    text = LedgerIndex(store.path / "INDEX.md").render(store.nodes())
    for slug, status in nodes.items():
        rows = [line for line in text.splitlines() if line.startswith(f"| [[{slug}]]")]
        assert rows == [f"| [[{slug}]] | {status.value} | summary of {slug} |"]


@given(nodes_strategy)
def test_the_graph_names_every_node_with_its_state_and_claim(nodes: dict[str, Status]) -> None:
    store = build_store(nodes)
    graph = LedgerIndex(store.path / "INDEX.md").graph(store.nodes())
    assert [row["slug"] for row in graph["nodes"]] == sorted(nodes)
    for row in graph["nodes"]:
        slug = str(row["slug"])
        assert row["state"] == nodes[slug].value and row["claim"] == f"summary of {slug}"


@given(nodes_strategy)
def test_edges_come_from_the_depends_frontmatter(nodes: dict[str, Status]) -> None:
    slugs = sorted(nodes)
    depends = {slug: slugs[0] for slug in slugs[1:]}
    store = build_store(nodes, depends)
    graph = LedgerIndex(store.path / "INDEX.md").graph(store.nodes())
    assert graph["edges"] == [{"from": slug, "to": slugs[0]} for slug in slugs[1:]]


def test_first_generation_moves_hand_authored_prose_under_the_manual_section(root: Path) -> None:
    store = NodeStore(root / "research" / "math")
    index = LedgerIndex(store.path / "INDEX.md")
    hand_written = index.path.read_text()
    text = index.render(store.nodes())
    assert text.startswith("# Mathematics Results Index\n")
    assert LedgerIndex.MARK in text and LedgerIndex.MANUAL in text
    manual = text.partition(LedgerIndex.MANUAL)[2]
    for line in hand_written.splitlines()[1:]:
        assert line in manual if line.strip() else True
    assert manual.index("Preamble prose.") < manual.index("Footer prose.")


def test_regeneration_is_idempotent_and_preserves_the_manual_section(root: Path) -> None:
    store = NodeStore(root / "research" / "math")
    index = LedgerIndex(store.path / "INDEX.md")
    first = index.write(store.nodes())
    assert index.path.read_text() == first
    assert index.render(store.nodes()) == first
    assert "Preamble prose." in first and "Footer prose." in first


def test_write_emits_the_graph_json_beside_the_index(root: Path) -> None:
    store = NodeStore(root / "research" / "math")
    index = LedgerIndex(store.path / "INDEX.md")
    index.write(store.nodes())
    assert index.graph_path == store.path / "INDEX.json"
    graph = json.loads(index.graph_path.read_text())
    assert {row["slug"] for row in graph["nodes"]} == {"demo", "dep", "blocked"}


def test_stale_lists_both_artifacts_until_written_then_nothing(root: Path) -> None:
    store = NodeStore(root / "research" / "math")
    index = LedgerIndex(store.path / "INDEX.md")
    assert index.stale(store.nodes()) == [index.path, index.graph_path]
    index.write(store.nodes())
    assert index.stale(store.nodes()) == []
    store.find("demo").set_status(Status.ABANDONED)
    assert index.stale(store.nodes()) == [index.path, index.graph_path]


def regenerating(path: Path, nodes: Sequence[Node]) -> Callable[[], None]:
    """One competing session's job: regenerate this index repeatedly from its own writer."""
    writer = LedgerIndex(path)

    def regenerate() -> None:
        for _ in range(20):
            writer.write(nodes)

    return regenerate


def test_racing_regenerations_never_leave_a_mixed_pair(root: Path) -> None:
    """Both artifacts move under one lock, so no session can leave one from each generation."""
    store = NodeStore(root / "research" / "math")
    path = store.path / "INDEX.md"
    every = store.nodes()
    raced(regenerating(path, every), regenerating(path, every[:1]))
    rows = [line for line in path.read_text().splitlines() if line.startswith("| [[")]
    tabled = {line.split("[[")[1].split("]]")[0] for line in rows}
    graph = json.loads(path.with_suffix(".json").read_text())
    assert tabled == {str(row["slug"]) for row in graph["nodes"]}


def test_a_missing_index_generates_from_scratch_without_a_manual_section(tmp_path: Path) -> None:
    note = tmp_path / "note" / "node.md"
    note.parent.mkdir()
    note.write_text(node_text(Status.SKETCHED, summary="s", title="note"))
    index = LedgerIndex(tmp_path / "Fresh Index.md")
    text = index.render([Node(note)])
    assert text.startswith("# Fresh Index\n")
    assert "| [[note]] | sketched | s |" in text
    assert LedgerIndex.MANUAL not in text


def test_a_statusless_special_node_shows_its_kind_and_a_claim_node_shows_nothing(
    tmp_path: Path,
) -> None:
    pool = tmp_path / "pool" / "node.md"
    pool.parent.mkdir(parents=True)
    pool.write_text(node_text(None, title="pool", front={"kind": "probe-pool"}))
    bare = tmp_path / "bare" / "node.md"
    bare.parent.mkdir()
    bare.write_text(node_text(None, title="bare claim"))
    index = LedgerIndex(tmp_path / "INDEX.md")
    assert index.state(Node(pool)) == "probe-pool"
    assert index.state(Node(bare)) == ""
    assert index.claim(Node(bare)) == "bare claim"


def test_a_claim_with_a_pipe_cannot_break_the_table(tmp_path: Path) -> None:
    note = tmp_path / "piped" / "node.md"
    note.parent.mkdir()
    note.write_text(node_text(summary="a | b", title="piped"))
    table = LedgerIndex(tmp_path / "INDEX.md").table([Node(note)])
    (row,) = [line for line in table.splitlines() if "piped" in line]
    assert row == "| [[piped]] | open | a \\| b |"


def test_a_regeneration_that_found_no_nodes_refuses_to_blank_the_index(root: Path) -> None:
    """The field failure: a blueprints root that matched nothing emptied a populated index.

    Zero nodes over an index that carries rows is a root that does not exist, never a
    workspace that lost every claim, so the roots searched are what the refusal names.
    """
    store = NodeStore(root / "research" / "math")
    index = LedgerIndex(store.path / "INDEX.md", store.path)
    generated = index.write(store.nodes())
    with pytest.raises(BlankIndexError) as refusal:
        index.write([])
    assert str(store.path) in str(refusal.value)
    assert index.path.read_text() == generated


def test_a_refusal_says_so_when_the_index_was_handed_no_roots_at_all(root: Path) -> None:
    store = NodeStore(root / "research" / "math")
    index = LedgerIndex(store.path / "INDEX.md")
    index.write(store.nodes())
    with pytest.raises(BlankIndexError, match="none declared"):
        index.write([])


def test_an_index_with_no_rows_to_lose_still_generates_from_an_empty_workspace(
    tmp_path: Path,
) -> None:
    """Nothing to drop is nothing to refuse: the guard reads rows, not emptiness."""
    index = LedgerIndex(tmp_path / "INDEX.md")
    assert "| Node | State | Claim |" in index.write([])


def test_a_leftover_lock_neither_blocks_the_next_run_nor_survives_it(root: Path) -> None:
    """What a killed session leaves: a lock file the kernel already dropped the lock behind."""
    store = NodeStore(root / "research" / "math")
    index = LedgerIndex(store.path / "INDEX.md")
    leftover = Path(f"{index.path}.lock")
    leftover.write_text("")
    index.write(store.nodes())
    assert not leftover.exists()
