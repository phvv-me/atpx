from collections.abc import Collection
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import NodeStore, Workspace
from atpx.study import Design
from atpx.support.clock import today

from ..support import node_text, planted

_BASE = int(today().replace("-", "")) * 100


@given(offsets=st.lists(st.integers(0, 6), max_size=6, unique=True))
def test_allocation_yields_the_smallest_base_no_node_ever_drew(
    offsets: Collection[int], tmp_path_factory: pytest.TempPathFactory
) -> None:
    blueprints = tmp_path_factory.mktemp("registry")
    taken = ", ".join(str(_BASE + offset) for offset in offsets)
    planted(blueprints, "holder", text=node_text(front={"seeds": f"[{taken}]"}))
    fresh = Design(NodeStore(blueprints)).allocated()
    assert fresh == min(base for base in range(_BASE, _BASE + 8) if base - _BASE not in offsets)


def test_the_registry_is_workspace_wide_and_the_allocation_is_recorded(root: Path) -> None:
    space = Workspace(root)
    space.design("demo")
    space.design("dep")
    assert space.nodes.find("demo").front.seeds == [_BASE]
    assert space.nodes.find("dep").front.seeds == [_BASE + 1]
    assert str(_BASE + 1) in (space.blueprints / "dep" / f"design-{today()}.md").read_text()


def test_a_second_design_on_the_same_day_is_refused(root: Path) -> None:
    space = Workspace(root)
    space.design("demo")
    with pytest.raises(FileExistsError, match="design tomorrow's run"):
        space.design("demo")
    assert space.nodes.find("demo").front.seeds == [_BASE]
