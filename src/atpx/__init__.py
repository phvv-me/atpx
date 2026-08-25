from .adversarial.lattice import boundary_ties, precision_tilt
from .adversarial.rederiving import Rederivation, rederive
from .adversarial.sweep import SeedSweep, seed_sensitivity
from .blueprint.claim import Claim
from .blueprint.manifest import Blueprint
from .core.certificate import Certificate
from .core.evidence import EvidenceStore
from .counsel.consulting.openrouter import consult
from .counsel.probing import gate
from .counsel.prover import Prover
from .counsel.records.attempt import Attempt
from .counsel.records.referral import Referral
from .counsel.refuter import Refuter
from .engines import Capability, Engine, SearchError
from .graph.category import Category
from .graph.frontmatter import Frontmatter
from .graph.kind import Kind
from .graph.node import Node
from .graph.status import Status
from .graph.store import NodeStore
from .models.consultation import Consultation
from .models.lane import ModelLane
from .models.lanes import Lanes
from .rigor.witness import is_ball_witness
from .settlement.exceptions import SettleError
from .support.naming import Naming
from .workspace.verbs import Workspace, workspace


def __getattr__(name: str) -> str:
    """Resolve `NAME` and `CONFIG` from `Naming` lazily, PEP 562 style.

    Neither is a constant this module owns: both mirror `Naming`, the class
    that actually states them, so a module-level assignment would just be a
    second, driftable spelling of the same value.
    """
    if name in {"NAME", "CONFIG"}:
        return str(getattr(Naming, name))
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CONFIG",
    "NAME",
    "Attempt",
    "Blueprint",
    "Capability",
    "Category",
    "Certificate",
    "Claim",
    "Consultation",
    "Engine",
    "EvidenceStore",
    "Frontmatter",
    "Kind",
    "Lanes",
    "ModelLane",
    "Node",
    "NodeStore",
    "Prover",
    "Rederivation",
    "Referral",
    "Refuter",
    "SearchError",
    "SeedSweep",
    "SettleError",
    "Status",
    "Workspace",
    "boundary_ties",
    "consult",
    "gate",
    "is_ball_witness",
    "precision_tilt",
    "rederive",
    "seed_sensitivity",
    "workspace",
]
