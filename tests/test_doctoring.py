import json
from pathlib import Path

from atpx.workspace import Workspace

from .conftest import FakeRunner, zettel_text


def test_doctor_reports_instead_of_crashing(root: Path) -> None:
    vault = root / "vault" / "Zettelkasten"
    (vault / "Odd.md").write_text(
        zettel_text("open", title="Odd", blueprint="research/math/ghost/").replace(
            "status: open", "status: closed"
        )
    )
    stray_home = root / "research" / "math" / "demo" / "evidence"
    stray_home.mkdir(parents=True, exist_ok=True)
    (stray_home / "routing_data.json").write_text('{"tokens": 684}')
    (root / "research" / "math" / "orphan").mkdir()
    (root / "research" / "math" / "notes.txt").write_text("not a blueprint\n")
    space = Workspace(root, runner=FakeRunner())
    report = json.loads(json.dumps(space.doctor()))
    assert report["invalid_statuses"] == {"Odd": "closed"}
    assert report["stray_evidence"] == {"demo": ["research/math/demo/evidence/routing_data.json"]}
    assert "orphan" in report["unmanifested_blueprints"]
    assert "notes.txt" not in report["unmanifested_blueprints"]
    assert report["dangling_blueprints"] == {"Odd": "research/math/ghost/"}
    assert space.status()["invalid"] == ["Odd (closed)"]
    assert space.sync.check("demo", "ok").ok


def test_doctor_is_quiet_on_a_healthy_workspace(root: Path) -> None:
    space = Workspace(root, runner=FakeRunner())
    assert space.doctor() == {
        "invalid_statuses": {},
        "stray_evidence": {},
        "unmanifested_blueprints": [],
        "dangling_blueprints": {},
    }
