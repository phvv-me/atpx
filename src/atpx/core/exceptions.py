class EvidenceError(RuntimeError):
    """Raised when a write would break the one-file-per-host append-only discipline."""
