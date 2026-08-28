import shlex
import tomllib
from collections.abc import Mapping, Sequence
from functools import cached_property
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter
from pydantic import JsonValue

from ...blueprint.manifest import Blueprint
from ...contracts.universe import Universe
from ...contracts.vocabulary import Vocabulary
from ...core.certificate import Certificate
from ...core.evidence import EvidenceStore
from ...graph.store import NodeStore
from ...models.lanes import Lanes
from ...running.execution import Running
from ...running.runners.process import ProcessRunner
from ...running.runners.seam import CommandRunner
from ...study.doctoring import DoctorReport
from ...study.index import LedgerIndex
from ...support.naming import Naming
from ..access import SyncVerbs, find_root, find_roots
from ..foundation import Slug
from .checking import CheckVerbs
from .counseling import CounselVerbs
from .studying import StudyVerbs


class Workspace(CheckVerbs, StudyVerbs, CounselVerbs):
    """The verbs of the math loop over one filesystem state, no daemon and no database.

    A thin facade over three sibling verb groups: `CheckVerbs` for
    capture-first execution and the freshness sweep, `StudyVerbs` for
    briefs, fleet views, the lint, and the journal, and `CounselVerbs` for
    scaffolding, settling, counsel, the fit lane, Lean ingestion, and
    recall. Each verb group declares only `FoundationState`, the structural
    shape it draws on, as its base, so `Workspace` is the single concrete
    provider of the root, the stores, the lanes, and the runner, and the
    three sit disjoint beside it rather than each subclassing it and forming
    a diamond. v3 posture: capture first, tolerate the mess, gate on
    evidence, and keep all node state blueprint-local in `node.md`, fully
    independent of any vault.
    """

    def __init__(self, given: Path | None = None, runner: CommandRunner | None = None) -> None:
        """given: where to look for the workspace, `ATPX_ROOT` or the cwd when None.

        Nothing here touches the filesystem: the root and everything read out of its
        manifest resolve on first use, so the CLI can print its own verb roster from a
        directory that holds no workspace at all, and a `--project` pin set after
        construction still decides which workspace the verbs act on.

        runner: command executor, defaulting to the manifest's declared launcher.
        """
        self.given = given
        self.runner = runner

    @cached_property
    def blueprints(self) -> Sequence[Path]:
        """The declared blueprint roots, in declaration order, where every node lives.

        A workspace declares one root or several. Several is what a program needs once
        its claims of record move between trees, `blueprints = ["math", "experiments"]`,
        and the whole graph is then read as their union rather than as two workspaces.
        A bare string still declares one root, so nothing that names a single tree has
        to change. The first root is where a fresh blueprint lands.
        """
        declared = self.config.get("blueprints", "research/math")
        names = declared if isinstance(declared, list) else [declared]
        return [self.root / str(name) for name in names]

    @cached_property
    def config(self) -> Mapping[str, JsonValue]:
        """The `[workspace]` table of the root manifest."""
        return self.manifest["workspace"]

    @cached_property
    def lanes(self) -> Lanes:
        """The counsel lanes the workspace declares under `[models]`."""
        return Lanes.configured(self.manifest.get("models", {}))

    @cached_property
    def launcher(self) -> Sequence[str]:
        """The `[workspace] runner` command prefix every claim and background check runs behind.

        A monorepo declares its own environment tool here, so a claim command in a node
        manifest stays the bare command it is and the workspace decides what it runs
        inside. A plain checkout declares nothing and runs claims on the interpreter
        already around atpx.
        """
        return shlex.split(str(self.config.get("runner", "")))

    @cached_property
    def lean_task(self) -> str:
        """The declared task name that runs the Lean build."""
        return str(self.config.get("lean", "lean-build"))

    @cached_property
    def ledger_index(self) -> LedgerIndex:
        """The generated index artifacts, the markdown note and the graph JSON beside it.

        The manifest's `index` setting names the note root-relative; an
        undeclared index lives beside the nodes as `INDEX.md`.
        """
        configured = self.config.get("index")
        path = self.root / str(configured) if configured else self.nodes.path / "INDEX.md"
        return LedgerIndex(path)

    @cached_property
    def manifest(self) -> Mapping[str, Mapping[str, JsonValue]]:
        """The parsed root manifest, read once per workspace."""
        return tomllib.loads((self.root / Naming.CONFIG).read_text())

    @cached_property
    def nodes(self) -> NodeStore:
        """The blueprint node graph."""
        return NodeStore(*self.blueprints)

    @cached_property
    def root(self) -> Path:
        """The workspace root, discovered from `given`, `ATPX_ROOT`, or the cwd on first use."""
        return find_root(self.given)

    @cached_property
    def running(self) -> Running:
        """The claim execution seam, behind the workspace's declared launcher."""
        runner = self.runner or ProcessRunner(root=self.root, launcher=self.launcher)
        return Running(runner, self.root)

    @property
    def sync(self) -> SyncVerbs:
        """Blocking access to the async verbs, `workspace().sync.recall(...)`."""
        return SyncVerbs(self)

    @cached_property
    def universe(self) -> Universe | None:
        """The `[universe]` trial layout this workspace declares, None when it declares none.

        Read here and executed nowhere: atpx owns the declaration because the workspace
        manifest is where a project says what shape it is, and whatever runs the trials
        reads the same table without either side importing the other.
        """
        declared = self.manifest.get("universe")
        return Universe.model_validate(declared) if declared else None

    @cached_property
    def vocabulary(self) -> Vocabulary:
        """The settled words the `[vocabulary]` table declares, empty when it declares none."""
        return Vocabulary.declared(self.manifest.get("vocabulary", {}))

    def doctor(self) -> Certificate:
        """What needs repair, here and in every workspace nested inside this one.

        This is both the lint tolerant readers rely on and the one command a monorepo runs
        to ask whether every mathematical idea it holds is still settled. Reports and never
        mutates. Each workspace is keyed in the payload by its path relative to this one,
        `.` for this one, so a single invocation from the top answers for every project
        beneath it and no caller ever pins a root per project.

        Exit is nonzero once a finding contradicts what a workspace itself asserts or
        leaves a node below the completeness contract: a status outside the ladder, a
        wikilink to nothing, a claim whose newest evidence failed, never ran, or predates
        the node statement it supports, frontmatter that does not parse, a node without a
        statement of record or a refutation condition, a sketched node whose linked
        judgment is missing or names no attacking rung, a statement that drifted from its
        judgment snapshot, or an index a regeneration would change. Untidiness that
        capture-first work is allowed to leave behind, stray data files under `evidence/`,
        a blueprint with no manifest or no node yet, or certificates with no design file,
        reports without failing the gate.
        """
        reports: dict[str, JsonValue] = {}
        broken: list[JsonValue] = []
        for root in find_roots(self.root):
            space = self if root == self.root else Workspace(root)
            report = DoctorReport(space.nodes, root=root, index=space.ledger_index).compiled()
            where = root.relative_to(self.root).as_posix()
            reports[where] = report
            broken += [f"{where}: {finding}" for finding in DoctorReport.breakages(report)]
        return Certificate.stamp(
            claim="doctor",
            result={"breakages": broken, "workspaces": reports},
            engine=Naming.NAME,
            engine_version=package_version(Naming.NAME),
            exit_status=1 if broken else 0,
            root=self.root,
        )

    def filed(self, path: str) -> Path:
        """A file argument resolved cwd-first and then workspace-root-relative.

        path: the path as given, absolute or relative.
        """
        direct = Path(path)
        return direct if direct.exists() else self.root / path

    def register(self, slug: str, *, claim: str, argv: Sequence[str] | None = None) -> Blueprint:
        """Load a blueprint, creating the directory, manifest, or claim as needed.

        A slug some root already holds is registered there, so a run against an
        existing node never opens a second copy of it under the first root.

        slug: the blueprint directory name under one of the blueprint roots.
        claim: the claim to ensure exists, when `argv` supplies its command.
        argv: the command tokens to register for a claim not yet in the manifest.
        """
        home = self.nodes.directory(slug).parent
        return Blueprint.register(home, slug=slug, claim=claim, argv=argv)

    async def run(
        self,
        slug: Slug,
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
        house idiom, so hyphenated tokens like `python -c ...` pass through
        verbatim on the CLI; put `--seed` and `--timeout` before the command,
        and separate a command that itself takes those flags with `--`.

        slug: the blueprint directory name, created when missing.
        claim: the claim name, registered with this command when new.
        argv: the command tokens to execute through the runner.
        seed: RNG seed to record when the command used one.
        timeout: hard wall-clock cap in seconds, stamped as exit 124 on expiry.
        """
        blueprint = self.register(slug, claim=claim, argv=list(argv))
        certificate = await self.running.attempted(blueprint, claim, seed=seed, timeout=timeout)
        EvidenceStore(blueprint.directory).append(certificate)
        return certificate
