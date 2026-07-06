import json
import sys
from pathlib import Path

import pytest

import atpx
from atpx import cli
from atpx.workspace import Workspace
from atpx.zettel import Vault

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


def test_cli_run_passes_hyphenated_command_tokens_verbatim(
    ws: tuple[Workspace, FakeRunner], capsys: pytest.CaptureFixture[str]
) -> None:
    space, runner = ws
    cli.build(space)(["run", "demo", "probe", "python", "-c", "print(1)"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["claim"] == "demo/probe"
    assert runner.calls == [["python", "-c", "print(1)"]]


def test_cli_run_options_before_the_command_still_parse(
    ws: tuple[Workspace, FakeRunner], capsys: pytest.CaptureFixture[str]
) -> None:
    space, runner = ws
    cli.build(space)(["run", "demo", "seeded", "--seed", "7", "python", "-c", "print(1)"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["seed"] == 7
    assert runner.calls == [["python", "-c", "print(1)"]]


def test_cli_keeps_underscored_command_names_and_prints_markdown_as_is(
    ws: tuple[Workspace, FakeRunner], capsys: pytest.CaptureFixture[str]
) -> None:
    space, _ = ws
    app = cli.build(space)
    app(["judge_brief", "demo"])
    text = capsys.readouterr().out
    assert text.startswith("# Judge brief for Demo Node")
    app(["doctor"])
    report = json.loads(capsys.readouterr().out)
    assert report["invalid_statuses"] == {}


def test_cli_help_lists_the_verbs_and_prints_no_result(
    ws: tuple[Workspace, FakeRunner], capsys: pytest.CaptureFixture[str]
) -> None:
    space, _ = ws
    cli.build(space)(["--help"])
    out = capsys.readouterr().out
    assert "settle" in out and "doctor" in out and "judge_brief" in out
    assert "null" not in out


def test_main_discovers_the_workspace_from_the_cwd(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", [atpx.NAME, "graph"])
    cli.main()
    frontier = json.loads(capsys.readouterr().out)
    assert [node["node"] for node in frontier] == ["Demo Node"]


@pytest.mark.parametrize(
    ("argv", "fragment"),
    [
        (["recall", "q", "--sources", "nosuch"], "no implementation with name='nosuch'"),
        (["brief", "ghost"], "no blueprint 'ghost'"),
        (["check", "demo", "ghost"], "no claim 'ghost'"),
        (["log", "Nowhere", "refuter", "t", "msg"], "no note named 'Nowhere'"),
        (["log", "Demo Node", "the refuter", "t", "msg"], "pattern"),
        (["run", "a/b", "ok", "echo", "hi"], "single path segments"),
        (["settle", "Demo Node", "immaculate"], "not a valid Status"),
        (["settle", "Demo Node", "sketched"], "judgment"),
    ],
)
def test_main_turns_a_domain_error_into_one_clean_line(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    fragment: str,
) -> None:
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", [atpx.NAME, *argv])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Traceback" not in captured.err
    assert captured.err.startswith("error: ") and fragment in captured.err


def test_display_prints_nothing_for_no_result(capsys: pytest.CaptureFixture[str]) -> None:
    cli.display(None)
    assert capsys.readouterr().out == ""


def test_main_lets_a_genuine_programming_fault_surface(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: Vault) -> list[dict[str, str | dict[str, str]]]:
        raise TypeError("not a domain error")

    monkeypatch.chdir(root)
    monkeypatch.setattr(Vault, "frontier", boom)
    monkeypatch.setattr(sys, "argv", [atpx.NAME, "graph"])
    with pytest.raises(TypeError, match="not a domain error"):
        cli.main()
