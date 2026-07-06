import os
import tomllib
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter
from pydantic import JsonValue

from . import CONFIG, NAME
from .background import BackgroundChecks
from .blueprint import Blueprint, register, satisfied
from .briefing import Briefing, JudgeBriefing
from .certificate import Certificate, git_revision
from .discovery import Discovery
from .doctoring import DoctorReport
from .evidence import EvidenceStore
from .index import ResultsIndex
from .leaning import LeanAudit
from .recalling import Recall
from .roles import Status
from .running import ChefeRunner, CommandRunner, FreshnessSweep, Running
from .runtime import drive
from .settlement import Petition, Settlement
from .zettel import LogEntry, Vault

ROOT_VARIABLE = f"{NAME.upper()}_ROOT"


def rooted(candidate: Path) -> bool:
    """Whether `candidate` holds a root manifest declaring `[workspace]`."""
    manifest = candidate / CONFIG
    return manifest.exists() and "workspace" in tomllib.loads(manifest.read_text())


def find_root(start: Path | None = None) -> Path:
    """The workspace root: `ATPX_ROOT` when set, else walking up from `start` or the cwd.

    The environment override pins every atpx invocation to one workspace, so a
    verb fired from anywhere in a monorepo cannot silently target whatever
    vault happens to sit above the cwd. An explicit `start` still wins, since
    the caller named it.

    start: where to begin walking, defaulting to the cwd.
    """
    if start is None and (pinned := os.environ.get(ROOT_VARIABLE)):
        home = Path(pinned).resolve()
        if not rooted(home):
            raise FileNotFoundError(
                f"{ROOT_VARIABLE}={pinned} has no {CONFIG} with a [workspace] table"
            )
        return home
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if rooted(candidate):
            return candidate
    raise FileNotFoundError(f"no {CONFIG} with a [workspace] table above {here}")


def workspace(root: str | Path | None = None) -> Workspace:
    """Open the workspace at `root`, discovering it from `ATPX_ROOT` or the cwd when omitted."""
    return Workspace(Path(root) if root else find_root())


