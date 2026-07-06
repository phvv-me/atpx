from pathlib import Path

from pydantic import JsonValue

from . import CONFIG
from .evidence import EvidenceStore
from .zettel import Vault


class DoctorReport:
    """What needs repair: invalid statuses, stray evidence, missing manifests.

    The lint the tolerant readers rely on. Reports and never mutates.
    """

    def __init__(self, vault: Vault, blueprints: Path, root: Path) -> None:
        """vault: the zettel graph whose statuses are linted.

        blueprints: the blueprints root directory.
        root: the workspace root paths report relative to.
        """
        self.vault = vault
        self.blueprints = blueprints
        self.root = root

    def compiled(self) -> dict[str, JsonValue]:
        """The full report, one key per lint."""
        return {
            "invalid_statuses": self.invalid_statuses(),
            "stray_evidence": self.stray_evidence(),
            "unmanifested_blueprints": self.unmanifested(),
            "dangling_blueprints": self.dangling(),
        }

    def invalid_statuses(self) -> dict[str, JsonValue]:
        """Nodes carrying a status string outside the lifecycle ladder."""
        return {node.name: node.raw_status for node in self.vault.nodes() if node.status is None}

    def stray_evidence(self) -> dict[str, JsonValue]:
        """Files under `evidence/` that are not certificate ledgers, per blueprint."""
        return {
            directory.name: [str(path.relative_to(self.root)) for path in stray]
            for directory in sorted(self.blueprints.iterdir())
            if directory.is_dir() and (stray := EvidenceStore.strays(directory))
        }

    def unmanifested(self) -> list[JsonValue]:
        """Blueprint directories without a claim manifest."""
        return list[JsonValue](
            sorted(
                directory.name
                for directory in self.blueprints.iterdir()
                if directory.is_dir() and not (directory / CONFIG).exists()
            )
        )

    def dangling(self) -> dict[str, JsonValue]:
        """Nodes whose `blueprint` frontmatter points at a directory that does not exist."""
        return {
            node.name: node.blueprint
            for node in self.vault.nodes()
            if node.blueprint and not (self.root / node.blueprint).is_dir()
        }
