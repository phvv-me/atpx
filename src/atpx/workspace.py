import asyncio
import json
import tomllib
from datetime import date
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Protocol

from pydantic import JsonValue

from . import CONFIG, NAME
from .analytics import integer_sequences, lean_table, strategy_table
from .background import BackgroundChecks
from .blueprint import Blueprint, satisfied
from .briefing import Briefing, JudgeBriefing, JudgmentLedger
from .certificate import Certificate, git_revision
from .engines import (
    Capability,
    Engine,
    EngineUnavailableError,
    SearchEngine,
    SearchError,
    UnsupportedOperationError,
    VaultEngine,
    normalized,
)
from .evidence import EvidenceStore
from .index import ResultsIndex
from .roles import Role, Status, authorize
from .runtime import drive
from .zettel import Vault

CLOSING = {"smtlib": (Capability.SOLVE_SMT, "unsat"), "tptp": (Capability.PROVE_TPTP, "Theorem")}
RERUN_LIMIT = 4


class CommandRunner(Protocol):
    """How the check verb executes a claim command."""

    async def __call__(self, argv: list[str]) -> tuple[int, str]: ...


class ChefeRunner:
    """Runs claim commands inside the chefe-managed environment from the workspace root."""

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


class CrossCheckError(RuntimeError):
    """Raised when fewer than two independent engines can run a probe."""


def find_root(start: Path | None = None) -> Path:
    """Walk up from `start` to the directory whose root manifest declares `[workspace]`.

    start: where to begin, defaulting to the cwd.
    """
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        manifest = candidate / CONFIG
        if manifest.exists() and "workspace" in tomllib.loads(manifest.read_text()):
            return candidate
    raise FileNotFoundError(f"no {CONFIG} with a [workspace] table above {here}")


def workspace(root: str | Path | None = None) -> Workspace:
    """Open the workspace at `root`, discovering it from the cwd when omitted."""
    return Workspace(Path(root) if root else find_root())


