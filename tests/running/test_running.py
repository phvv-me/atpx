import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import Blueprint, EvidenceStore, Workspace
from atpx.running import ProcessRunner, Running, clipped, payload, stale_claims
from atpx.support import drive

from ..support import FakeRunner, SleepyRunner, stamped


def test_payload_takes_the_last_json_line() -> None:
    output = 'noise\n{"broken": \n{"margin": 0.25}\ntrailing prose'
    assert payload(output) == {"margin": 0.25}
    assert payload("no json at all") == {"output": "no json at all"}


def test_payload_falls_back_when_the_only_json_line_is_broken() -> None:
    assert payload('{"broken":') == {"output": '{"broken":'}


def test_payload_reads_indented_json() -> None:
    assert payload('prose\n   {"a": 1}') == {"a": 1}


def test_payload_takes_the_last_value_of_an_interleaved_line() -> None:
    assert payload('{"a": 1}{"b": 2}') == {"b": 2}
    assert payload('{"a": 1} {"b": 2}') == {"b": 2}
    assert payload('[1, 2] {"b": 2}\tnot json trailer') == {"b": 2}


@given(st.dictionaries(st.text(), st.integers(), max_size=3), st.text())
def test_payload_recovers_the_last_printed_object(result: dict[str, int], noise: str) -> None:
    assert payload(noise + "\n" + json.dumps(result) + "\n") == result


@given(st.text(min_size=0, max_size=200))
def test_clipped_keeps_short_text_verbatim(text: str) -> None:
    assert clipped(text, limit=200) == text


@given(st.integers(min_value=10, max_value=100))
def test_clipped_keeps_both_ends_around_the_elision_marker(limit: int) -> None:
    head, tail = "H" * limit, "T" * limit
    text = head + "M" * (3 * limit) + tail
    kept = clipped(text, limit=limit)
    assert kept.startswith("H" * (limit // 2))
    assert kept.endswith("T" * (limit // 2))
    assert f"[{len(text) - limit} characters elided]" in kept


def test_payload_fallback_keeps_the_head_of_long_output() -> None:
    long_output = "first case line\n" + ("x" * 20_000) + "\nlast case line"
    fallback = payload(long_output)
    assert isinstance(fallback, dict)
    kept = fallback["output"]
    assert isinstance(kept, str)
    assert kept.startswith("first case line")
    assert kept.endswith("last case line")


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
