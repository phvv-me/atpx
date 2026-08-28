from collections.abc import Mapping

from atpx import Status

_REFUTATION = "Refutation condition. A demonstrated counterexample in scope refutes this."


def node_text(
    status: Status | str | None = Status.OPEN,
    *,
    date: str = "2026-06-10",
    summary: str = "",
    title: str = "Demo Node",
    body: str = "A claim using [[dep]].",
    refutation: str | None = _REFUTATION,
    evidence: str | None = "",
    heading: str = "## Evidence",
    front: Mapping[str, str] | None = None,
    log: str | None = "- [prover/start 2026-06-10] opened.",
) -> str:
    """Render a blueprint node file in the house contract shape from its parts.

    status: the frontmatter status, omitted when None.
    date: the frontmatter date.
    summary: the one-line summary, omitted when empty.
    title: the statement heading.
    body: the statement of record's prose.
    refutation: the explicit refutation condition line, omitted when None.
    evidence: the evidence section's body, the whole section omitted when None.
    heading: which spelling of the evidence section to render, `## Evidence` or `## Ledger`.
    front: extra frontmatter lines, `kind` or `judgments` say.
    log: the log section's body, the whole section omitted when None.
    """
    lines = [f"status: {Status(status).value}"] if status else []
    lines += [f"date: {date}"]
    lines += [f"summary: {summary}"] if summary else []
    lines += [f"{key}: {value}" for key, value in (front or {}).items()]
    head = "\n".join(["---", *lines, "---"])
    statement = "\n\n".join(filter(None, ["## Statement", body, refutation]))
    sections = [head, "#math #proof #ai-generated", f"# {title}", statement]
    if evidence is not None:
        sections += ["\n\n".join(filter(None, [heading, evidence]))]
    if log is not None:
        sections += [f"## Log    (append-only: [who/tag YYYY-MM-DD] one line)\n{log}"]
    return "\n\n".join(sections) + "\n"
