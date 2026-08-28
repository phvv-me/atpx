import asyncio
import json
import tempfile
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import Blueprint, EvidenceStore, Workspace
from atpx.running import Capture, ProcessRunner, Running, clipped, stale_claims
from atpx.support import drive

from ..support import FakeRunner, SleepyRunner, stamped


@pytest.fixture
def capture(tmp_path: Path) -> Capture:
    """A capture externalizing oversized output under a throwaway blueprint directory."""
    return Capture(tmp_path)


def test_payload_takes_the_last_json_line(capture: Capture) -> None:
    output = 'noise\n{"broken": \n{"margin": 0.25}\ntrailing prose'
    assert capture.payload(output) == {"margin": 0.25}
    assert capture.payload("no json at all") == {"output": "no json at all"}


def test_payload_falls_back_when_the_only_json_line_is_broken(capture: Capture) -> None:
    assert capture.payload('{"broken":') == {"output": '{"broken":'}


def test_payload_reads_indented_json(capture: Capture) -> None:
    assert capture.payload('prose\n   {"a": 1}') == {"a": 1}


def test_payload_takes_the_last_value_of_an_interleaved_line(capture: Capture) -> None:
    assert capture.payload('{"a": 1}{"b": 2}') == {"b": 2}
    assert capture.payload('{"a": 1} {"b": 2}') == {"b": 2}
    assert capture.payload('[1, 2] {"b": 2}\tnot json trailer') == {"b": 2}


