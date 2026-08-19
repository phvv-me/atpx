from collections.abc import Iterable, Sequence
from typing import overload


class FakeFrame:
    """The slice of the pandas frame surface the fit lane touches."""

    def __init__(
        self, columns: Sequence[str], rows: Sequence[Sequence[float]] | None = None
    ) -> None:
        """columns: the column names, target included.

        rows: the row values, a small two-row default when omitted.
        """
        self.columns = list(columns)
        self.rows = [list(row) for row in rows] if rows is not None else [[1.0, 2.0], [3.0, 4.0]]
        self.index = list(range(len(self.rows)))

    @overload
    def __getitem__(self, key: str) -> list[float]: ...

    @overload
    def __getitem__(self, key: list[str]) -> FakeFrame: ...

    def __getitem__(self, key: str | list[str]) -> list[float] | FakeFrame:
        if isinstance(key, str):
            place = self.columns.index(key)
            return [row[place] for row in self.rows]
        return FakeFrame(key, self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def drop(self, index: Iterable[int]) -> FakeFrame:
        return FakeFrame(self.columns, self.rows)

    def nlargest(self, count: int, column: str) -> FakeFrame:
        place = self.columns.index(column)
        ordered = sorted(self.rows, key=lambda row: row[place], reverse=True)
        return FakeFrame(self.columns, ordered[:count])

    def sample(self, *, n: int, random_state: int) -> FakeFrame:
        return FakeFrame(self.columns, self.rows[:n])
