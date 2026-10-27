"""Single in-memory HTTP follow-up, with no authority, retry or restart recovery."""
from __future__ import annotations

import copy
import re
import threading
from collections.abc import Callable, Mapping

_FIELDS = {"command_id", "preparation_ref", "preparation_sha256", "preview_sha256",
    "transfer_accepted", "cost_bound_accepted", "double_execution_cost_risk_accepted"}


class P0PilotCommandFollowup:
    """The existing Application command alone owns all business transitions."""

    def __init__(self, execute: Callable[[str, Mapping[str, object]], dict[str, object]], *,
                 normal: bool = False,
                 codesign: bool = False,
                 finite: bool = False,
                 retained_reader: Callable[[str], dict[str, object]] | None = None) -> None:
        if type(normal) is not bool or type(codesign) is not bool or type(finite) is not bool or sum((normal, codesign, finite)) > 1 or (retained_reader is not None and not (normal or finite)):
            raise ValueError("P0_NORMAL_FOLLOWUP_MODE_REQUIRED")
        self._execute = execute
        self._normal, self._retained_reader = normal, retained_reader
        self._codesign, self._finite = codesign, finite
        self._payload: dict[str, object] | None = None
        self._mutex = threading.Lock()
        self._command: str | None = None
        self._view: dict[str, object] | None = None
        self._worker: threading.Thread | None = None

    def start(self, payload: Mapping[str, object]) -> dict[str, object]:
        fields = _FIELDS - {"double_execution_cost_risk_accepted"} if self._normal else _FIELDS
        decisions = ("transfer_accepted", "cost_bound_accepted") if self._normal else (
            "transfer_accepted", "cost_bound_accepted", "double_execution_cost_risk_accepted")
        if self._codesign or self._finite:
            fields = {"command_id", "production_ref", "version_ref", "bundle_sha256", "direction", "objective", "evidence_query"}
            if self._finite:
                fields |= {"preview_sha256", "transfer_accepted", "cost_bound_accepted"}
                if (payload.get("transfer_accepted") is not True or payload.get("cost_bound_accepted") is not True
                        or re.fullmatch(r"[0-9a-f]{64}", str(payload.get("preview_sha256"))) is None):
                    raise ValueError("P0_CHAIN_EXACT_CONSENT_REQUIRED")
            if (set(payload) != fields or not isinstance(payload.get("command_id"), str)
                    or re.fullmatch(r"[0-9a-f]{32}", str(payload["command_id"])) is None
                    or any(not isinstance(payload.get(key), str) or re.fullmatch(prefix+r":[0-9a-f]{32}", str(payload[key])) is None
                        for key, prefix in (("production_ref", "prod"), ("version_ref", "ver")))
                    or not isinstance(payload.get("bundle_sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", str(payload["bundle_sha256"])) is None
                    or payload.get("direction") not in {"V2_TO_AI", "AI_TO_V2"}
                    or not isinstance(payload.get("objective"), str) or not str(payload["objective"]).strip() or len(str(payload["objective"])) > 2000
                    or payload.get("evidence_query") is not None and (not isinstance(payload["evidence_query"], str) or len(str(payload["evidence_query"])) > 256)):
                raise ValueError("P0_CODESIGN_REQUEST_REJECTED")
        elif (set(payload) != fields
            or not isinstance(payload.get("command_id"), str)
            or re.fullmatch(r"[0-9a-f]{32}", str(payload["command_id"])) is None
            or not isinstance(payload.get("preparation_ref"), str)
            or re.fullmatch(r"prep:[0-9a-f]{32}", str(payload["preparation_ref"])) is None
            or any(not isinstance(payload.get(key), str)
                or re.fullmatch(r"[0-9a-f]{64}", str(payload[key])) is None
                for key in ("preparation_sha256", "preview_sha256"))
            or any(payload.get(key) is not True for key in decisions)):
            raise ValueError("P1_PILOT_EXACT_CONSENT_REQUIRED")
        copied = copy.deepcopy(dict(payload))
        with self._mutex:
            if self._command is not None:
                if self._codesign or self._finite:
                    if copied != self._payload:
                        raise ValueError("P0_IDEMPOTENCY_CONFLICT")
                    assert self._view is not None
                    return copy.deepcopy(self._view)
                raise ValueError("P1_PILOT_COMMAND_ALREADY_SUBMITTED")
            self._command = str(copied["command_id"])
            if self._codesign or self._finite:
                self._payload = copied
            self._view = {"state": "LOCAL_COMMAND_RUNNING", "command_id": self._command}
            # Keep the claim even if thread creation fails. No silent second run.
            try:
                self._worker = threading.Thread(target=self._run, args=(copied,),
                    name="v2-pilot-final-command", daemon=True)
                self._worker.start()
            except Exception:
                self._view = {"state": "LOCAL_COMMAND_UNCERTAIN", "command_id": self._command,
                    "code": "P1_PILOT_FOLLOWUP_START_UNCONFIRMED"}
            return dict(self._view)

    def _run(self, payload: Mapping[str, object]) -> None:
        try:
            result = self._execute("codesign-consent" if self._finite else "codesign" if self._codesign else "consent_generate", payload)
            view: dict[str, object] = {"state": "LOCAL_COMMAND_COMPLETED",
                "command_id": payload["command_id"], "result": result}
            if self._finite and result.get("state") != "CODESIGN_CANDIDATE":
                view.update(state="LOCAL_COMMAND_UNCERTAIN", code="P0_CHAIN_LOCAL_RESULT_NOT_ACCEPTED")
        except Exception as error:
            # No exception proves no provider effect. The durable ledger is
            # separate; this volatile view cannot declare a refund or retry.
            view = {"state": "LOCAL_COMMAND_UNCERTAIN", "command_id": payload["command_id"],
                "code": "P1_PILOT_COMMAND_OUTCOME_INDETERMINATE"}
            if (self._normal or self._finite) and re.fullmatch(r"(?:P0|P1)_[A-Z0-9_]{1,80}", str(error)):
                view["code"] = str(error)
        with self._mutex:
            if self._view is not None:
                view.update({k:v for k,v in self._view.items() if k in {"phase", "evidence", "phases"}})
            if view["state"] == "LOCAL_COMMAND_COMPLETED":
                candidate_result = view.get("result")
                if isinstance(candidate_result, Mapping):
                    publication = candidate_result.get("publication")
                    if isinstance(publication, Mapping) and publication.get("state") == "APPLICATION_SAVED":
                        view["phase"] = "APPLICATION_SAVED"
                        view["evidence"] = {"record_sha256": publication["record_sha256"]}
            self._view = view

    def observe(self, phase: str, evidence: Mapping[str, object]) -> None:
        allowed = {"PREFLIGHT_RUNNING", "PREFLIGHT_CHECKED", "BUDGET_RESERVED", "RESERVED",
            "TRANSPORT_ENTERED", "RESPONSE_CAPTURED", "PARSED", "OUTCOME_UNCONFIRMED"}
        keys = {"preflight_sha256", "reserved_usd", "grant_sha256", "provider_attempts",
            "provider_arrival", "response_artifact_sha256", "response_status", "technical_code",
            "failure_stage", "outcome_marker"}
        if phase not in allowed or set(evidence) - keys:
            return
        if any(not (value is None or type(value) is int or
                    isinstance(value, str) and len(value) <= 160) for value in evidence.values()):
            return
        with self._mutex:
            if self._view is not None and self._view.get("state") == "LOCAL_COMMAND_RUNNING":
                prior = self._view.get("phases")
                history: list[object] = list(prior) if isinstance(prior, list) else []
                history.append({"phase": phase, "evidence": dict(evidence)})
                self._view.update(phase=phase, evidence=dict(evidence), phases=history[-16:])

    def handles(self, command_id: str) -> bool:
        with self._mutex:
            return self._command == command_id

    def read(self, command_id: str) -> dict[str, object]:
        if re.fullmatch(r"[0-9a-f]{32}", command_id) is None:
            raise ValueError("P1_PILOT_FOLLOWUP_IDENTITY_REQUIRED")
        with self._mutex:
            if command_id != self._command or self._view is None:
                value = None
            else:
                value = copy.deepcopy(self._view)
        if value is not None:
            if self._finite and self._retained_reader is not None and value.get("state") == "LOCAL_COMMAND_UNCERTAIN":
                retained = self._retained_reader(command_id)
                if retained.get("state") != "LOCAL_COMMAND_FOLLOWUP_UNAVAILABLE":
                    return retained
            if self._finite and value.get("state") == "LOCAL_COMMAND_RUNNING" and self._worker is not None and not self._worker.is_alive():
                # A dead worker is not proof of non-send or a reusable right.
                value = {"state":"LOCAL_COMMAND_UNCERTAIN", "command_id":command_id,
                    "code":"P0_CHAIN_WORKER_STOPPED_WITHOUT_RESULT", "retry":0}
                if self._retained_reader is not None:
                    retained = self._retained_reader(command_id)
                    if retained.get("state") != "LOCAL_COMMAND_FOLLOWUP_UNAVAILABLE":
                        return retained
            if self._finite and self._retained_reader is not None and value.get("state") == "LOCAL_COMMAND_RUNNING":
                durable = self._retained_reader(command_id)
                if durable.get("state") != "LOCAL_COMMAND_FOLLOWUP_UNAVAILABLE":
                    return {**value, **durable}
            return value
        if self._retained_reader is not None:
            return self._retained_reader(command_id)
        return {"state": "LOCAL_COMMAND_FOLLOWUP_UNAVAILABLE", "command_id": command_id}
