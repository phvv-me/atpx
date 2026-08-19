import sys


def announce(line: str) -> None:
    """Write one protocol or interpretation line to stdout, flushed immediately.

    The single console boundary outside the CLI: witness lines a gate audits
    and interpretation lines a verb owes its caller, flushed so they survive
    a crashing probe.

    line: the complete line to emit, without its trailing newline.
    """
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
