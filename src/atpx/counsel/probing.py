import json
from pathlib import Path

from pydantic import JsonValue

from ..core.certificate import Certificate
from ..models.consultation import Consultation
from ..support.runtime import drive
from .records.workbench import Workbench

_TACTICS = "TACTICS.md"
_MEASURED_LINES = 3
_TAIL = 2000
_PROBE_TIMEOUT = 120.0


def cap(timeout: float | None = None) -> float:
    """The effective probe wall-clock cap in seconds, the measured default when unset.

    timeout: an explicit cap, None for the 120s default that fits quick probes.
    """
    return _PROBE_TIMEOUT if timeout is None else timeout


def staged(
    space: Workbench,
    path: Path,
    probe: str,
    *,
    name: str,
    claim: str,
    timeout: float = _PROBE_TIMEOUT,
) -> Certificate:
    """Persist one probe to disk and run it as a real claim, returning its certificate.

    space: the workspace the claim runs in.
    path: where the probe source lands inside the blueprint.
    probe: the probe source to persist.
    name: the blueprint directory name the claim runs under.
    claim: the claim name the certificate stamps.
    timeout: hard wall-clock cap in seconds, the measured probe timeout by default.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(probe)
    relative = path.relative_to(space.root).as_posix()
    return drive(space.run(name, claim, "python", relative, timeout=timeout))


def measured(stdout: str) -> list[str]:
    """The measured lines of a probe's output, a line holding `=` and a digit."""
    return [line for line in stdout.splitlines() if "=" in line and any(c.isdigit() for c in line)]


def gate(source: str, *, stdout: str) -> str | None:
    """The validity gate on a passing probe, the violation message or None when clean.

    Measured rules that exit 0 must satisfy to count: the source calls
    `sys.exit` explicitly, and the output shows at least three measured lines.

    source: the probe source code.
    stdout: the probe's captured output.
    """
    if "sys.exit" not in source:
        return "the probe never calls sys.exit, so exit 0 certifies nothing"
    if len(measured(stdout)) < _MEASURED_LINES:
        return (
            f"only {len(measured(stdout))} measured lines printed, at least {_MEASURED_LINES} "
            "`name=value` case lines are required"
        )
    return None


def tactics(blueprints: Path) -> str:
    """The shared probe-writing tactics, empty when the blueprints root carries none.

    blueprints: the blueprints root directory holding `TACTICS.md`.
    """
    try:
        return (blueprints / _TACTICS).read_text()
    except FileNotFoundError:
        return ""


def charge(contract: str, *, lessons: str) -> str:
    """The system message: the role contract plus the tactics file when present."""
    return f"{contract}\n\n{lessons}".rstrip()


def transcript(certificate: Certificate) -> str:
    """The probe output the gate reads, the raw text when the certificate kept it."""
    result = certificate.result
    if isinstance(result, dict) and isinstance(output := result.get("output"), str):
        return output
    return json.dumps(result)


def tail(text: str, limit: int = _TAIL) -> str:
    """The last `limit` characters, where the traceback or case summary lives."""
    return text[-limit:]


def fielded(consultation: Consultation, field: str) -> str:
    """One named string field of a JSON reply, empty when missing or not parseable."""
    try:
        data = json.loads(consultation.content)
    except json.JSONDecodeError:
        return ""
    value = data.get(field) if isinstance(data, dict) else None
    return value if isinstance(value, str) else ""


def judged(source: str, certificate: Certificate) -> str:
    """Why one probe run does not count, empty when it exits 0 through a clean gate."""
    output = transcript(certificate)
    if certificate.exit_status != 0:
        return f"exit {certificate.exit_status}: {tail(output)}"
    return gate(source, stdout=output) or ""


def recorded(directory: Path, name: str, entry: dict[str, JsonValue]) -> None:
    """Append one JSON line to `attempts/<name>.jsonl`, the append-only episode record.

    directory: the blueprint directory the episode ran in.
    name: the claim name keying the record file.
    entry: the round's consultations and outcome.
    """
    path = directory / "attempts" / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(entry) + "\n")
