import json
from pathlib import Path


def evidence_entries(blueprint: Path):
    """Parsed entries of every evidence ledger under a blueprint, untyped for free indexing.

    Reads both formats the store reads, the NDJSON stream a line at a time and the
    pre-migration JSON array whole, so a test asserting on stored records never has
    to know which one the code under test wrote.
    """
    files = sorted((blueprint / "evidence").glob("*"))
    return [
        entry
        for file in files
        if file.suffix in (".json", ".ndjson")
        for entry in (
            [
                json.loads(line)
                for line in file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if file.suffix == ".ndjson"
            else json.loads(file.read_text(encoding="utf-8"))
        )
    ]
