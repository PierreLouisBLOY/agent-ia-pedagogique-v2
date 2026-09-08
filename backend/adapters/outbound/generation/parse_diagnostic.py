"""Private bounded parse observations; no content, persistence or business authority."""
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum


class ParseStage(StrEnum):
    ENVELOPE = "ENVELOPE"
    OUTPUT_EXTRACT = "OUTPUT_EXTRACT"
    TEXT_EXTRACT = "TEXT_EXTRACT"
    JSON_DECODE = "JSON_DECODE"
    SCHEMA_VALIDATE = "SCHEMA_VALIDATE"
    DOMAIN_MAP = "DOMAIN_MAP"


class ParseCode(StrEnum):
    RESPONSE_ENVELOPE_INVALID = "RESPONSE_ENVELOPE_INVALID"
    STRUCTURED_OUTPUT_MISSING = "STRUCTURED_OUTPUT_MISSING"
    OUTPUT_TEXT_MISSING = "OUTPUT_TEXT_MISSING"
    JSON_DECODE_FAILURE = "JSON_DECODE_FAILURE"
    SCHEMA_VALIDATION_FAILURE = "SCHEMA_VALIDATION_FAILURE"
    REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    ENUM_INVALID = "ENUM_INVALID"
    CARDINALITY_INVALID = "CARDINALITY_INVALID"
    DOMAIN_MAPPING_FAILURE = "DOMAIN_MAPPING_FAILURE"
    UNCLASSIFIED_PARSE_FAILURE = "UNCLASSIFIED_PARSE_FAILURE"


class ParseStatus(StrEnum):
    STARTED = "STARTED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    UNKNOWN = "UNKNOWN"


class ParseDiagnostic:
    """One attempt, first failure wins; never retains inputs or exception objects."""

    __slots__ = ("_enabled", "_stage", "_code", "_status")

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._stage = ParseStage.ENVELOPE
        self._code: ParseCode | None = None
        self._status = ParseStatus.UNKNOWN

    def begin(self, stage: ParseStage) -> None:
        if type(stage) is not ParseStage:
            raise TypeError("PARSE_STAGE_CLOSED")
        if self._enabled and self._status is not ParseStatus.FAILED:
            self._stage, self._status = stage, ParseStatus.STARTED

    def fail(self, code: ParseCode) -> None:
        if type(code) is not ParseCode:
            raise TypeError("PARSE_CODE_CLOSED")
        if self._enabled and self._status is not ParseStatus.FAILED:
            self._code, self._status = code, ParseStatus.FAILED

    @contextmanager
    def capture(self) -> Iterator[None]:
        try:
            yield
        except Exception:
            self.fail(ParseCode.UNCLASSIFIED_PARSE_FAILURE)
            raise
        else:
            if self._enabled and self._status is ParseStatus.STARTED:
                self._status = ParseStatus.COMPLETED

    @contextmanager
    def at(self, stage: ParseStage, *, expected: tuple[type[Exception], ...] = (),
           code: ParseCode = ParseCode.UNCLASSIFIED_PARSE_FAILURE) -> Iterator[None]:
        self.begin(stage)
        try:
            yield
        except expected:
            self.fail(code)
            raise
        except Exception:
            self.fail(ParseCode.UNCLASSIFIED_PARSE_FAILURE)
            raise

    def snapshot(self) -> dict[str, str | None]:
        return {
            "parse_stage": self._stage.value,
            "parse_code": self._code.value if self._code is not None else None,
            "parse_status": self._status.value,
            "schema_target": "PREPARE_SUPPLEMENTS_V1",
        }
