import json
import sys
from pathlib import Path

import pytest

import atpx
from atpx import NodeStore, Workspace
from atpx.cli import __main__, build, display, main
from atpx.cli.app import reported

from ..support import FakeRunner, node_text, planted


def test_every_self_reference_derives_from_the_package_name() -> None:
    assert atpx.NAME == "atpx"
    derived = f"{atpx.NAME}.toml"
    assert derived == atpx.CONFIG
    assert callable(atpx.workspace)


def test_module_getattr_resolves_name_and_config_and_refuses_anything_else() -> None:
    assert atpx.__getattr__("NAME") == atpx.NAME
    assert atpx.__getattr__("CONFIG") == atpx.CONFIG
    with pytest.raises(AttributeError, match="ghost"):
        atpx.__getattr__("ghost")


def test_cli_prints_a_sync_verb_as_json(
    space: Workspace, capsys: pytest.CaptureFixture[str]
) -> None:
    build(space)(["status"])
    assert json.loads(capsys.readouterr().out) == {
        "open": ["demo"],
        "in_progress": ["blocked"],
        "sketched": ["dep"],
    }


def test_cli_runs_an_async_verb_on_its_own_loop(
    space: Workspace, runner: FakeRunner, capsys: pytest.CaptureFixture[str]
) -> None:
    build(space)(["check", "demo", "ok", "--seed", "7"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["claim"] == "demo/ok" and certificate["seed"] == 7
    assert runner.calls == [["python", f"{space.blueprints / 'demo'}/checks.py", "ok"]]


def test_cli_run_passes_hyphenated_command_tokens_verbatim(
    space: Workspace, runner: FakeRunner, capsys: pytest.CaptureFixture[str]
) -> None:
    build(space)(["run", "demo", "probe", "python", "-c", "print(1)"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["claim"] == "demo/probe"
    assert runner.calls == [["python", "-c", "print(1)"]]


def test_cli_run_options_before_the_command_still_parse(
    space: Workspace, runner: FakeRunner, capsys: pytest.CaptureFixture[str]
) -> None:
    build(space)(["run", "demo", "seeded", "--seed", "7", "python", "-c", "print(1)"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["seed"] == 7
    assert runner.calls == [["python", "-c", "print(1)"]]


def test_cli_keeps_underscored_command_names_and_prints_markdown_as_is(
    space: Workspace, capsys: pytest.CaptureFixture[str]
) -> None:
    build(space)(["judge_brief", "demo"])
    assert capsys.readouterr().out.startswith("# Judge brief for demo")


def test_cli_prints_the_doctor_certificate_and_exits_with_its_status(
    space: Workspace, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failing certificate gates a shell pipeline without anyone parsing its JSON."""
    with pytest.raises(SystemExit) as exit_info:
        build(space)(["doctor"])
    certificate = json.loads(capsys.readouterr().out)
    assert exit_info.value.code == certificate["exit_status"] == 1
    report = certificate["result"]["workspaces"]["."]
    assert report["unevidenced_claims"] == {"demo": ["gpu", "ok"]}


def test_cli_leaves_a_clean_certificate_alone(
    space: Workspace, capsys: pytest.CaptureFixture[str]
) -> None:
    build(space)(["run", "demo", "probe", "true"])
    assert json.loads(capsys.readouterr().out)["exit_status"] == 0


def test_reported_prints_plain_data_without_touching_the_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reported({"open": ["demo"]})
    assert json.loads(capsys.readouterr().out) == {"open": ["demo"]}


def test_cli_help_answers_from_a_directory_holding_no_workspace(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Describing the tool never opens a workspace, so the verbs are discoverable anywhere."""
    monkeypatch.chdir(tmp_path_factory.mktemp("bare"))
    monkeypatch.setattr(sys, "argv", [atpx.NAME, "--help"])
    main()
    out = capsys.readouterr().out
    assert "doctor" in out and "lab" in out and "--project" in out


def test_cli_project_flag_pins_a_nested_workspace(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The answer to a launcher that normalizes the working directory to a monorepo root."""
    inner = root / "research" / "thoughtlens"
    (inner / "math").mkdir(parents=True)
    (inner / "atpx.toml").write_text('[workspace]\nblueprints = "math"\n')
    planted(inner / "math", "lensed", text=node_text("sketched", title="Lensed"))
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", [atpx.NAME, "--project", str(inner), "status"])
    main()
    assert json.loads(capsys.readouterr().out) == {"sketched": ["lensed"]}


def test_cli_help_lists_the_verbs_and_prints_no_result(
    space: Workspace, capsys: pytest.CaptureFixture[str]
) -> None:
    build(space)(["--help"])
    out = capsys.readouterr().out
    assert "settle" in out and "doctor" in out and "judge_brief" in out and "adopt" in out
    assert "note" in out and "design" in out
    assert "null" not in out


def test_main_discovers_the_workspace_from_the_cwd(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", [atpx.NAME, "graph"])
    main()
    frontier = json.loads(capsys.readouterr().out)
    assert [node["node"] for node in frontier] == ["demo"]


@pytest.mark.parametrize(
    ("argv", "fragment"),
    [
        (["recall", "q", "--sources", "nosuch"], "no implementation with name='nosuch'"),
        (["brief", "ghost"], "no blueprint 'ghost'"),
        (["check", "demo", "ghost"], "no claim 'ghost'"),
        (["log", "nowhere", "refuter", "t", "msg"], "no node named 'nowhere'"),
        (["log", "demo", "the refuter", "t", "msg"], "pattern"),
        (["run", "a/b", "ok", "echo", "hi"], "single path segments"),
        (["adopt", "ghost", "--source", "nowhere/x.md"], "no note at"),
        (["note", "nowhere", "a bullet"], "no node named 'nowhere'"),
        (["design", "nowhere"], "no node named 'nowhere'"),
        (["settle", "demo", "immaculate"], "not a valid Status"),
        (["settle", "demo", "sketched"], "judgment"),
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
        main()
    assert exit_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Traceback" not in captured.err
    assert captured.err.startswith("error: ") and fragment in captured.err


def test_dunder_main_re_exports_the_same_main_as_the_package() -> None:
    assert __main__.main is main


def test_display_prints_nothing_for_no_result(capsys: pytest.CaptureFixture[str]) -> None:
    display(None)
    assert capsys.readouterr().out == ""


def test_main_lets_a_genuine_programming_fault_surface(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: NodeStore) -> list[dict[str, str | dict[str, str]]]:
        raise TypeError("not a domain error")

    monkeypatch.chdir(root)
    monkeypatch.setattr(NodeStore, "frontier", boom)
    monkeypatch.setattr(sys, "argv", [atpx.NAME, "graph"])
    with pytest.raises(TypeError, match="not a domain error"):
        main()