class Workspace:
    """The verbs of the math loop over one filesystem state, no daemon and no database.

    The same methods back the Python API and the CLI; the third surface is the
    filesystem they read and write, blueprint directories with per-host evidence
    ledgers plus the vault zettels that carry node status. The verbs with real
    I/O underneath (`check`, `verify`, `recall`, `connect`) are async and
    compose on the caller's event loop; the CLI runs them through cyclopts,
    which owns the loop, and synchronous scripts block on them through the
    `sync` facade.

    The verb set is governed by the no-proxy principle, the tool offers only what
    an agent cannot already do well alone. Guardrails (append-only provenance,
    role-gated transitions, deterministic index regeneration), accelerators for
    measured friction (brief, judge_brief, graph, recall, the adversarial probes),
    and corpus analytics needing the whole ledger and log history (strategies,
    connect, lean_candidates). Any proposed verb an agent can replicate with one
    library import and no evidence value gets rejected. Zettel "Prova Proof
    Bookkeeping Package", the no-proxy principle section.
    """

    def __init__(self, root: Path, runner: CommandRunner | None = None) -> None:
        """root: the workspace root holding the root manifest.

        runner: claim command executor, defaulting to chefe.
        """
        self.root = root
        config = tomllib.loads((root / CONFIG).read_text())["workspace"]
        self.blueprints = root / config.get("blueprints", "research/math")
        self.vault = Vault(root / config.get("vault", "vault/Zettelkasten"))
        self.results_index = ResultsIndex(
            self.vault.path / config.get("index", "Mathematics Results Index.md")
        )
        self.runner = runner or ChefeRunner(root)

    @property
    def sync(self) -> SyncVerbs:
        """Blocking access to the async verbs, `workspace().sync.recall(...)`."""
        return SyncVerbs(self)

    async def check(
        self, slug: str, claim: str, seed: int | None = None, background: bool = False
    ) -> Certificate:
        """Run one blueprint claim, stamp a certificate, and persist it to evidence.

        A claim whose `requires` this host cannot meet is skipped gracefully: the
        returned certificate says so and nothing enters the evidence ledger,
        since a skip is not a run. With `background=True` the run detaches
        instead: the child process persists the real certificate on completion
        and the returned certificate only records the submission.

        slug: the blueprint directory name under the blueprints root.
        claim: the claim name declared in the blueprint manifest.
        seed: RNG seed to record when the claim script used one.
        background: detach the run instead of waiting for it.
        """
        blueprint = Blueprint.load(self.blueprints / slug)
        if background:
            return BackgroundChecks(blueprint, self.root).submit(claim)
        spec = blueprint.claim(claim)
        if spec.requires and not satisfied(spec.requires):
            return Certificate.stamp(
                claim=f"{slug}/{claim}",
                result={"skipped": True, "requires": spec.requires},
                engine=NAME,
                engine_version=package_version(NAME),
                root=self.root,
            )
        certificate = await self.attempt(blueprint, claim, seed)
        EvidenceStore(blueprint.directory).append(certificate)
        return certificate

    async def attempt(
        self, blueprint: Blueprint, claim: str, seed: int | None = None
    ) -> Certificate:
        """Run one claim command and stamp its certificate without persisting it.

        blueprint: the loaded claim manifest.
        claim: the claim name to run.
        seed: RNG seed to record when the claim script used one.
        """
        return await attempted(self.runner, blueprint, claim, self.root, seed)

    def checks(self, slug: str) -> list[dict[str, str]]:
        """Background submissions for one blueprint, each pending or landed.

        slug: the blueprint directory name under the blueprints root.
        """
        return BackgroundChecks(Blueprint.load(self.blueprints / slug), self.root).listing()

    async def verify(self, slug: str | None = None) -> Certificate:
        """Freshness sweep: re-run every claim this host can run and flag stale evidence.

        Claims re-run concurrently as asyncio subprocesses, at most
        `RERUN_LIMIT` in flight, and the fresh certificates land in the
        evidence ledger sequentially afterwards, keeping the per-host file
        race free. A claim is stale when its latest prior certificate was
        stamped at a different git revision than the tree now. Nothing is
        ever deleted; a `requires`-gated claim this host cannot run is
        reported skipped.

        slug: one blueprint to sweep, defaulting to every blueprint with a manifest.
        """
        slugs = (
            [slug] if slug else sorted(p.parent.name for p in self.blueprints.glob(f"*/{CONFIG}"))
        )
        revision = git_revision(self.root)
        report: dict[str, JsonValue] = {}
        failures = 0
        for name in slugs:
            blueprint = Blueprint.load(self.blueprints / name)
            stale = self.stale_claims(blueprint, revision)
            runnable = [
                claim
                for claim, spec in blueprint.claims.items()
                if not spec.requires or satisfied(spec.requires)
            ]
            fresh = await swept(self.runner, blueprint, runnable, self.root)
            store = EvidenceStore(blueprint.directory)
            for certificate in fresh.values():
                store.append(certificate)
            entries: dict[str, JsonValue] = {}
            for claim in blueprint.claims:
                ran = fresh.get(claim)
                state = "skipped" if ran is None else "fresh" if ran.ok else "failed"
                failures += ran is not None and not ran.ok
                entries[claim] = {"state": state, "stale": claim in stale}
            report[name] = entries
        return Certificate.stamp(
            claim=f"verify {slug}" if slug else "verify",
            result=report,
            engine=NAME,
            engine_version=package_version(NAME),
            exit_status=0 if not failures else 1,
            root=self.root,
        )

    def stale_claims(self, blueprint: Blueprint, revision: str) -> frozenset[str]:
        """Claims whose latest persisted certificate was stamped at another git revision.

        blueprint: the loaded claim manifest.
        revision: the workspace's current git revision.
        """
        latest: dict[str, Certificate] = {}
        for ledger in EvidenceStore.ledgers(blueprint.directory).values():
            for certificate in ledger:
                name = certificate.claim.partition("/")[2]
                if name not in latest or certificate.timestamp > latest[name].timestamp:
                    latest[name] = certificate
        return frozenset(
            name for name, certificate in latest.items() if certificate.git_rev != revision
        )

    def brief(self, slug: str) -> str:
        """The full agent context bundle for one blueprint node, as markdown.

        slug: the blueprint directory name under the blueprints root.
        """
        blueprint = Blueprint.load(self.blueprints / slug)
        node = self.vault.find(blueprint.zettel)
        return Briefing(blueprint, node, self.vault, git_revision(self.root)).render()

    def judge_brief(self, slug: str) -> str:
        """What changed since the node's last refuter judgment, as markdown.

        slug: the blueprint directory name under the blueprints root.
        """
        blueprint = Blueprint.load(self.blueprints / slug)
        node = self.vault.find(blueprint.zettel)
        return JudgeBriefing(blueprint, node).render()

    def status(self) -> dict[str, list[str]]:
        """Node names grouped by zettel status, down the certification ladder."""
        return self.vault.statuses()

    def graph(self) -> list[dict[str, str | dict[str, str]]]:
        """The frontier: unsettled nodes whose wikilink dependencies are all settled."""
        return self.vault.frontier()

    async def recall(self, query: str, sources: list[str] | None = None) -> Certificate:
        """Federated read-only search, one certificate listing the hits per source.

        Every engine with the `search` capability is asked unless `sources` names
        a subset, and the sources are awaited concurrently on the caller's
        event loop since they are network and subprocess bound. A source that is
        unavailable or fails at run time becomes an entry under `errors` and
        the certificate exits nonzero, so a partial recall is never mistaken
        for a complete one.

        query: the search text every source receives.
        sources: engine names to ask, defaulting to every search engine.
        """
        candidates = (
            [Engine.find(name) for name in sources]
            if sources
            else Engine.supporting(Capability.SEARCH)
        )
        instances = [self.searcher(engine) for engine in candidates]
        hits, errors = await recalled(instances, query)
        return Certificate.stamp(
            claim=f"recall {query}",
            result={"hits": hits, "errors": errors},
            engine=NAME,
            engine_version=package_version(NAME),
            exit_status=0 if not errors else 1,
            root=self.root,
        )

    def searcher(self, engine: type[Engine]) -> SearchEngine:
        """One ready search source, refusing engines without the search capability.

        engine: the registered engine class to instantiate.
        """
        if not issubclass(engine, SearchEngine):
            raise UnsupportedOperationError(
                f"{engine.name} only does {engine.capability.value}, not {Capability.SEARCH.value}"
            )
        return VaultEngine(self.root) if engine is VaultEngine else engine()

    async def connect(self, slug: str, minimum: int = 4, limit: int = 8) -> Certificate:
        """Fingerprint a node's evidence numerics against the OEIS, one certificate of matches.

        Integer runs of `minimum` or more values are extracted from every
        persisted certificate payload and each is queried through the existing
        OEIS search engine via `recall`, keeping the per-source error
        discipline. v1 is ambient conjecture generation, nothing is scored.

        slug: the blueprint directory name under the blueprints root.
        minimum: shortest integer run worth fingerprinting.
        limit: most sequences queried per call.
        """
        blueprint = Blueprint.load(self.blueprints / slug)
        ledgers = EvidenceStore.ledgers(blueprint.directory)
        runs = dict.fromkeys(
            run
            for ledger in ledgers.values()
            for certificate in ledger
            for run in integer_sequences(certificate.result, minimum)
        )
        results: dict[str, JsonValue] = {}
        clean = True
        for run in list(runs)[:limit]:
            found = await self.recall(", ".join(map(str, run)), sources=["oeis"])
            results[found.claim.removeprefix("recall ")] = found.result
            clean = clean and found.ok
        return Certificate.stamp(
            claim=f"connect {slug}",
            result=results,
            engine=NAME,
            engine_version=package_version(NAME),
            exit_status=0 if clean else 1,
            root=self.root,
        )

    def strategies(self) -> str:
        """Close-rates by strategy tag over every node's append-only log, a markdown table."""
        return strategy_table(self.vault.nodes())

    def lean_candidates(self) -> str:
        """Sketched nodes ranked for formalization, backlink count over statement length.

        A documented heuristic: load-bearing cheap leaves float to the top so the
        formalizer's rare Lean budget goes where it pays.
        """
        return lean_table(self.vault.nodes(), self.vault.notes())

    def log(
        self, zettel: str, role: Role | str, tag: str, message: str, status: str | None = None
    ) -> str:
        """Append one role-stamped log line to a node, optionally moving its status.

        Status transitions are role-gated in code: only a refuter settles a node
        as sketched or refuted, and only the formalizer marks it verified. A
        refuter line on a node with a blueprint also snapshots the node into the
        blueprint's judgment ledger, the diff base `judge_brief` reads.

        zettel: the node's name (filename stem).
        role: who is writing, mathematician, prover, refuter, or formalizer.
        tag: the strategy or pass tag inside the brackets.
        message: the one-line entry body.
        status: optional new status for the node.
        """
        author, note = Role(role), self.vault.find(zettel)
        target = Status(status) if status is not None else None
        if target is not None:
            authorize(author, target)
        line = f"- [{author.value}/{tag} {date.today().isoformat()}] {message}"
        note.append_log(line)
        if target is not None:
            note.set_status(target)
        if author is Role.REFUTER and note.blueprint:
            JudgmentLedger(self.root / note.blueprint).record(note)
        return line

    def index(self, write: bool = False) -> str:
        """Regenerate the results index from node frontmatter, writing it when asked.

        write: persist the regenerated index over the existing file.
        """
        text = self.results_index.render(self.vault.nodes())
        if write:
            self.results_index.path.write_text(text)
        return text

    def compute(self, engine: str, operation: str, payload: str) -> Certificate:
        """Run one typed engine operation and certify its result.

        engine: registered engine name.
        operation: one of the engine capabilities.
        payload: the operation input.
        """
        instance = Engine.find(engine)()
        result = instance.run(operation, payload)
        return Certificate.stamp(
            claim=f"{operation} {payload}",
            result=result,
            engine=instance.name,
            engine_version=instance.version(),
            root=self.root,
        )

    def prove(self, goal: str, syntax: str | None = None) -> Certificate:
        """Try ATP engines in capability order on a goal, certifying who closed it.

        SMT-LIB goals assert the claim's negation, so `unsat` closes them; TPTP
        goals close on SZS Theorem. When no engine closes the goal the
        certificate records every attempt and exits nonzero.

        goal: the goal text in SMT-LIB or TPTP form.
        syntax: `smtlib` or `tptp`, detected from the goal when omitted.
        """
        dialect = syntax or self.syntax(goal)
        if dialect not in CLOSING:
            known = ", ".join(sorted(CLOSING))
            raise ValueError(f"unknown syntax {dialect!r}; pass one of {known}")
        capability, closing = CLOSING[dialect]
        attempts: dict[str, str] = {}
        for engine in Engine.supporting(capability):
            instance = engine()
            if not instance.available():
                continue
            attempts[instance.name] = instance.run(capability, goal)
            if attempts[instance.name] == closing:
                return Certificate.stamp(
                    claim=goal,
                    result={"closed": True, "attempts": dict(attempts)},
                    engine=instance.name,
                    engine_version=instance.version(),
                    root=self.root,
                )
        return Certificate.stamp(
            claim=goal,
            result={"closed": False, "attempts": dict(attempts)},
            engine=NAME,
            engine_version=package_version(NAME),
            exit_status=1,
            root=self.root,
        )

    def cross_check(
        self, operation: str, payload: str, engines: list[str] | None = None
    ) -> Certificate:
        """Run the same probe on independent engines and certify agreement.

        The probes run as a plain sequential loop on purpose. Every engine
        here is an in-process CPU-bound library (sympy, mpmath, flint, z3,
        cvc5), so there is no I/O for an event loop to overlap and threads
        would only add shared-state hazards without speedup under the GIL.

        operation: the shared capability to probe.
        payload: the probe input every engine receives.
        engines: engine names to use, defaulting to every available implementation.
        """
        capability = Capability(operation)
        candidates = (
            [Engine.find(name) for name in engines] if engines else Engine.supporting(capability)
        )
        instances = [engine() for engine in candidates if engine().available()]
        if len(instances) < 2:
            raise CrossCheckError(
                f"cross-check needs at least two available engines for {capability.value}"
            )
        results = {instance.name: instance.run(capability, payload) for instance in instances}
        agree = len({normalized(capability, value) for value in results.values()}) == 1
        return Certificate.stamp(
            claim=f"{operation} {payload}",
            result={"agree": agree, "results": dict(results)},
            engine=NAME,
            engine_version=package_version(NAME),
            exit_status=0 if agree else 1,
            root=self.root,
        )

    @staticmethod
    def payload(output: str) -> JsonValue:
        """The structured result of a claim run, the last JSON object printed.

        Falls back to the tail of the raw output when the script printed no JSON.

        output: the combined stdout and stderr of the claim command.
        """
        for line in reversed(output.strip().splitlines()):
            if line.startswith(("{", "[")):
                try:
                    parsed: JsonValue = json.loads(line)
                except json.JSONDecodeError:
                    continue
                return parsed
        return {"output": output.strip()[-2000:]}

    def syntax(self, goal: str) -> str:
        """Detect whether a goal is SMT-LIB or TPTP text."""
        if any(marker in goal for marker in ("(assert", "(set-logic", "(declare-")):
            return "smtlib"
        if any(marker in goal for marker in ("fof(", "cnf(", "tff(", "thf(")):
            return "tptp"
        raise ValueError("cannot detect goal syntax, pass syntax='smtlib' or 'tptp'")