class Workspace:
    """The verbs of the math loop over one filesystem state, no daemon and no database.

    A thin facade: each verb reads as its algorithm and delegates to one
    service, `Running` for capture-first execution, `FreshnessSweep` for
    verify, `Settlement` for the evidence gates, `LeanAudit` for build
    ingestion, `Discovery` for the fit lane, `Recall` for federated search,
    `DoctorReport` for the lint. v2 posture: capture first, tolerate the
    mess, gate on evidence. Zettel "atpx Critical Review 2026-07 From
    Gatekeeper to Capture-First Ledger".
    """

    def __init__(self, root: Path, runner: CommandRunner | None = None) -> None:
        """root: the workspace root holding the root manifest.

        runner: command executor, defaulting to chefe.
        """
        self.root = root
        config = tomllib.loads((root / CONFIG).read_text())["workspace"]
        self.blueprints = root / config.get("blueprints", "research/math")
        self.vault = Vault(root / config.get("vault", "vault/Zettelkasten"))
        self.results_index = ResultsIndex(
            self.vault.path / config.get("index", "Mathematics Results Index.md")
        )
        self.lean_task = config.get("lean", "lean-build")
        self.running = Running(runner or ChefeRunner(root), root)

    @property
    def sync(self) -> SyncVerbs:
        """Blocking access to the async verbs, `workspace().sync.recall(...)`."""
        return SyncVerbs(self)

    async def run(
        self,
        slug: str,
        claim: str,
        *argv: Annotated[str, Parameter(allow_leading_hyphen=True)],
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Capture-first: run any command as a claim, stamp, persist, auto-register.

        The manifest is a record the tool maintains, not a form the agent fills.
        A new slug gets a blueprint directory and manifest, a new claim gets its
        command registered on first use, and the certificate always lands in the
        evidence ledger. The command is a leading-hyphen var-positional in the
        chefe idiom, so hyphenated tokens like `python -c ...` pass through
        verbatim on the CLI; put `--seed` and `--timeout` before the command,
        and separate a command that itself takes those flags with `--`.

        slug: the blueprint directory name, created when missing.
        claim: the claim name, registered with this command when new.
        argv: the command tokens to execute through the runner.
        seed: RNG seed to record when the command used one.
        timeout: hard wall-clock cap in seconds, stamped as exit 124 on expiry.
        """
        blueprint = self.register(slug, claim, list(argv))
        certificate = await self.running.attempted(blueprint, claim, seed=seed, timeout=timeout)
        EvidenceStore(blueprint.directory).append(certificate)
        return certificate

    def register(self, slug: str, claim: str, argv: list[str] | None = None) -> Blueprint:
        """Load a blueprint, creating the directory, manifest, or claim as needed.

        slug: the blueprint directory name under the blueprints root.
        claim: the claim to ensure exists, when `argv` supplies its command.
        argv: the command tokens to register for a claim not yet in the manifest.
        """
        return register(self.blueprints, slug, claim, argv)

    async def check(
        self, slug: str, claim: str, seed: int | None = None, background: bool = False
    ) -> Certificate:
        """Re-run one registered blueprint claim, stamp a certificate, persist it.

        A claim whose `requires` this host cannot meet is skipped gracefully:
        the returned certificate says so and nothing enters the evidence ledger,
        since a skip is not a run. With `background=True` the run detaches and
        the child persists the real certificate on completion.

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
            return self.skipped(slug, claim, spec.requires)
        certificate = await self.running.attempted(blueprint, claim, seed=seed)
        EvidenceStore(blueprint.directory).append(certificate)
        return certificate

    def skipped(self, slug: str, claim: str, requirement: str) -> Certificate:
        """The unpersisted certificate for a claim this host cannot run."""
        return Certificate.stamp(
            claim=f"{slug}/{claim}",
            result={"skipped": True, "requires": requirement},
            engine=NAME,
            engine_version=package_version(NAME),
            root=self.root,
        )

    def checks(self, slug: str) -> list[dict[str, str]]:
        """Background submissions for one blueprint, each pending or landed.

        slug: the blueprint directory name under the blueprints root.
        """
        return BackgroundChecks(Blueprint.load(self.blueprints / slug), self.root).listing()

    async def verify(self, slug: str | None = None) -> Certificate:
        """Freshness sweep: re-run every claim this host can run and flag stale evidence.

        slug: one blueprint to sweep, defaulting to every blueprint with a manifest.
        """
        slugs = (
            [slug] if slug else sorted(p.parent.name for p in self.blueprints.glob(f"*/{CONFIG}"))
        )
        sweep = FreshnessSweep(self.running, self.blueprints)
        report, failures = await sweep.report(slugs, git_revision(self.root))
        return Certificate.stamp(
            claim=f"verify {slug}" if slug else "verify",
            result=report,
            engine=NAME,
            engine_version=package_version(NAME),
            exit_status=0 if not failures else 1,
            root=self.root,
        )

    def brief(self, slug: str) -> str:
        """The full agent context bundle for one blueprint node, as markdown.

        slug: the blueprint directory name under the blueprints root.
        """
        blueprint = Blueprint.load(self.blueprints / slug)
        node = self.vault.find(blueprint.zettel)
        return Briefing(blueprint, node, self.vault, git_revision(self.root)).render()

    def judge_brief(self, slug: str) -> str:
        """What changed since the node's last judgment snapshot, as markdown.

        slug: the blueprint directory name under the blueprints root.
        """
        blueprint = Blueprint.load(self.blueprints / slug)
        node = self.vault.find(blueprint.zettel)
        return JudgeBriefing(blueprint, node).render()

    def status(self) -> dict[str, list[str]]:
        """Node names grouped by zettel status, malformed values under `invalid`."""
        return self.vault.statuses()

    def graph(self) -> list[dict[str, str | dict[str, str]]]:
        """The frontier: unsettled nodes whose wikilink dependencies are all settled."""
        return self.vault.frontier()

    def doctor(self) -> dict[str, JsonValue]:
        """What needs repair: invalid statuses, stray evidence, missing manifests.

        The lint the tolerant readers rely on. Reports and never mutates.
        """
        return DoctorReport(self.vault, self.blueprints, self.root).compiled()

    def settle(
        self,
        zettel: str,
        status: str,
        message: str = "",
        judgment: str | None = None,
        counterexample: str | None = None,
        lean: str | None = None,
    ) -> str:
        """Move a node's status, gated on evidence artifacts rather than claimed roles.

        `sketched` demands a judgment file, `refuted` a counterexample
        certificate in the node's ledgers, `verified` a clean Lean certificate
        with zero sorries and no flagged risky axioms. The free statuses
        (open, in_progress, abandoned, known) need none.

        zettel: the node's name (filename stem).
        status: the target lifecycle status.
        message: the one-line journal entry body.
        judgment: path to the recorded refuter ruling, required for sketched.
        counterexample: claim id of a persisted counterexample certificate, for refuted.
        lean: claim id of a persisted clean Lean certificate, for verified.
        """
        target, node = Status(status), self.vault.find(zettel)
        petition = Petition(
            message=message, judgment=judgment, counterexample=counterexample, lean=lean
        )
        return Settlement(self.root).move(node, target, petition)

    async def lean(
        self, slug: str, target: str | None = None, timeout: float | None = 3600
    ) -> Certificate:
        """Ingest a Lean build as evidence: run it, audit it, stamp, persist.

        slug: the blueprint the certificate lands in, created when missing.
        target: the build target passed to the lean task, defaulting to none.
        timeout: hard wall-clock cap in seconds.
        """
        blueprint = self.register(slug, "lean", None)
        certificate = await LeanAudit(self.running, self.lean_task).certified(
            slug, target, timeout
        )
        EvidenceStore(blueprint.directory).append(certificate)
        return certificate

    def fit(
        self,
        data: str,
        target: str,
        slug: str | None = None,
        seed: int = 0,
        niterations: int = 40,
        unary: list[str] | None = None,
        binary: list[str] | None = None,
        tail: float | None = None,
        driver: str | None = None,
        features: list[str] | None = None,
    ) -> Certificate:
        """The fit lane: PySR over a data artifact, certifying the Pareto front.

        Operator menus take repeated flags or comma-joined tokens, so
        `--binary "+,-,*"` sidesteps flag parsing of a bare `-`. The data path
        resolves cwd-first and then root-relative. Records honest
        unavailability when pysr is not installed.

        data: path to a CSV whose named column is the target.
        target: the column to fit.
        slug: blueprint to persist into, defaulting to an unpersisted certificate.
        seed: random_state for the certifying run.
        niterations: search budget.
        unary: unary operator menu, PySR's `unary_operators`, defaults hold when omitted.
        binary: binary operator menu, PySR's `binary_operators`, defaults hold when omitted.
        tail: hold out this fraction of the rows with the largest driver values
            instead of a random 20%.
        driver: the column ranking the tail holdout, defaulting to the first
            feature column.
        features: restrict the fit to these columns, defaulting to every
            non-target column.
        """
        certificate = Discovery(self.root).fit(
            data,
            target,
            seed=seed,
            niterations=niterations,
            unary=unary,
            binary=binary,
            tail=tail,
            driver=driver,
            features=features,
        )
        if slug and certificate.ok:
            EvidenceStore(self.register(slug, "fit", None).directory).append(certificate)
        return certificate

    async def recall(self, query: str, sources: list[str] | None = None) -> Certificate:
        """Federated read-only search, one certificate listing the hits per source.

        query: the search text every source receives.
        sources: engine names to ask, defaulting to every search engine.
        """
        hits, errors = await Recall(self.root).fanned(query, sources)
        return Certificate.stamp(
            claim=f"recall {query}",
            result={"hits": hits, "errors": errors},
            engine=NAME,
            engine_version=package_version(NAME),
            exit_status=0 if not errors else 1,
            root=self.root,
        )

    def log(self, zettel: str, who: str, tag: str, message: str) -> str:
        """Append one journal line to a node, `- [who/tag date] message`.

        Status moves live in `settle`, which gates them on evidence. The entry
        is validated to round-trip through the journal parser, so a `who` with
        spaces or a multi-line message is refused instead of silently vanishing.

        zettel: the node's name (filename stem).
        who: free-form author label, mathematician, prover, refuter, a model name.
        tag: the strategy or pass tag inside the brackets.
        message: the one-line entry body.
        """
        node = self.vault.find(zettel)
        line = str(LogEntry.today(who=who, tag=tag, message=message))
        node.append_log(line)
        return line

    def index(self, write: bool = False) -> str:
        """Regenerate the results index from node frontmatter, writing it when asked.

        write: persist the regenerated index over the existing file.
        """
        text = self.results_index.render(self.vault.nodes())
        if write:
            self.results_index.path.write_text(text)
        return text


class SyncVerbs:
    """The async workspace verbs as plain blocking calls, for one-liner scripts."""

    def __init__(self, verbs: Workspace) -> None:
        """verbs: the workspace whose async verbs this facade blocks on."""
        self.verbs = verbs

    def run(
        self,
        slug: str,
        claim: str,
        *argv: str,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Blocking `Workspace.run`, capture-first execution to one certificate."""
        return drive(self.verbs.run(slug, claim, *argv, seed=seed, timeout=timeout))

    def check(
        self, slug: str, claim: str, seed: int | None = None, background: bool = False
    ) -> Certificate:
        """Blocking `Workspace.check`, one claim run stamped and persisted."""
        return drive(self.verbs.check(slug, claim, seed, background))

    def verify(self, slug: str | None = None) -> Certificate:
        """Blocking `Workspace.verify`, the freshness sweep run to completion."""
        return drive(self.verbs.verify(slug))

    def recall(self, query: str, sources: list[str] | None = None) -> Certificate:
        """Blocking `Workspace.recall`, the federated search awaited to one certificate."""
        return drive(self.verbs.recall(query, sources))

    def lean(
        self, slug: str, target: str | None = None, timeout: float | None = 3600
    ) -> Certificate:
        """Blocking `Workspace.lean`, one build ingested to one certificate."""
        return drive(self.verbs.lean(slug, target, timeout))
