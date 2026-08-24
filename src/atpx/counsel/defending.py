import ast

from ..core.certificate import Certificate
from .probing import judged, measured, transcript

_GRAMMAR = {"case", "measured", "target", "diff"}


def rebutted(source: str, certificate: Certificate, *, attack: str) -> str:
    """Why one defense run does not count, empty when it rebuts through the defense gate.

    Beyond `judged`, a rebuttal must be unable to exit 0 from a failure
    handler and must re-measure every quantity the attack named, so a probe
    that survives its own crash, or measures beside the attack, never counts.

    source: the defense probe source.
    certificate: the defense run's certificate.
    attack: the demonstrated attack output the defense answered.
    """
    violation = judged(source, certificate)
    if violation:
        return violation
    return fallback(source) or covered(transcript(certificate), attack=attack) or ""


def covered(stdout: str, *, attack: str) -> str | None:
    """Why the defense's named cases miss the attack's targets, None when each is measured.

    stdout: the defense probe's captured output.
    attack: the demonstrated attack output the defense answered.
    """
    missing = sorted(targets(attack) - cases(stdout))
    if missing:
        return (
            f"the defense never measures {', '.join(missing)}, every quantity the "
            "attack names must reappear as a `case=<name>` measured line"
        )
    return None


def fallback(source: str) -> str | None:
    """Why the probe's success exit is untrustworthy, None when no handler can exit 0.

    A probe that catches its own failure and still exits 0 launders a broken
    run into a win, so inside an `except` handler every `sys.exit` must name a
    constant nonzero status.
    """
    handlers = (
        node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ExceptHandler)
    )
    calls = (
        node
        for handler in handlers
        for node in ast.walk(handler)
        if isinstance(node, ast.Call) and _is_exit(node) and not _is_failing(node)
    )
    if next(calls, None) is not None:
        return (
            "an except handler may exit 0, letting a failed measurement count "
            "as a rebuttal, every fallback exit must be nonzero"
        )
    return None


def targets(stdout: str) -> set[str]:
    """Every quantity a probe's measured lines name.

    A `case=<name>` token names its value and any other `name=value` token
    names its key, while the measurement grammar words themselves never count
    as quantities.
    """
    tokens = (token for line in measured(stdout) for token in line.split())
    return {name for name in map(_quantity, tokens) if name}


def cases(stdout: str) -> set[str]:
    """Every case a probe's measured lines name through `case=<name>` tokens."""
    return {
        token.removeprefix("case=")
        for line in measured(stdout)
        for token in line.split()
        if token.startswith("case=")
    }


def _quantity(token: str) -> str:
    """The quantity one `name=value` token names, empty for grammar or prose tokens."""
    name, sep, value = token.partition("=")
    if not sep:
        return ""
    if name == "case":
        return value
    return name if name.isidentifier() and name not in _GRAMMAR else ""


def _is_exit(call: ast.Call) -> bool:
    """Whether one call expression is a `sys.exit` invocation."""
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "exit"
        and isinstance(func.value, ast.Name)
        and func.value.id == "sys"
    )


def _is_failing(call: ast.Call) -> bool:
    """Whether an exit call names a constant status that cannot be success."""
    head = call.args[0] if call.args else None
    return isinstance(head, ast.Constant) and bool(head.value)