class SyncVerbs:
    """The async workspace verbs as plain blocking calls, for one-liner scripts.

    `workspace().sync.recall("...")` drives the verb to completion on a fresh
    event loop, so a single Python expression needs no asyncio boilerplate.
    Code already inside a running loop should await the workspace verb
    directly; there the facade refuses with `drive`'s clear nested-loop error.
    """

    def __init__(self, verbs: Workspace) -> None:
        """verbs: the workspace whose async verbs this facade blocks on."""
        self.verbs = verbs

    def check(
        self, slug: str, claim: str, seed: int | None = None, background: bool = False
    ) -> Certificate:
        """Blocking `Workspace.check`, one claim run stamped and persisted.

        slug: the blueprint directory name under the blueprints root.
        claim: the claim name declared in the blueprint manifest.
        seed: RNG seed to record when the claim script used one.
        background: detach the run instead of waiting for it.
        """
        return drive(self.verbs.check(slug, claim, seed, background))

    def verify(self, slug: str | None = None) -> Certificate:
        """Blocking `Workspace.verify`, the freshness sweep run to completion.

        slug: one blueprint to sweep, defaulting to every blueprint with a manifest.
        """
        return drive(self.verbs.verify(slug))

    def recall(self, query: str, sources: list[str] | None = None) -> Certificate:
        """Blocking `Workspace.recall`, the federated search awaited to one certificate.

        query: the search text every source receives.
        sources: engine names to ask, defaulting to every search engine.
        """
        return drive(self.verbs.recall(query, sources))

    def connect(self, slug: str, minimum: int = 4, limit: int = 8) -> Certificate:
        """Blocking `Workspace.connect`, the OEIS fingerprinting run to completion.

        slug: the blueprint directory name under the blueprints root.
        minimum: shortest integer run worth fingerprinting.
        limit: most sequences queried per call.
        """
        return drive(self.verbs.connect(slug, minimum, limit))


