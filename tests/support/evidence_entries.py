import json
from pathlib import Path


def evidence_entries(blueprint: Path):
    """Parsed entries of every evidence file under a blueprint, untyped for free indexing."""
    files = sorted((blueprint / "evidence").glob("*.json"))
    return [entry for f in files for entry in json.loads(f.read_text())]
