from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from evaluation_harness.reporting.model import EvaluationSuiteReport
from evaluation_harness.reporting.renderers import (
    MAX_SERIALIZED_REPORT_BYTES,
    EvaluationJsonReportRenderer,
    EvaluationMarkdownReportRenderer,
)

_SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class EvaluationArtifactFormat(Enum):
    JSON = "JSON"
    MARKDOWN = "MARKDOWN"

    @property
    def media_type(self) -> str:
        return {
            EvaluationArtifactFormat.JSON: "application/json; charset=utf-8",
            EvaluationArtifactFormat.MARKDOWN: "text/markdown; charset=utf-8",
        }[self]


@dataclass(frozen=True, slots=True)
class EvaluationArtifactName:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str:
            raise TypeError("artifact name must be a string")
        if (
            not _SAFE_ARTIFACT_NAME.fullmatch(self.value)
            or ".." in self.value
            or "/" in self.value
            or "\\" in self.value
            or ":" in self.value
        ):
            raise ValueError("artifact name must be path-safe")


@dataclass(frozen=True, slots=True)
class EvaluationArtifact:
    name: EvaluationArtifactName
    format: EvaluationArtifactFormat
    content: bytes

    def __post_init__(self) -> None:
        if type(self.name) is not EvaluationArtifactName:
            raise TypeError("name must be an EvaluationArtifactName")
        if not isinstance(self.format, EvaluationArtifactFormat):
            raise TypeError("format must be an EvaluationArtifactFormat")
        if type(self.content) is not bytes:
            raise TypeError("content must be UTF-8 bytes")
        if not self.content or len(self.content) > MAX_SERIALIZED_REPORT_BYTES:
            raise ValueError("artifact content exceeds the canonical limit")
        self.content.decode("utf-8")

    @property
    def media_type(self) -> str:
        return self.format.media_type


class EvaluationArtifactFactory:
    def __init__(
        self,
        json_renderer: EvaluationJsonReportRenderer | None = None,
        markdown_renderer: EvaluationMarkdownReportRenderer | None = None,
    ) -> None:
        self._json_renderer = json_renderer or EvaluationJsonReportRenderer()
        self._markdown_renderer = (
            markdown_renderer or EvaluationMarkdownReportRenderer()
        )

    def create(
        self,
        report: EvaluationSuiteReport,
        name: EvaluationArtifactName,
        format: EvaluationArtifactFormat,
    ) -> EvaluationArtifact:
        if format is EvaluationArtifactFormat.JSON:
            content = self._json_renderer.render(report)
        elif format is EvaluationArtifactFormat.MARKDOWN:
            content = self._markdown_renderer.render(report)
        else:
            raise TypeError("format must be an EvaluationArtifactFormat")
        return EvaluationArtifact(name, format, content)


class EvaluationArtifactSinkPort(Protocol):
    def write(self, artifact: EvaluationArtifact) -> None: ...


class ArtifactDeliveryStatus(Enum):
    DELIVERED = "DELIVERED"
    ERROR = "ERROR"


class ArtifactDeliveryReasonCode(Enum):
    ARTIFACT_SINK_ERROR = "ARTIFACT_SINK_ERROR"


@dataclass(frozen=True, slots=True)
class ArtifactDeliveryResult:
    status: ArtifactDeliveryStatus
    reason_code: ArtifactDeliveryReasonCode | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ArtifactDeliveryStatus):
            raise TypeError("status must be an ArtifactDeliveryStatus")
        if self.status is ArtifactDeliveryStatus.DELIVERED:
            if self.reason_code is not None:
                raise ValueError("delivered artifact has no failure reason")
        elif self.reason_code is not ArtifactDeliveryReasonCode.ARTIFACT_SINK_ERROR:
            raise ValueError("failed delivery requires its closed reason")


class EvaluationArtifactDelivery:
    """Single-attempt sink delivery, isolated from evaluation results."""

    def deliver(
        self,
        artifact: EvaluationArtifact,
        sink: EvaluationArtifactSinkPort,
    ) -> ArtifactDeliveryResult:
        if type(artifact) is not EvaluationArtifact:
            raise TypeError("artifact must be an EvaluationArtifact")
        try:
            sink.write(artifact)
        except Exception:
            return ArtifactDeliveryResult(
                ArtifactDeliveryStatus.ERROR,
                ArtifactDeliveryReasonCode.ARTIFACT_SINK_ERROR,
            )
        return ArtifactDeliveryResult(ArtifactDeliveryStatus.DELIVERED)
