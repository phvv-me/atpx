import re
import shlex
import shutil
import tomllib
from collections.abc import Callable
from pathlib import Path

from pydantic import JsonValue, field_validator

from . import CONFIG
from .base import FrozenModel

REQUIREMENTS: dict[str, Callable[[], bool]] = {
    "cuda": lambda: shutil.which("nvidia-smi") is not None,
}

BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def satisfied(requirement: str) -> bool:
    """Whether this host meets a claim requirement, `cuda` meaning an NVIDIA driver on PATH.

    requirement: a key of the requirement vocabulary, unknown keys raise with the known ones.
    """
    try:
        probe = REQUIREMENTS[requirement]
    except KeyError:
        known = ", ".join(sorted(REQUIREMENTS))
        message = f"unknown requirement {requirement!r}; known requirements are {known}"
        raise KeyError(message) from None
    return probe()


class Claim(FrozenModel):
    """One runnable claim: a command template plus an optional host requirement.

    In `atpx.toml` a claim is either a bare command string or a table with
    `command` and `requires`; the runner skips gracefully when the requirement
    is not met on this host instead of failing the claim.
    """

    command: str
    requires: str | None = None


class Blueprint(FrozenModel):
    """A blueprint directory's claim manifest, mapping claim names to runnable commands."""

    slug: str
    directory: Path
    zettel: str
    claims: dict[str, Claim]

    @field_validator("claims", mode="before")
    @classmethod
    def coerce_commands(cls, value: dict[str, str | dict[str, str]]) -> dict[str, dict[str, str]]:
        """Lift bare command strings into claim tables, refusing a non-table cleanly."""
        if not isinstance(value, dict):
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
        config = directory / CONFIG
        if not config.exists():
            raise FileNotFoundError(f"no blueprint {directory.name!r} at {directory}")
        manifest = tomllib.loads(config.read_text())
        return cls(
            slug=directory.name,
            directory=directory,
            zettel=manifest["zettel"],
            claims=manifest["claims"],
        )

    def claim(self, name: str) -> Claim:
        """The claim called `name`, raising with the known names on a miss."""
        try:
            return self.claims[name]
        except KeyError:
            known = ", ".join(sorted(self.claims))
            message = f"{self.slug} has no claim {name!r}; known claims are {known}"
            raise KeyError(message) from None

    def command(self, claim: str, root: Path) -> list[str]:
        """The argv for one claim, with `{dir}` expanded to the blueprint directory.

        claim: the claim name declared in `atpx.toml`.
        root: the workspace root the command runs from.
        """
        relative = self.directory.relative_to(root).as_posix()
        return shlex.split(self.claim(claim).command.format(dir=relative))


def register(blueprints: Path, slug: str, claim: str, argv: list[str] | None = None) -> Blueprint:
    """Load a blueprint under `blueprints`, creating directory, manifest, or claim as needed.

    The capture-first entry: a new slug gets a directory and manifest, a new
    claim gets its command recorded on first use, and an existing manifest keeps
    every table it already holds. Slugs and claims are single path segments,
    since a slash would desynchronize certificate ids from the directory name.

    blueprints: the blueprints root directory.
    slug: the blueprint directory name under it.
    claim: the claim to ensure exists, when `argv` supplies its command.
    argv: the command tokens to register for a claim not yet in the manifest.
    """
    if "/" in slug or "/" in claim:
        raise ValueError(f"slugs and claims are single path segments, got {slug!r} / {claim!r}")
    directory = blueprints / slug
    manifest = directory / CONFIG
    recorded: dict[str, JsonValue] = (
        tomllib.loads(manifest.read_text()) if manifest.exists() else {"zettel": slug}
    )
    claims = recorded.setdefault("claims", {})
    fresh = not manifest.exists()
    if argv and isinstance(claims, dict) and claim not in claims:
        claims[claim] = shlex.join(argv)
        fresh = True
    if fresh:
        directory.mkdir(parents=True, exist_ok=True)
        manifest.write_text(manifest_text(recorded))
    return Blueprint.load(directory)


def manifest_text(recorded: dict[str, JsonValue]) -> str:
    """Serialize a blueprint manifest back to TOML, round-tripping through `tomllib`.

    Scalar keys come first, then one `[table]` per dict value with its own
    scalars and one `[table.sub]` per nested dict, the manifest's natural
    shape (`zettel`, `[claims]`, `[claims.name]`). Deeper nesting falls back
    to inline tables.

    recorded: the manifest structure, `zettel` plus a `claims` table.
    """
    scalars = {key: value for key, value in recorded.items() if not isinstance(value, dict)}
    tables = {key: value for key, value in recorded.items() if isinstance(value, dict)}
    lines = [f"{toml_key(key)} = {toml_value(value)}" for key, value in scalars.items()]
    for name, table in tables.items():
        entries = {key: value for key, value in table.items() if not isinstance(value, dict)}
        subtables = {key: value for key, value in table.items() if isinstance(value, dict)}
        lines += ["", f"[{toml_key(name)}]"]
        lines += [f"{toml_key(key)} = {toml_value(value)}" for key, value in entries.items()]
        for subname, subtable in subtables.items():
            lines += ["", f"[{toml_key(name)}.{toml_key(subname)}]"]
            lines += [f"{toml_key(key)} = {toml_value(value)}" for key, value in subtable.items()]
    return "\n".join(lines) + "\n"


def toml_key(name: str) -> str:
    """`name` as a TOML key, bare when possible and quoted otherwise."""
    return name if BARE_KEY.match(name) else toml_string(name)


def toml_string(text: str) -> str:
    """`text` as a quoted TOML basic string, control characters escaped.

    JSON escaping is close but not identical: TOML also forbids a raw DEL and
    raw C0 controls inside basic strings, so those become `\\uXXXX` here.
    """
    pieces = [
        ESCAPES.get(
            char, char if ord(char) >= 0x20 and ord(char) != 0x7F else f"\\u{ord(char):04X}"
        )
        for char in text
    ]
    return '"' + "".join(pieces) + '"'


def toml_value(value: JsonValue) -> str:
    """`value` as a TOML literal; the manifest carries strings, numbers, arrays, tables."""
    match value:
        case bool():
            return "true" if value else "false"
        case str():
            return toml_string(value)
        case int() | float():
            return repr(value)
        case list():
            return "[" + ", ".join(toml_value(item) for item in value) + "]"
        case dict():
            entries = ", ".join(f"{toml_key(k)} = {toml_value(v)}" for k, v in value.items())
            return "{" + entries + "}"
        case _:
            raise ValueError(f"TOML cannot hold {value!r} in a manifest")
