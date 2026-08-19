from datetime import UTC, datetime

from patos import FrozenModel
from pydantic import ConfigDict, Field, field_validator


class LogEntry(FrozenModel):
    """One append-only journal line, `- [who/tag date] message`, validated to round-trip.

    The field constraints mirror the journal parser in `Node.log`, so any
    entry this model accepts is an entry the parser reads back: a `who` with
    spaces or a message holding a line break is refused at write time instead
    of silently vanishing from every later read of the log. The patterns
    compile on Python's `re` so acceptance matches the parser exactly,
    character class semantics included.
    """

    model_config = ConfigDict(regex_engine="python-re")

    who: str = Field(pattern=r"^\w+$")
    tag: str = Field(pattern=r"^[\w.-]+$")
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    message: str

    def __str__(self) -> str:
        return f"- [{self.who}/{self.tag} {self.date}] {self.message}"

    @field_validator("message")
    @classmethod
    def one_line(cls, value: str) -> str:
        """Refuse messages that would break the one-line journal format."""
        if "".join(value.splitlines()) != value:
            raise ValueError("a journal message must stay on one line")
        return value

    @classmethod
    def today(cls, *, who: str, tag: str, message: str) -> LogEntry:
        """A validated entry dated today in UTC, the same clock certificates stamp.

        who: free-form author label, one word.
        tag: the strategy or pass tag inside the brackets.
        message: the one-line entry body.
        """
        return cls(who=who, tag=tag, date=datetime.now(UTC).date().isoformat(), message=message)
