from __future__ import annotations

from evaluation_harness.reporting import EvaluationArtifact


class RecordingArtifactSink:
    def __init__(self, error: BaseException | None = None) -> None:
        self.error = error
        self.calls: list[EvaluationArtifact] = []

    def write(self, artifact: EvaluationArtifact) -> None:
        self.calls.append(artifact)
        if self.error is not None:
            raise self.error
