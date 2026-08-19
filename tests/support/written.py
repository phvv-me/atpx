import tempfile
from pathlib import Path

from atpx import Node


def written(text: str) -> Node:
    """A node written under a throwaway blueprint directory named `note`."""
    path = Path(tempfile.mkdtemp()) / "note" / "node.md"
    path.parent.mkdir()
    path.write_text(text)
    return Node(path)
