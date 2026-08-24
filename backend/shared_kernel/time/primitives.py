from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class Instant:
    """A timezone-aware point in time supplied by a caller."""

    value: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.value, datetime):
            raise TypeError("value must be a datetime")
        if self.value.tzinfo is None or self.value.utcoffset() is None:
            raise ValueError("Instant requires a timezone-aware datetime")


@dataclass(frozen=True, slots=True)
class BusinessDate:
    """A calendar date without clock or timezone policy."""

    value: date

    def __post_init__(self) -> None:
        if not isinstance(self.value, date) or isinstance(self.value, datetime):
            raise TypeError("value must be a date, not a datetime")
