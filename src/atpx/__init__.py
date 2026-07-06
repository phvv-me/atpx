# The package name *is* the project name (the build maps pyproject -> this package),
# so a rename is a single move of the `src/atpx` folder. Every self-reference
# derives from it; reading pyproject.toml at runtime would be fragile (it isn't
# in the wheel). The constants precede the re-exports so submodules can import
# them while the package is still initializing.
NAME: str = __name__

# The manifest a user writes, both the workspace root marker and the blueprint claim map.
CONFIG: str = f"{NAME}.toml"

from .adversarial import (
    Rederivation,
    SeedSweep,
    boundary_ties,
    precision_tilt,
    rederive,
    seed_sensitivity,
)
from .blueprint import Blueprint, Claim
from .certificate import Certificate
from .engines import Capability, Engine, SearchError
from .evidence import EvidenceStore
from .roles import Status
from .settlement import SettleError
from .workspace import Workspace, workspace
from .zettel import Vault, Zettel

__all__ = [
    "CONFIG",
    "NAME",
    "Blueprint",
    "Capability",
    "Certificate",
    "Claim",
    "Engine",
    "EvidenceStore",
    "Rederivation",
    "SearchError",
    "SeedSweep",
    "SettleError",
    "Status",
    "Vault",
    "Workspace",
    "Zettel",
    "boundary_ties",
    "precision_tilt",
    "rederive",
    "seed_sensitivity",
    "workspace",
]
