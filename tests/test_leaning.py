from pathlib import Path

from atpx.workspace import Workspace

from .conftest import FakeRunner, result_of


def test_lean_ingests_a_build_as_evidence(root: Path) -> None:
    space = Workspace(root, runner=FakeRunner(output="warning: declaration uses 'sorry'\n"))
    certificate = space.sync.lean("demo", "Compression")
    assert certificate.exit_status == 1 and result_of(certificate)["sorries"] == 1
    assert certificate.claim == "demo/lean Compression"
    clean = Workspace(root, runner=FakeRunner(output="Build completed successfully.\n"))
    verdict = clean.sync.lean("demo")
    assert verdict.ok and result_of(verdict)["flagged"] == []


def test_lean_flags_risky_axioms_even_on_a_passing_build(root: Path) -> None:
    output = "axioms: [propext, Lean.ofReduceBool, Lean.trustCompiler]\nnative_decide replay\n"
    space = Workspace(root, runner=FakeRunner(output=output))
    certificate = space.sync.lean("demo")
    assert certificate.exit_status == 1
    assert result_of(certificate)["sorries"] == 0
    assert result_of(certificate)["flagged"] == [
        "ofReduceBool",
        "Lean.trustCompiler",
        "native_decide",
    ]


def test_lean_keeps_the_build_exit_status(root: Path) -> None:
    space = Workspace(root, runner=FakeRunner(exit_status=3, output="compiler crashed\n"))
    certificate = space.sync.lean("demo")
    assert certificate.exit_status == 3


def test_lean_registers_a_missing_blueprint(root: Path) -> None:
    space = Workspace(root, runner=FakeRunner(output="ok\n"))
    certificate = space.sync.lean("greenfield")
    assert certificate.ok
    assert (space.blueprints / "greenfield" / "atpx.toml").exists()


def test_lean_passes_the_target_to_the_task(root: Path) -> None:
    runner = FakeRunner(output="ok\n")
    space = Workspace(root, runner=runner)
    space.sync.lean("demo", "Compression.Basic")
    assert runner.calls == [["lean-build", "Compression.Basic"]]
