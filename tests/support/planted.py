from pathlib import Path


def planted(blueprints: Path, slug: str, *, text: str, manifest: str = "[claims]\n") -> Path:
    """Write one blueprint directory with its `node.md` and manifest, returning the node path."""
    directory = blueprints / slug
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "atpx.toml").write_text(manifest)
    path = directory / "node.md"
    path.write_text(text)
    return path
