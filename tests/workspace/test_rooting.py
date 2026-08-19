from pathlib import Path

import pytest

from atpx import workspace
from atpx.workspace import find_root, find_roots


def test_find_root_walks_past_blueprint_manifests(root: Path) -> None:
    inner = root / "research" / "math" / "demo"
    assert find_root(inner) == root


def test_find_root_fails_loudly_outside_a_workspace(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no atpx.toml"):
        find_root(tmp_path)


def test_find_root_honors_the_environment_override(
    root: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("ATPX_ROOT", str(root))
    assert find_root() == root
    assert workspace().root == root


def test_find_root_rejects_a_pinned_non_workspace(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path_factory.mktemp("not-a-workspace")
    monkeypatch.setenv("ATPX_ROOT", str(elsewhere))
    with pytest.raises(FileNotFoundError, match="ATPX_ROOT"):
        find_root()


def test_an_explicit_start_beats_the_environment_override(
    root: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATPX_ROOT", str(root))
    with pytest.raises(FileNotFoundError, match="no atpx.toml"):
        find_root(tmp_path_factory.mktemp("named-start"))


def test_workspace_discovers_root_from_the_cwd(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(root / "research")
    assert workspace().root == root


def test_find_roots_answers_for_the_root_and_every_workspace_under_it(root: Path) -> None:
    """The whole-monorepo reading, so one lint covers every project without pinning each."""
    inner = root / "research" / "thoughtlens"
    inner.mkdir(parents=True)
    (inner / "atpx.toml").write_text('[workspace]\nblueprints = "math"\n')
    assert find_roots(root) == [root, inner]


def test_find_roots_never_mistakes_a_blueprint_manifest_for_a_workspace(root: Path) -> None:
    assert find_roots(root) == [root]
