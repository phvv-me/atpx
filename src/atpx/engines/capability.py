from enum import StrEnum, auto


class Capability(StrEnum):
    """The typed operations engines implement; v2 keeps only read-only search."""

    SEARCH = auto()
