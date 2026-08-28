from enum import StrEnum, auto


class Stance(StrEnum):
    """What one settled word does to the prediction behind it, declared per word.

    A vocabulary of only confirmations and refutations forces every reading into one of
    the two, and a program whose subject is numeric noise then rounds an inconclusive
    separation into a decisive word. `neither` is the honest third position and it is
    the DEFAULT, so a workspace that never thinks about stance is never recorded as
    having claimed anything.
    """

    CONFIRMS = auto()
    REFUTES = auto()
    NEITHER = auto()
