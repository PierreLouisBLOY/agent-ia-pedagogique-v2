from __future__ import annotations

from threading import Lock
from typing import Protocol, TextIO, runtime_checkable


@runtime_checkable
class TextRecordWriter(Protocol):
    """Injected synchronous writer for one complete text record."""

    def write(self, record: str) -> int: ...


class StreamTextRecordWriter:
    """Thread-safe adapter around an injected text stream; never owns its path."""

    def __init__(self, stream: TextIO) -> None:
        if not callable(getattr(stream, "write", None)):
            raise TypeError("stream must provide write(record)")
        self._stream = stream
        self._lock = Lock()

    def write(self, record: str) -> int:
        if type(record) is not str:
            raise TypeError("record must be a string")
        with self._lock:
            return self._stream.write(record)
