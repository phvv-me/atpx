from pathlib import Path

import pytest

import atpx
from atpx import cli


def test_every_self_reference_derives_from_the_package_name() -> None:
    assert atpx.NAME == "atpx"
    derived = f"{atpx.NAME}.toml"
    assert derived == atpx.CONFIG
    assert callable(atpx.workspace)


def test_cli_fires_the_workspace_under_the_package_name(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(root)
    fired: list[tuple[object, str]] = []
    monkeypatch.setattr(cli.fire, "Fire", lambda component, name: fired.append((component, name)))
    cli.main()
    component, name = fired[0]
    assert isinstance(component, atpx.Workspace)
    assert component.root == root
    assert name == atpx.NAME
