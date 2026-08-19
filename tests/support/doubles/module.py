import types
from collections.abc import Callable

from .frame import FakeFrame
from .regressor import FakeRegressor


class FakeModule(types.ModuleType):
    """A stand-in for an optional dependency, its attributes fixed at construction."""

    def __init__(
        self,
        name: str,
        **attributes: str | type[FakeRegressor] | Callable[[str], FakeFrame],
    ) -> None:
        """name: the module name the fake answers to in `sys.modules`.

        attributes: the module attributes the code under test reaches for.
        """
        super().__init__(name)
        for attribute, value in attributes.items():
            setattr(self, attribute, value)
