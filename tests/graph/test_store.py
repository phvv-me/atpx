from pathlib import Path

import pytest

from atpx import NodeStore

from ..support import node_text


def test_store_statuses_and_frontier(root: Path) -> None:
    store = NodeStore(root / "research" / "math")
    assert store.statuses() == {
        "open": ["demo"],
        "in_progress": ["blocked"],
        "sketched": ["dep"],
    }
    frontier = store.frontier()
    assert [node["node"] for node in frontier] == ["demo"]
    assert frontier[0]["deps"] == {"dep": "sketched"}


def test_membership_is_the_existence_of_the_node_file(root: Path) -> None:
    """A node without tags still shows in fleet views, existence is the test."""
    untagged = root / "research" / "math" / "untagged"
    untagged.mkdir()
    (untagged / "node.md").write_text("---\nstatus: open\n---\n\n# Untagged\n\nNo tags at all.\n")
    store = NodeStore(root / "research" / "math")
    assert "untagged" in [node.name for node in store.nodes()]
    assert "untagged" in store.statuses()["open"]


def test_an_absent_status_lands_in_the_invalid_bucket(root: Path) -> None:
    statusless = root / "research" / "math" / "statusless"
    statusless.mkdir()
    (statusless / "node.md").write_text(node_text(status=None))
    assert NodeStore(root / "research" / "math").statuses()["invalid"] == ["statusless (missing)"]


def test_store_find_misses_loudly(root: Path) -> None:
    store = NodeStore(root / "research" / "math")
    assert store.find("dep").name == "dep"
    with pytest.raises(KeyError, match="demo"):
        store.find("nowhere")


def test_frontier_carries_typed_relations(tmp_path: Path) -> None:
    blueprints = tmp_path / "math"
    (blueprints / "parent").mkdir(parents=True)
    (blueprints / "parent" / "node.md").write_text(node_text("sketched"))
    (blueprints / "child").mkdir()
    (blueprints / "child" / "node.md").write_text(
        "---\nstatus: open\ndate: 2026-08-15\nsuccessor_of: parent\n---\n\n"
        "# C\n\nUses [[parent]].\n"
    )
    (entry,) = NodeStore(blueprints).frontier()
    assert entry["node"] == "child"
    assert entry["relations"] == {"successor_of": ["parent"]}
