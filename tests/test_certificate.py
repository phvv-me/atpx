import json
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from plumbum import local

from atpx.certificate import Certificate, git_revision, short_hostname

from .conftest import stamped


@given(st.integers(min_value=0, max_value=255))
def test_ok_means_exit_zero(exit_status: int) -> None:
    assert stamped(exit_status=exit_status).ok == (exit_status == 0)


def test_stamp_captures_full_provenance() -> None:
    certificate = Certificate.stamp(claim="demo/ok", result=1, engine="e", engine_version="0")
    assert certificate.hostname == short_hostname()
    assert "-" in certificate.device
    assert certificate.timestamp.endswith("+00:00")
    assert certificate.seed is None
    assert json.loads(str(certificate))["claim"] == "demo/ok"


def test_stamp_records_a_seed() -> None:
    certificate = Certificate.stamp(claim="c", result=1, engine="e", engine_version="0", seed=42)
    assert certificate.seed == 42


def test_git_revision_outside_a_repository_is_unknown(tmp_path: Path) -> None:
    assert git_revision(tmp_path) == "unknown"


def test_git_revision_tracks_commits_and_dirt(tmp_path: Path) -> None:
    git = local["git"]["-C", str(tmp_path)]
    git("init", "-q")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x")
    clean = git_revision(tmp_path)
    assert clean != "unknown" and "+dirty" not in clean
    (tmp_path / "scratch.txt").write_text("dirt")
    assert git_revision(tmp_path) == f"{clean}+dirty"
