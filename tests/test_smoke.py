import json
import sys
from pathlib import Path

import pytest

import atpx
from atpx import cli
from atpx.workspace import Workspace

from .conftest import FakeRunner


def test_every_self_reference_derives_from_the_package_name() -> None:
    assert atpx.NAME == "atpx"
    derived = f"{atpx.NAME}.toml"
    assert derived == atpx.CONFIG
    assert callable(atpx.workspace)


def test_cli_prints_a_sync_verb_as_json(
    ws: tuple[Workspace, FakeRunner], capsys: pytest.CaptureFixture[str]
) -> None:
    space, _ = ws
    cli.build(space)(["status"])
    assert json.loads(capsys.readouterr().out) == {
        "open": ["Demo Node"],
        "in_progress": ["Blocked"],
        "sketched": ["Dep"],
    }


def test_cli_runs_an_async_verb_on_its_own_loop(
    ws: tuple[Workspace, FakeRunner], capsys: pytest.CaptureFixture[str]
) -> None:
    space, runner = ws
    cli.build(space)(["check", "demo", "ok", "--seed", "7"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["claim"] == "demo/ok" and certificate["seed"] == 7
    assert runner.calls == [["python", "research/math/demo/checks.py", "ok"]]


def test_cli_keeps_underscored_command_names_and_prints_markdown_as_is(
    ws: tuple[Workspace, FakeRunner], capsys: pytest.CaptureFixture[str]
) -> None:
    space, _ = ws
    app = cli.build(space)
    app(["cross_check", "evaluate", "sqrt(2)"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["result"]["agree"] is True
    app(["lean_candidates"])
    table = capsys.readouterr().out
    assert table.splitlines()[0] == "| node | backlinks | length | score |"


def test_cli_help_lists_the_verbs_and_prints_no_result(
    ws: tuple[Workspace, FakeRunner], capsys: pytest.CaptureFixture[str]
) -> None:
    space, _ = ws
    cli.build(space)(["--help"])
    out = capsys.readouterr().out
    assert "cross_check" in out and "judge_brief" in out
    assert "null" not in out


def test_main_discovers_the_workspace_from_the_cwd(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", [atpx.NAME, "graph"])
    cli.main()
    frontier = json.loads(capsys.readouterr().out)
    assert [node["node"] for node in frontier] == ["Demo Node"]
