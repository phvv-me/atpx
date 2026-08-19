from .exceptions import EvidenceError
from .provenance import Provenance
from .repository import Repository

git_revision = Provenance.git_revision
short_hostname = Provenance.short_hostname

__all__ = [
    "EvidenceError",
    "Repository",
    "git_revision",
    "short_hostname",
]
