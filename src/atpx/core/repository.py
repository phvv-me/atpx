from pathlib import Path

from plumbum import CommandNotFound, ProcessExecutionError, local


class Repository:
    """The git history questions a workspace asks about its own files.

    root: a directory inside the repository.
    """

    def __init__(self, root: Path) -> None:
        self.git = local["git"]["-C", str(root)]

    def moved_since(self, revision: str, path: Path) -> bool:
        """Whether any commit after `revision` touched `path`.

        The staleness test evidence is judged by: a certificate stamped before the last
        commit that changed a node no longer certifies what the node now says. A `+dirty`
        suffix is dropped, since a dirty tree is a provenance flag the certificate already
        carries and not a commit. A certificate that recorded no revision at all is stale
        by definition, while a revision this checkout cannot resolve leaves the question
        unanswered rather than raising an alarm nobody can act on.

        revision: the revision the evidence was stamped at.
        path: the file or directory whose history is read.
        """
        base = revision.partition("+")[0]
        if not base or base == "unknown":
            return True
        try:
            return bool(self.git("log", "--oneline", f"{base}..HEAD", "--", str(path)).strip())
        except ProcessExecutionError, CommandNotFound:
            return False
