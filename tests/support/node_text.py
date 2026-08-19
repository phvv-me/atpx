from atpx import Status


def node_text(
    status: Status | str | None = Status.OPEN,
    *,
    date: str = "2026-06-10",
    summary: str = "",
    title: str = "Demo Node",
    body: str = "A claim using [[dep]].",
    log: str | None = "- [prover/start 2026-06-10] opened.",
) -> str:
    """Render a blueprint node file in the house format from its parts."""
    front = [f"status: {Status(status).value}"] if status else []
    front += [f"date: {date}"]
    front += [f"summary: {summary}"] if summary else []
    head = "\n".join(["---", *front, "---"])
    sections = [head, "#math #proof #ai-generated", f"# {title}", body]
    if log is not None:
        sections += [f"## Log    (append-only: [who/tag YYYY-MM-DD] one line)\n{log}"]
    return "\n\n".join(sections) + "\n"