async def attempted(
    runner: CommandRunner, blueprint: Blueprint, claim: str, root: Path, seed: int | None = None
) -> Certificate:
    """Run one claim command through the runner and stamp its certificate.

    The async internal under `Workspace.attempt` and the `verify` sweep, so a
    single claim and a concurrent batch share one code path.

    runner: the claim command executor.
    blueprint: the loaded claim manifest.
    claim: the claim name to run.
    root: the workspace root commands run from.
    seed: RNG seed to record when the claim script used one.
    """
    exit_status, output = await runner(blueprint.command(claim, root))
    return Certificate.stamp(
        claim=f"{blueprint.slug}/{claim}",
        result=Workspace.payload(output),
        engine=NAME,
        engine_version=package_version(NAME),
        exit_status=exit_status,
        seed=seed,
        root=root,
    )


async def swept(
    runner: CommandRunner, blueprint: Blueprint, claims: list[str], root: Path
) -> dict[str, Certificate]:
    """Re-run claims as concurrent subprocesses, at most `RERUN_LIMIT` in flight.

    The semaphore bounds the fan-out so a wide blueprint cannot fork dozens of
    chefe environments at once.

    runner: the claim command executor.
    blueprint: the loaded claim manifest.
    claims: the claim names this host can run.
    root: the workspace root commands run from.
    """
    semaphore = asyncio.Semaphore(RERUN_LIMIT)

    async def bounded(claim: str) -> Certificate:
        async with semaphore:
            return await attempted(runner, blueprint, claim, root)

    certificates = await asyncio.gather(*(bounded(claim) for claim in claims))
    return dict(zip(claims, certificates, strict=True))


async def recalled(
    instances: list[SearchEngine], query: str
) -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
    """Fan one query out to every source concurrently, splitting hits from errors.

    A source that is unavailable or fails at run time lands in the error map
    instead of vanishing, so a partial recall never looks complete.

    instances: the search sources to ask.
    query: the search text every source receives.
    """

    async def attempt(instance: SearchEngine) -> tuple[str, JsonValue, str | None]:
        try:
            return instance.name, json.loads(await instance.search(query)), None
        except (SearchError, EngineUnavailableError) as error:
            return instance.name, None, str(error)

    hits: dict[str, JsonValue] = {}
    errors: dict[str, JsonValue] = {}
    for name, found, error in await asyncio.gather(*(attempt(i) for i in instances)):
        if error is None:
            hits[name] = found
        else:
            errors[name] = error
    return hits, errors
