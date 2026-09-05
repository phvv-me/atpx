import os
import stat
import sys
from pathlib import Path
from typing import Protocol


class ScriptFactory(Protocol):
    """Build one test executable on the host platform."""

    def __call__(self, name: str, *, output: str | None = None, forever: bool = False) -> Path: ...


def script(
    directory: Path,
    name: str,
    *,
    output: str | None = None,
    forever: bool = False,
) -> Path:
    """Write a Python-backed test executable and return its platform-native path."""
    if (output is None) == (not forever):
        raise ValueError("a test script needs exactly one of output or forever")
    program = (
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "if len(sys.argv) > 1:\n"
        "    Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
        "while True:\n"
        "    pass"
        if forever
        else (
            "from pathlib import Path\n"
            "import sys\n"
            f"print({output!r}.format(args=' '.join(sys.argv[1:]), cwd=Path.cwd()))"
        )
    )
    if os.name == "nt":
        source = directory / f".{name}.py"
        source.write_text(program + "\n", encoding="utf-8")
        path = directory / f"{name}.cmd"
        path.write_text(f'@"{sys.executable}" "{source}" %*\n', encoding="utf-8")
        return path
    path = directory / name
    path.write_text(f"#!{sys.executable}\n{program}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path
