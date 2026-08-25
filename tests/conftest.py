from collections.abc import Callable, Iterator
from pathlib import Path
from typing import ClassVar

import pytest

from atpx import Capability, Engine, Workspace

from .support import FakeRunner, node_text, planted, script


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A minimal workspace: root manifest and three blueprint-local nodes."""
    (tmp_path / "atpx.toml").write_text("[workspace]\n")
    blueprints = tmp_path / "research" / "math"
    planted(
        blueprints,
        "demo",
        text=node_text(summary="a demo claim holds"),
        manifest="""[claims]
ok = "python {dir}/checks.py ok"

[claims.gpu]
command = "python {dir}/checks.py gpu"
requires = "cuda"
""",
    )
    planted(
        blueprints,
        "dep",
        text=node_text(
            "sketched",
            title="Dep",
            body="Settled.",
            summary="a settled dep",
            front={"judgments": "[judgments/draft.md]"},
        ),
    )
    (blueprints / "dep" / "judgments").mkdir()
    (blueprints / "dep" / "judgments" / "draft.md").write_text(
        """# Draft judgment for dep

Mechanical verdict survived.

Strongest attacking rung 1 (fake/model).
"""
    )
    planted(
        blueprints,
        "blocked",
        text=node_text("in_progress", title="Blocked", body="Needs [[demo]]."),
    )
    (blueprints / "INDEX.md").write_text(
        """# Mathematics Results Index

Preamble prose.

## Sketched (refuter-survived, usable)

- [[dep]], a settled dep.

Footer prose.

Links: [[Research]].
"""
    )
    return tmp_path


@pytest.fixture
def runner() -> FakeRunner:
    """A recording fake claim runner replying with one canned passing line."""
    return FakeRunner()


@pytest.fixture
def space(root: Path, runner: FakeRunner) -> Workspace:
    """A workspace over the fixture root driven by the recording fake runner."""
    return Workspace(root, runner=runner)


@pytest.fixture
def on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str, str], Path]:
    """A factory that installs a named executable with a given body, alone on PATH."""
    monkeypatch.setenv("PATH", str(tmp_path))
    return lambda name, body: script(tmp_path, name, body=body)


@pytest.fixture
def ghost_engine() -> Iterator[type[Engine]]:
    """A registered engine whose module never exists, unenrolled again on teardown.

    The cleanup keeps the registry enumeration tests (`Engine.supporting`)
    order-independent: no other test ever sees the ghost.
    """

    class GhostEngine(Engine):
        name = "ghost"
        module: ClassVar[str] = "nosuch_module_anywhere"
        distribution: ClassVar[str] = "nosuch-dist"
        capability: ClassVar[Capability] = Capability.SEARCH

        def execute(self, payload: str) -> str:
            return payload

    yield GhostEngine
    Engine.registry_entries.remove(GhostEngine)
