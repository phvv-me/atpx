import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import Node, NodeStore, Status, Workspace
from atpx.study import BlankIndexError, LedgerIndex

from ..support import FakeRunner, node_text, planted, raced

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


def test_the_index_lists_each_node_document_with_its_own_state(tmp_path: Path) -> None:
    """One campaign directory, two registrations, two rows, so a refutation cannot hide."""
    store = NodeStore(tmp_path / "math")
    directory = store.path / "campaign"
    directory.mkdir(parents=True)
    (directory / "node.md").write_text(
        node_text("validated", title="Campaign", summary="the v1 campaign")
    )
    (directory / "v2-node.md").write_text(
        node_text("refuted", title="Campaign v2", summary="the v2 successor")
    )
    text = LedgerIndex(store.path / "INDEX.md").render(store.nodes())
    assert "| [[campaign]] | validated | the v1 campaign |" in text
    assert "| [[campaign/v2]] | refuted | the v2 successor |" in text


def noted(directory: Path, text: str) -> Node:
    """One node written under its own blueprint directory."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "node.md"
    path.write_text(text)
    return Node(path)


def test_the_okf_body_lists_every_node_as_a_bullet_under_its_state(root: Path) -> None:
    store = NodeStore(root / "research" / "math")
    text = LedgerIndex(store.path / "INDEX.md").render(store.nodes())
    assert "# Open\n\n* [demo](demo/node.md) - A claim using [[dep]]." in text
    assert text.index("# Open") < text.index("# In progress") < text.index("# Sketched")
    assert text.index("* [dep](dep/node.md) - Settled.") > text.index("# Sketched")


def test_a_bullet_reads_the_okf_title_and_description_keys(tmp_path: Path) -> None:
    node = noted(
        tmp_path / "law",
        node_text(
            front={"title": "The Fused Block Law", "description": "Blocks accumulate exactly."}
        ),
    )
    bullet = LedgerIndex(tmp_path / "index.md").bullet(node)
    assert bullet == "* [The Fused Block Law](law/node.md) - Blocks accumulate exactly."


def test_a_bullet_falls_back_to_the_slug_and_the_first_sentence(tmp_path: Path) -> None:
    node = noted(tmp_path / "law", node_text(body="It holds. And more.", refutation=None))
    assert LedgerIndex(tmp_path / "index.md").bullet(node) == "* [law](law/node.md) - It holds."


def test_a_node_that_describes_itself_nowhere_is_a_bare_link(tmp_path: Path) -> None:
    node = noted(tmp_path / "law", node_text(body="<!-- to write -->", refutation=None))
    assert LedgerIndex(tmp_path / "index.md").bullet(node) == "* [law](law/node.md)"


def test_sections_order_down_the_ladder_and_park_every_other_state_after_it(
    tmp_path: Path,
) -> None:
    nodes = [
        noted(tmp_path / "settled", node_text(Status.VALIDATED)),
        noted(tmp_path / "pool", node_text(None, front={"type": "probe-pool"})),
        noted(tmp_path / "bare", node_text(None)),
    ]
    text = LedgerIndex(tmp_path / "index.md").sections(nodes)
    assert text.index("# Validated") < text.index("# Probe-pool") < text.index("# Unstated")


def test_the_bundle_root_carries_the_one_frontmatter_key_the_format_allows(root: Path) -> None:
    store = NodeStore(root / "research" / "math")
    index = LedgerIndex(store.path / "INDEX.md", store.path, okf_version="0.2")
    text = index.write(store.nodes())
    assert text.startswith('---\nokf_version: "0.2"\n---\n\n# Mathematics Results Index')
    assert index.stale(store.nodes()) == []


def test_the_workspace_declares_which_okf_version_its_index_is_the_root_of(root: Path) -> None:
    (root / "atpx.toml").write_text('[workspace]\nokf_version = "0.2"\n')
    assert Workspace(root, runner=FakeRunner()).index().startswith('---\nokf_version: "0.2"\n---')


def test_a_hand_authored_index_donates_its_body_but_never_its_frontmatter(
    tmp_path: Path,
) -> None:
    index = LedgerIndex(tmp_path / "index.md", okf_version="0.2")
    index.path.write_text('---\nokf_version: "0.2"\n---\n\n# Old Index\n\nKept prose.\n')
    text = index.render([noted(tmp_path / "law", node_text())])
    assert text.count("okf_version") == 1 and text.startswith("---")
    assert "Kept prose." in text.partition(LedgerIndex.MANUAL)[2]


def test_an_unclosed_leading_fence_is_prose_like_any_other_hand_authored_line(
    tmp_path: Path,
) -> None:
    index = LedgerIndex(tmp_path / "index.md")
    index.path.write_text("---\n\n# Old Index\n\nKept prose.\n")
    manual = index.render([noted(tmp_path / "law", node_text())]).partition(LedgerIndex.MANUAL)[2]
    assert "Kept prose." in manual and manual.strip().startswith("---")


def test_an_edge_naming_a_name_the_node_has_left_resolves_to_the_node_of_record(
    tmp_path: Path,
) -> None:
    store = NodeStore(tmp_path / "math")
    planted(store.path, "renamed", text=node_text(front={"aliases": "[old-name]"}))
    planted(store.path, "reader", text=node_text(front={"depends": "[old-name]"}))
    graph = LedgerIndex(store.path / "INDEX.md").graph(store.nodes())
    assert graph["edges"] == [{"from": "reader", "to": "renamed"}]


def test_a_description_that_only_repeats_the_title_is_dropped(tmp_path: Path) -> None:
    node = noted(
        tmp_path / "law",
        node_text(front={"title": "The Fused Block Law", "description": "The fused block law."}),
    )
    bullet = LedgerIndex(tmp_path / "index.md").bullet(node)
    assert bullet == "* [The Fused Block Law](law/node.md)"
