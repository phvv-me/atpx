import shlex
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path

import tomlkit
from patos import FrozenModel
from pydantic import field_validator
from rapidfuzz import process
from tomlkit import TOMLDocument

from ..support.naming import Naming
from .claim import Claim


class Blueprint(FrozenModel):
    """A blueprint directory's claim manifest, mapping claim names to runnable commands.

    Node identity is the directory name itself; unknown top-level keys in an
    old manifest are tolerated on load and simply ignored.
    """

    slug: str
    directory: Path
    claims: dict[str, Claim]

    @field_validator("claims", mode="before")
    @classmethod
    def coerce_commands(
        cls, value: Mapping[str, str | dict[str, str]]
    ) -> dict[str, dict[str, str]]:
        """Lift bare command strings into claim tables, refusing a non-table cleanly."""
        if not isinstance(value, Mapping):
            raise ValueError(f"claims must be a table of commands, got {value!r}")
        return {
            name: {"command": claim} if isinstance(claim, str) else claim
            for name, claim in value.items()
        }

    @classmethod
    def load(cls, directory: Path) -> Blueprint:
        """Read the claim manifest (the tool's own `<name>.toml`) from a blueprint directory.

        directory: the `research/math/<slug>` directory.
        """
        config = directory / Naming.CONFIG
        if not config.exists():
            raise FileNotFoundError(f"no blueprint {directory.name!r} at {directory}")
        manifest = tomlkit.parse(config.read_text())
        return cls(slug=directory.name, directory=directory, claims=manifest.get("claims", {}))

    @classmethod
    def register(
        cls, blueprints: Path, *, slug: str, claim: str, argv: Sequence[str] | None = None
    ) -> Blueprint:
        """Load a blueprint under `blueprints`, creating directory, manifest, or claim as needed.

        The capture-first entry: a new slug gets a directory and manifest, and the
        manifest is a record of the latest run, so a scalar claim command is
        updated when a run supplies a different one (a stale pre-registered path
        must never shadow the command actually executing). Claim TABLES and every
        other table, comment, and formatting survive rewrites, since a human is
        free to hand-edit `atpx.toml` between runs and a table carries fields such
        as `requires` that a run command cannot express. Slugs and claims are
        single path segments, since a slash would desynchronize certificate ids
        from the directory name.

        blueprints: the blueprints root directory.
        slug: the blueprint directory name under it.
        claim: the claim to ensure exists, when `argv` supplies its command.
        argv: the command tokens this run executes for the claim.
        """
        if "/" in slug or "/" in claim:
            raise ValueError(
                f"slugs and claims are single path segments, got {slug!r} / {claim!r}"
            )
        directory = blueprints / slug
        manifest = directory / Naming.CONFIG
        recorded = cls.__read(manifest)
        claims = recorded.setdefault("claims", {})
        fresh = not manifest.exists()
        if argv and isinstance(claims, MutableMapping):
            command = shlex.join(argv)
            recorded_command = claims.get(claim)
            stale_scalar = isinstance(recorded_command, str) and recorded_command != command
            if claim not in claims or stale_scalar:
                claims[claim] = command
                fresh = True
        if fresh:
            cls.__persist(directory, recorded)
        return cls(slug=slug, directory=directory, claims=claims)

    def claim(self, name: str) -> Claim:
        """The claim called `name`, raising with a close-match hint and known names on a miss."""
        try:
            return self.claims[name]
        except KeyError:
            raise KeyError(
                f"{self.slug} has no claim {name!r}; {self.__suggestion(name)}"
            ) from None

    def command(self, claim: str) -> list[str]:
        """The argv for one claim, with `{dir}` expanded to the blueprint directory's full path.

        Absolute rather than workspace-relative, because the launcher a workspace declares
        decides the working directory a claim actually runs from (`mainboard run` changes
        into its own workspace root, which in a monorepo sits above a nested atpx
        workspace), and only a full path survives that. The template stored in `atpx.toml`
        stays machine-independent; the expansion is per-run.

        claim: the claim name declared in `atpx.toml`.
        """
        return shlex.split(self.claim(claim).command.format(dir=self.directory))

    @staticmethod
    def __persist(directory: Path, recorded: TOMLDocument) -> None:
        """Create the blueprint directory when needed and write its manifest back to disk."""
        directory.mkdir(parents=True, exist_ok=True)
        (directory / Naming.CONFIG).write_text(tomlkit.dumps(recorded))

    @staticmethod
    def __read(manifest: Path) -> TOMLDocument:
        """The manifest's parsed TOML document, empty when no manifest exists yet."""
        return tomlkit.parse(manifest.read_text()) if manifest.exists() else tomlkit.document()

    def __suggestion(self, name: str) -> str:
        """A close-match hint ahead of the known-claims roster, empty when nothing is close."""
        known = ", ".join(sorted(self.claims))
        match = process.extractOne(name, list(self.claims), score_cutoff=60)
        hint = f"did you mean {match[0]!r}? " if match else ""
        return f"{hint}known claims are {known}"
