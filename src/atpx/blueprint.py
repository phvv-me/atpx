import shlex
import shutil
import tomllib
from collections.abc import Callable
from pathlib import Path

from pydantic import field_validator

from . import CONFIG
from .base import FrozenModel

REQUIREMENTS: dict[str, Callable[[], bool]] = {
    "cuda": lambda: shutil.which("nvidia-smi") is not None,
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
        """Lift bare command strings into claim tables."""
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
