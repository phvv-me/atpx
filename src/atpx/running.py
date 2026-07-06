import asyncio
import json
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Protocol

from pydantic import JsonValue

from . import NAME
from .blueprint import Blueprint, satisfied
from .certificate import Certificate
from .evidence import EvidenceStore

RERUN_LIMIT = 4


class CommandRunner(Protocol):
    """How claim and build commands execute."""

    async def __call__(self, argv: list[str]) -> tuple[int, str]: ...


class ChefeRunner:
    """Runs commands inside the chefe-managed environment from the workspace root."""

    def __init__(self, root: Path) -> None:
        """root: the workspace root chefe runs from."""
        self.root = root

    async def __call__(self, argv: list[str]) -> tuple[int, str]:
        """Execute `chefe run <argv>` from the root and return (exit status, combined output)."""
        process = await asyncio.create_subprocess_exec(
            "chefe",
            "run",
            *argv,
            cwd=self.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await process.communicate()
        return process.returncode or 0, stdout.decode()


class Running:
    """Capture-first execution: run commands through one runner, stamp certificates.

    The (runner, root) pair every run needs travels here once, so the verbs
    above read as their algorithm: attempt a claim, sweep several, or bound an
    arbitrary command under the hard wall-clock cap.
    """

    def __init__(self, runner: CommandRunner, root: Path) -> None:
        """runner: the command executor.

        root: the workspace root commands run from and certificates stamp.
        """
        self.runner = runner
        self.root = root

    async def bounded(self, argv: list[str], timeout: float | None) -> tuple[int, str]:
        """Run one command under a hard wall-clock cap.

        Expiry returns exit 124 in the shell timeout convention instead of
        hanging the loop, per the house rule that no call may block a session.

        argv: the command tokens.
        timeout: seconds before giving up, None to wait forever.
        """
        try:
            async with asyncio.timeout(timeout):
                return await self.runner(argv)
        except TimeoutError:
            return 124, f"timed out after {timeout}s"

    async def attempted(
        self,
        blueprint: Blueprint,
        claim: str,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Run one claim command and stamp its certificate.

        blueprint: the loaded claim manifest.
        claim: the claim name to run.
        seed: RNG seed to record when the claim script used one.
        timeout: hard wall-clock cap in seconds.
        """
        exit_status, output = await self.bounded(blueprint.command(claim, self.root), timeout)
        return Certificate.stamp(
            claim=f"{blueprint.slug}/{claim}",
            result=payload(output),
            engine=NAME,
            engine_version=package_version(NAME),
            exit_status=exit_status,
            seed=seed,
            root=self.root,
        )

    async def swept(self, blueprint: Blueprint, claims: list[str]) -> dict[str, Certificate]:
        """Re-run claims concurrently, at most `RERUN_LIMIT` in flight.

        A `TaskGroup` rather than a bare gather, so an unexpected fault in one
        claim, or a ctrl-c reaching the loop, cancels the siblings and waits
        for them instead of abandoning half-finished subprocesses.

        blueprint: the loaded claim manifest.
        claims: the claim names this host can run.
        """
        semaphore = asyncio.Semaphore(RERUN_LIMIT)

        async def turn(claim: str) -> Certificate:
            async with semaphore:
                return await self.attempted(blueprint, claim)

        async with asyncio.TaskGroup() as group:
            tasks = {claim: group.create_task(turn(claim)) for claim in claims}
        return {claim: task.result() for claim, task in tasks.items()}


class FreshnessSweep:
    """One `verify` pass: re-run runnable claims, persist certificates, flag stale evidence."""

    def __init__(self, running: Running, blueprints: Path) -> None:
        """running: the claim execution seam.

        blueprints: the blueprints root directory.
        """
        self.running = running
        self.blueprints = blueprints

    async def report(self, slugs: list[str], revision: str) -> tuple[dict[str, JsonValue], int]:
        """(per-blueprint claim states, failure count) for one sweep.

        Every runnable claim re-runs and its certificate persists; each claim
        reports `fresh`, `failed`, or `skipped` plus whether its prior evidence
        was stamped at another git revision.

        slugs: the blueprint names to sweep.
        revision: the workspace's current git revision, the staleness reference.
        """
        report: dict[str, JsonValue] = {}
        failures = 0
        for name in slugs:
            blueprint = Blueprint.load(self.blueprints / name)
            stale = stale_claims(blueprint, revision)
            runnable = [
                claim
                for claim, spec in blueprint.claims.items()
                if not spec.requires or satisfied(spec.requires)
            ]
            fresh = await self.running.swept(blueprint, runnable)
            store = EvidenceStore(blueprint.directory)
            for certificate in fresh.values():
                store.append(certificate)
            failures += sum(1 for certificate in fresh.values() if not certificate.ok)
            report[name] = {
                claim: self.entry(fresh.get(claim), claim in stale) for claim in blueprint.claims
            }
        return report, failures

    def entry(self, certificate: Certificate | None, stale: bool) -> dict[str, JsonValue]:
        """One claim's report line: its state after the sweep and its stale flag."""
        state = "skipped" if certificate is None else "fresh" if certificate.ok else "failed"
        return {"state": state, "stale": stale}


def stale_claims(blueprint: Blueprint, revision: str) -> frozenset[str]:
    """Claims none of whose per-host latest certificates were stamped at `revision`.

    Hosts can disagree: one box re-ran after a commit while another still holds
    older evidence, and clocks across hosts are not comparable. So each host's
    ledger is judged by its own newest certificate per claim, and a claim only
    counts stale when no host's newest matches the current revision.

    blueprint: the loaded claim manifest.
    revision: the workspace's current git revision.
    """
    prefix = f"{blueprint.slug}/"
    newest: dict[tuple[str, str], Certificate] = {}
    for host, ledger in EvidenceStore.ledgers(blueprint.directory).items():
        for certificate in ledger:
            if not certificate.claim.startswith(prefix):
                continue
            key = (host, certificate.claim.removeprefix(prefix))
            if key not in newest or certificate.timestamp > newest[key].timestamp:
                newest[key] = certificate
    fresh = {
        name for (host, name), certificate in newest.items() if certificate.git_rev == revision
    }
    return frozenset(key[1] for key in newest) - fresh


def payload(output: str) -> JsonValue:
    """The structured result of a claim run, the last JSON value printed.

    Lines are scanned from the end; a line holding several concatenated JSON
    values (interleaved writers) yields its last complete value, and indented
    JSON still counts. Falls back to the tail of the raw output when the
    script printed no JSON at all.

    output: the combined stdout and stderr of the claim command.
    """
    for line in reversed(output.strip().splitlines()):
        candidate = line.strip()
        if candidate.startswith(("{", "[")) and (values := decoded(candidate)):
            return values[-1]
    return {"output": output.strip()[-2000:]}


def decoded(line: str) -> list[JsonValue]:
    """Every complete JSON value concatenated on one line, in order of appearance.

    line: one stripped output line starting with `{` or `[`.
    """
    decoder = json.JSONDecoder()
    values: list[JsonValue] = []
    position = 0
    while position < len(line):
        try:
            value, position = decoder.raw_decode(line, position)
        except json.JSONDecodeError:
            break
        values.append(value)
        while position < len(line) and line[position] in " \t":
            position += 1
    return values
