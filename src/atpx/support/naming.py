from typing import ClassVar


class Naming:
    """The package's self-derived names, so renaming the project is one folder move.

    The package name *is* the project name (the build maps pyproject onto this
    package); reading pyproject.toml at runtime would be fragile since it is
    not in the wheel, so every self-reference derives from the import system.
    """

    NAME: ClassVar[str] = str(__package__).partition(".")[0]
    CONFIG: ClassVar[str] = f"{NAME}.toml"
