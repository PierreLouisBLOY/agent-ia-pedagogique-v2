from __future__ import annotations

from threading import Event, Lock


class BoundedCollectingTextWriter:
    def __init__(self, max_records: int = 1_024) -> None:
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        self._max_records = max_records
        self._records: list[str] = []
        self._lock = Lock()

    @property
    def records(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._records)

    def write(self, record: str) -> int:
        with self._lock:
            if len(self._records) >= self._max_records:
                raise RuntimeError("bounded writer rejected record")
            self._records.append(record)
            return len(record)


class FailingTextWriter:
    def __init__(self, message: str = "writer failure") -> None:
        self.calls = 0
        self._message = message

    def write(self, record: str) -> int:
        self.calls += 1
        raise RuntimeError(self._message)


class PartialTextWriter:
    def __init__(self) -> None:
        self.calls = 0

    def write(self, record: str) -> int:
        self.calls += 1
        return max(0, len(record) - 1)


class FailAfterTextWriter:
    def __init__(self, successful_writes: int) -> None:
        if type(successful_writes) is not int or successful_writes < 0:
            raise ValueError("successful_writes must be a non-negative integer")
        self._successful_writes = successful_writes
        self.records: list[str] = []
        self.calls = 0

    def write(self, record: str) -> int:
        self.calls += 1
        if len(self.records) >= self._successful_writes:
            raise RuntimeError("planned writer failure")
        self.records.append(record)
        return len(record)


class CoordinatedTextWriter:
    """Test-only bounded wait used to observe non-blocking concurrent flush."""

    def __init__(self) -> None:
        self.entered = Event()
        self.release = Event()
        self.calls = 0

    def write(self, record: str) -> int:
        self.calls += 1
        self.entered.set()
        if not self.release.wait(timeout=5):
            raise RuntimeError("test writer coordination timeout")
        return len(record)
