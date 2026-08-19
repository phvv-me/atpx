import shutil
from collections.abc import Callable

from patos import FrozenModel

_REQUIREMENTS: dict[str, Callable[[], bool]] = {
    "cuda": lambda: shutil.which("nvidia-smi") is not None,
}


def is_satisfied(requirement: str) -> bool:
    """Whether this host meets a claim requirement, `cuda` meaning an NVIDIA driver on PATH.

    requirement: a key of the requirement vocabulary, unknown keys raise with the known ones.
    """
    try:
        probe = _REQUIREMENTS[requirement]
    except KeyError:
        raise KeyError(
            f"unknown requirement {requirement!r}; "
            f"known requirements are {', '.join(sorted(_REQUIREMENTS))}"
        ) from None
    return probe()


class Claim(FrozenModel):
    """One runnable claim: a command template plus an optional host requirement.

    In `atpx.toml` a claim is either a bare command string or a table with
    `command` and `requires`; the runner skips gracefully when the requirement
    is not met on this host instead of failing the claim.
    """

    command: str
    requires: str | None = None

    def is_runnable(self) -> bool:
        """Whether this host meets the claim's requirement, trivially true without one."""
        return self.requires is None or is_satisfied(self.requires)
