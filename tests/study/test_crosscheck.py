from pathlib import Path

from atpx import EvidenceStore, Workspace
from atpx.study.crosscheck import DeviceComparison

from ..support import FakeRunner, result_of, stamped

_MATH = "research/math"


def measured(root: Path, claim: str, *, device: str, exit_status: int = 0) -> None:
    """Record one certificate for `claim` as though `device` had produced it."""
    certificate = stamped(claim, exit_status=exit_status).model_copy(update={"device": device})
    EvidenceStore(root / _MATH / claim.partition("/")[0]).append(certificate)


def test_a_family_with_no_evidence_compares_to_an_empty_table(root: Path) -> None:
    comparison = DeviceComparison(Workspace(root, runner=FakeRunner()).nodes, "demo")
    assert comparison.devices == [] and comparison.addresses == []


def test_each_address_reads_its_verdict_per_device_side_by_side(root: Path) -> None:
    measured(root, "demo/ok", device="Linux-x86_64")
    measured(root, "demo/ok", device="Linux-aarch64")
    measured(root, "demo/gpu", device="Linux-x86_64")
    comparison = DeviceComparison(Workspace(root, runner=FakeRunner()).nodes, "demo")
    assert comparison.devices == ["Linux-aarch64", "Linux-x86_64"]
    assert comparison.table() == (
        "| Address | Linux-aarch64 | Linux-x86_64 |\n"
        "| --- | --- | --- |\n"
        "| demo/gpu |  | passed |\n"
        "| demo/ok | passed | passed |"
    )
    assert comparison.gaps("Linux-aarch64") == ["demo/gpu"]
    assert comparison.gaps("Linux-x86_64") == []


def test_a_family_prefix_selects_the_nodes_it_names(root: Path) -> None:
    measured(root, "demo/ok", device="Linux-x86_64")
    measured(root, "dep/ok", device="Linux-x86_64")
    nodes = Workspace(root, runner=FakeRunner()).nodes
    assert DeviceComparison(nodes, "dep").addresses == ["dep/ok"]
    assert DeviceComparison(nodes).addresses == ["demo/ok", "dep/ok"]


def test_the_newest_certificate_per_device_is_the_one_compared(root: Path) -> None:
    measured(root, "demo/ok", device="Linux-x86_64", exit_status=1)
    later = stamped("demo/ok").model_copy(
        update={"device": "Linux-x86_64", "timestamp": "2099-01-01T00:00:00Z"}
    )
    EvidenceStore(root / _MATH / "demo").append(later)
    comparison = DeviceComparison(Workspace(root, runner=FakeRunner()).nodes, "demo")
    assert comparison.table().endswith("| demo/ok | passed |")


def test_two_devices_answering_one_address_differently_fails_the_command(root: Path) -> None:
    measured(root, "demo/ok", device="Linux-x86_64")
    measured(root, "demo/ok", device="Linux-aarch64", exit_status=1)
    certificate = Workspace(root, runner=FakeRunner()).compare("demo")
    assert not certificate.ok
    assert result_of(certificate)["disagreements"] == ["demo/ok"]


def test_a_family_no_device_contradicts_passes(root: Path) -> None:
    """A card that has not reached an address yet is a gap, never a disagreement."""
    measured(root, "demo/ok", device="Linux-x86_64")
    measured(root, "demo/gpu", device="Linux-aarch64")
    certificate = Workspace(root, runner=FakeRunner()).compare("demo")
    assert certificate.ok
    assert result_of(certificate)["gaps"] == {
        "Linux-aarch64": ["demo/ok"],
        "Linux-x86_64": ["demo/gpu"],
    }


def test_a_second_certificate_at_the_same_instant_never_displaces_the_first(root: Path) -> None:
    """Newest wins, and same-instant is not newer, so a replay cannot rewrite a verdict."""
    measured(root, "demo/ok", device="Linux-x86_64", exit_status=1)
    measured(root, "demo/ok", device="Linux-x86_64")
    comparison = DeviceComparison(Workspace(root, runner=FakeRunner()).nodes, "demo")
    assert comparison.table().endswith("| demo/ok | failed |")
