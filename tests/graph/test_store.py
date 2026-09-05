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
        """---
status: open
date: 2026-08-15
successor_of: parent
---

# C

Uses [[parent]].
"""
    )
    (entry,) = NodeStore(blueprints).frontier()
    assert entry["node"] == "child"
    assert entry["relations"] == {"successor_of": ["parent"]}


def test_a_second_node_document_is_its_own_node_with_its_own_state(root: Path) -> None:
    """A directory that re-registers a successor beside its run holds two nodes, not one."""
    directory = root / "research" / "math" / "campaign"
    directory.mkdir()
    (directory / "node.md").write_text(node_text("validated", title="Campaign"))
    (directory / "v2-node.md").write_text(node_text("refuted", title="Campaign v2"))
    store = NodeStore(root / "research" / "math")
    found = {node.name: node.raw_status for node in store.nodes()}
    assert found["campaign"] == "validated"
    assert found["campaign/v2"] == "refuted"
    assert store.statuses()["refuted"] == ["campaign/v2"]


def test_a_second_node_document_is_reached_by_its_own_name(root: Path) -> None:
    directory = root / "research" / "math" / "campaign"
    directory.mkdir()
    (directory / "node.md").write_text(node_text("validated", title="Campaign"))
    (directory / "v2-node.md").write_text(node_text("refuted", title="Campaign v2"))
    store = NodeStore(root / "research" / "math")
    assert "campaign/v2" in store.reach()
    assert store.find("campaign/v2").path == directory / "v2-node.md"
    assert store.resolve("campaign/v2") == directory
