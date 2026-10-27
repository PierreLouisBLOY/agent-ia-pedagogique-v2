"""Bound partial text through the existing reader's LOCK and read-set rechecks."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, closed, money
from backend.adapters.outbound.persistence.p0_pilot_command_reader import (
    P0PilotCommandReader,
    ValidatedPilotCommandInspection,
)
from backend.core_contracts.outcome import ApplicationFailureKind
from backend.modules.work_orchestration.contracts.dto.p0_captured_partial import (
    CapturedPartial,
    CapturedPartialRequest,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionPortError,
    P1CampaignInspectionView,
)


class _BoundPartialReader(P0PilotCommandReader):
    def __init__(self, *, loader: Callable[[], ValidatedPilotCommandInspection],
                 binding: CapturedPartialRequest, clock: Callable[[], datetime]) -> None:
        super().__init__(loader=loader, profile_sha256=binding.profile_sha256, clock=clock)
        self.binding = binding
        self._text: str | None = None
        self.capture: CapturedPartial | None = None

    def _locked_read(self, loaded: ValidatedPilotCommandInspection) -> Mapping[str, object]:
        if (loaded.command_id != self.binding.command_id
                or loaded.profile_sha256 != self.binding.profile_sha256
                or loaded.recipe.get("request_sha256") != self.binding.request_sha256):
            raise ValueError("P0_CAPTURED_PARTIAL_BINDING")
        metadata = super()._locked_read(loaded)
        if self._text is None:
            raise ValueError("P0_CAPTURED_PARTIAL_NOT_AVAILABLE")
        self.capture = CapturedPartial(self.binding, self._text,
            P1CampaignInspectionView.from_mapping(metadata))
        return metadata

    def _receipts(self, loaded: ValidatedPilotCommandInspection, *, slot: Mapping[str, object],
            observations: dict[Path, tuple[Path, str]],
            absent_paths: list[tuple[Path, Path]], include_diagnostic: bool
            ) -> tuple[list[dict[str, object]], str | None, dict[str, object] | None, dict[str, object]]:
        result = super()._receipts(loaded, slot=slot, observations=observations,
            absent_paths=absent_paths, include_diagnostic=include_diagnostic)
        rows, status, _, _ = result
        pins = {str(row["state"]): str(row["sha256"]) for row in rows}
        if (status != "incomplete" or pins.get("RESULT") != self.binding.result_sha256
                or "RESPONSE_CAPTURED" not in pins):
            raise ValueError("P0_CAPTURED_PARTIAL_NOT_AVAILABLE")
        namespace = str(slot["namespace_sha256"])
        artifact, _ = self._read(loaded.receipt_root,
            loaded.receipt_root / f"{namespace}.RESULT.json", observations,
            expected=self.binding.result_sha256)
        witness, _ = self._read(loaded.receipt_root,
            loaded.receipt_root / f"{namespace}.RESPONSE_CAPTURED.json", observations,
            expected=pins["RESPONSE_CAPTURED"])
        closed(witness, {"schema", "grant_sha256", "request_sha256", "preflight_sha256",
            "namespace_sha256", "state", "timestamp_utc", "provider_attempts", "response_status",
            "response_artifact_sha256", "usage", "reserved_usd", "observed_cost_status"},
            "P0_CAPTURED_PARTIAL_WITNESS_FIELDS")
        if (witness.get("response_artifact_sha256") != self.binding.result_sha256
                or witness.get("response_status") != "incomplete"
                or type(witness.get("provider_attempts")) is not int
                or witness.get("provider_attempts") != 1
                or witness.get("observed_cost_status") != "NOT_ESTABLISHED"
                or money(witness.get("reserved_usd")) != money(slot["reserved_usd"])
                or canonical(witness.get("usage")) != canonical(artifact["usage"])
                or any(witness.get(key) != slot[key] for key in (
                    "namespace_sha256", "grant_sha256", "request_sha256", "preflight_sha256"))
                or artifact["request_sha256"] != self.binding.request_sha256
                or type(artifact["output_text"]) is not str):
            raise ValueError("P0_CAPTURED_PARTIAL_WITNESS_CHANGED")
        self._text = artifact["output_text"]
        return result


class P0CapturedPartialReader:
    def __init__(self, *, loader: Callable[[], ValidatedPilotCommandInspection],
                 binding: CapturedPartialRequest, clock: Callable[[], datetime]) -> None:
        self.loader, self.binding, self.clock = loader, binding, clock

    def read(self, request: CapturedPartialRequest) -> CapturedPartial:
        if request != self.binding:
            raise P1CampaignInspectionPortError(ApplicationFailureKind.AF_MAPPING_CORRUPTION)
        # A fresh internal reader per invocation prevents text leaking between calls.
        reader = _BoundPartialReader(loader=self.loader, binding=self.binding, clock=self.clock)
        reader.inspect(inspection_ref="p1-inspection:" + self.binding.profile_sha256,
            expected_plan_or_profile_sha256=self.binding.profile_sha256)
        # Returned only after the base reader's final validation and LOCK exit.
        if reader.capture is None:
            raise P1CampaignInspectionPortError(ApplicationFailureKind.AF_MAPPING_CORRUPTION)
        return reader.capture