@given(st.dictionaries(st.text(), st.integers(), max_size=3), st.text())
def test_payload_recovers_the_last_printed_object(result: dict[str, int], noise: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        line = json.dumps(result)
        assert Capture(Path(directory)).payload(f"{noise}\n{line}\n") == result


@given(st.text(min_size=0, max_size=200))
def test_clipped_keeps_short_text_verbatim(text: str) -> None:
    assert clipped(text, limit=200) == text


@given(st.integers(min_value=4, max_value=60))
def test_clipped_keeps_only_whole_lines_from_both_ends(count: int) -> None:
    """The elision boundary is a line break, so a kept line is never half a line."""
    lines = [f"case={index} measured={index}.5 target={index}.4" for index in range(count)]
    text = "\n".join(lines)
    kept = clipped(text, limit=len(text) // 2)
    body = kept.splitlines()
    assert body[0] == lines[0] and body[-1] == lines[-1]
    assert [line for line in body if line not in lines] == [
        line for line in body if line.startswith("... [")
    ]


def test_clipped_drops_a_single_oversized_line_whole() -> None:
    """One long line has no safe cut inside it, so the marker stands alone."""
    assert clipped("x" * 500, limit=100) == "... [500 characters elided] ..."


def test_oversized_output_is_written_whole_beside_the_ledger(capture: Capture) -> None:
    text = "\n".join(f"case={index} measured=1.0" for index in range(2_000))
    recorded = capture.recorded(text)
    elided = recorded["elided"]
    assert isinstance(elided, dict)
    assert elided["characters"] == len(text)
    assert elided["digest"] == f"sha256:{sha256(text.encode()).hexdigest()}"
    assert (capture.directory / str(elided["path"])).read_text() == text
    assert str(elided["path"]) in str(recorded["output"])


def test_an_oversized_json_document_is_externalized_rather_than_cut(capture: Capture) -> None:
    """The defect on disk: a JSON blob too long to store, elided into a middle nothing reads.

    It is now written out whole and what the certificate keeps holds only whole
    lines of it, so nothing ever reads back a JSON document cut through the middle.
    """
    cases = [{"case": index, "measured": index * 1.5} for index in range(2_000)]
    document = json.dumps({"cases": cases}, indent=2)
    result = capture.payload(document)
    assert isinstance(result, dict)
    elided = result["elided"]
    assert isinstance(elided, dict)
    assert (capture.directory / str(elided["path"])).read_text() == document
    lines = document.splitlines()
    kept = [line for line in str(result["output"]).splitlines() if not line.startswith("... [")]
    assert all(line in lines for line in kept)


def test_bounded_stamps_exit_124_on_expiry(tmp_path: Path) -> None:
    running = Running(SleepyRunner(), tmp_path)
    exit_status, output = drive(running.bounded(["sleep"], 0.01))
    assert exit_status == 124 and "timed out" in output


def test_process_runner_runs_the_bare_command_from_the_root(
    root: Path, on_path: Callable[[str, str], Path]
) -> None:
    on_path("probe", 'echo "probe ran: $@ in $PWD"')
    exit_status, output = drive(ProcessRunner(root=root)(["probe", "checks.py"]))
    assert exit_status == 0 and f"probe ran: checks.py in {root}" in output


def test_process_runner_hands_the_command_to_the_declared_launcher(
    root: Path, on_path: Callable[[str, str], Path]
) -> None:
    on_path("launcher", 'echo "launched: $@"')
    runner = ProcessRunner(root=root, launcher=["launcher", "run", "--"])
    exit_status, output = drive(runner(["python", "checks.py"]))
    assert exit_status == 0 and "launched: run -- python checks.py" in output


def test_process_runner_kills_a_cancelled_child(
    root: Path, on_path: Callable[[str, str], Path]
) -> None:
    on_path("probe", "while :; do :; done")
    with pytest.raises(TimeoutError):
        drive(asyncio.wait_for(ProcessRunner(root=root)(["probe"]), timeout=0.05))


def test_swept_returns_one_certificate_per_claim(root: Path) -> None:
    running = Running(FakeRunner(), root)
    blueprint = Blueprint.load(root / "research" / "math" / "demo")
    fresh = drive(running.swept(blueprint, ["ok", "gpu"]))
    assert set(fresh) == {"ok", "gpu"}
    assert all(certificate.ok for certificate in fresh.values())


def test_stale_claims_judge_only_the_latest_certificate(root: Path) -> None:
    store = EvidenceStore(root / "research" / "math" / "demo")
    old = stamped("demo/ok").model_copy(update={"timestamp": "2026-06-01T00:00:00+00:00"})
    store.append(old)
    space = Workspace(root, runner=FakeRunner())
    blueprint = space.register("demo", claim="ok")
    assert stale_claims(blueprint, "0000000") == set()
    assert stale_claims(blueprint, "1111111") == {"ok"}


def test_stale_claims_keep_the_newest_of_two_certificates(root: Path) -> None:
    store = EvidenceStore(root / "research" / "math" / "demo")
    newer = stamped("demo/ok").model_copy(update={"timestamp": "2026-06-12T00:00:00+00:00"})
    older = stamped("demo/ok").model_copy(
        update={"timestamp": "2026-06-01T00:00:00+00:00", "git_rev": "9999999"}
    )
    store.append(newer)
    store.append(older)
    space = Workspace(root, runner=FakeRunner())
    blueprint = space.register("demo", claim="ok")
    assert stale_claims(blueprint, "0000000") == set()


def test_stale_claims_trust_any_host_at_the_current_revision(root: Path) -> None:
    """A later run on another host at another revision must not shadow fresh local evidence."""
    directory = root / "research" / "math" / "demo"
    EvidenceStore(directory).append(stamped("demo/ok"))
    foreign = stamped("demo/ok").model_copy(
        update={
            "hostname": "elsewhere",
            "timestamp": "2099-01-01T00:00:00+00:00",
            "git_rev": "9999999",
        }
    )
    EvidenceStore(directory, hostname="elsewhere").append(foreign)
    blueprint = Blueprint.load(directory)
    assert stale_claims(blueprint, "0000000") == set()
    assert stale_claims(blueprint, "1111111") == {"ok"}


def test_stale_claims_skip_certificates_outside_the_slug_convention(root: Path) -> None:
    EvidenceStore(root / "research" / "math" / "demo").append(stamped("fit data.csv"))
    blueprint = Blueprint.load(root / "research" / "math" / "demo")
    assert stale_claims(blueprint, "1111111") == set()
