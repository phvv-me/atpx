from enum import StrEnum


class Severity(StrEnum):
    """How badly one judgment cut, the four words every referee in this house rules under.

    Uppercase because that is how the referees write it, in the prose files and in the
    journal lines alike, and a machine-checkable record that spelled it differently
    would be a second vocabulary rather than the same one made readable.
    """

    FATAL = "FATAL"
    GAP = "GAP"
    MINOR = "MINOR"
    NONE = "NONE"
