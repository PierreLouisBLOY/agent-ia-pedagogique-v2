"""Finite-effect protocol over the same pinned append-only receipt writer."""

from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, closed, sha, utc
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.openai.contracts import OpenAIResponsesResponse

EVENTS = ("RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSED", "CONSUMED")
FIELDS = {
    "schema",
    "state",
    "grant_sha256",
    "request_sha256",
    "preflight_sha256",
    "namespace_sha256",
    "reserved_usd",
    "timestamp_utc",
    "artifact_sha256",
    "format_status",
    "billed_cost",
}


class FiniteEffectReceipt:
    def __init__(self, receipt: P0NormalReceipt, slot: Mapping[str, object]) -> None:
        self.receipt, self.slot = receipt, slot

    def event(
        self, state: str, now: datetime, *, artifact: str | None = None, status: str | None = None
    ) -> str:
        if state not in (*EVENTS, "UNKNOWN", "PARSING_REJECTED"):
            raise ValueError("P0_CHAIN_RECEIPT_STATE")
        return self.receipt.publish(
            state,
            {
                "schema": "P0-FINITE-EFFECT-RECEIPT-1.0",
                "state": state,
                **{
                    key: self.slot[key]
                    for key in (
                        "grant_sha256",
                        "request_sha256",
                        "preflight_sha256",
                        "namespace_sha256",
                        "reserved_usd",
                    )
                },
                "timestamp_utc": now.isoformat(),
                "artifact_sha256": artifact,
                "format_status": status,
                "billed_cost": "NOT_ESTABLISHED",
            },
        )

    def capture(self, response: OpenAIResponsesResponse, now: datetime) -> str:
        artifact = self.receipt.publish(
            "RESULT",
            {
                "schema": "P0-FINITE-EFFECT-RESULT-1.0",
                "grant_sha256": self.slot["grant_sha256"],
                "request_sha256": self.slot["request_sha256"],
                "response_status": response.status.value,
                "output_text": response.output_text,
                "usage": asdict(response.usage),
                "service_tier": response.service_tier,
                "incomplete_reason": response.incomplete_reason.value,
            },
        )
        self.event("RESPONSE_CAPTURED", now, artifact=artifact, status=response.status.value)
        return artifact

    def states(self) -> tuple[str, ...]:
        result = []
        grant = cast(Mapping[str, object], self.slot["grant"])
        prior = utc(grant["issued_at_utc"])
        for state in (*EVENTS, "UNKNOWN", "PARSING_REJECTED"):
            if not self.receipt.exists(state):
                continue
            event = self.receipt.read(state)
            closed(event, FIELDS, "P0_CHAIN_RECEIPT_FIELDS")
            timestamp = utc(event["timestamp_utc"])
            if (
                event["schema"] != "P0-FINITE-EFFECT-RECEIPT-1.0"
                or event["state"] != state
                or any(
                    event[key] != self.slot[key]
                    for key in (
                        "grant_sha256",
                        "request_sha256",
                        "preflight_sha256",
                        "namespace_sha256",
                        "reserved_usd",
                    )
                )
                or timestamp < prior
                or event["billed_cost"] != "NOT_ESTABLISHED"
            ):
                raise ValueError("P0_CHAIN_RECEIPT_BINDING")
            prior = timestamp
            result.append(state)
        if "RESPONSE_CAPTURED" in result:
            event = self.receipt.read("RESPONSE_CAPTURED")
            artifact = self.receipt.read("RESULT")
            if (
                event["artifact_sha256"] != sha(canonical(artifact))
                or artifact.get("schema") != "P0-FINITE-EFFECT-RESULT-1.0"
                or artifact.get("grant_sha256") != self.slot["grant_sha256"]
                or artifact.get("request_sha256") != self.slot["request_sha256"]
            ):
                raise ValueError("P0_CHAIN_CAPTURE_BINDING")
            closed(
                artifact,
                {
                    "schema",
                    "grant_sha256",
                    "request_sha256",
                    "response_status",
                    "output_text",
                    "usage",
                    "service_tier",
                    "incomplete_reason",
                },
                "P0_CHAIN_RESULT_FIELDS",
            )
            if (
                not isinstance(artifact["output_text"], (str, type(None)))
                or "CONSUMED" in result
                and (
                    artifact["response_status"] != "completed"
                    or artifact["service_tier"] not in {None, "default"}
                )
            ):
                raise ValueError("P0_CHAIN_RESULT_NOT_CONSUMABLE")
        required = {
            "PROVIDER_ATTEMPTED": "RESERVED",
            "RESPONSE_CAPTURED": "PROVIDER_ATTEMPTED",
            "PARSED": "RESPONSE_CAPTURED",
            "CONSUMED": "PARSED",
            "UNKNOWN": "PROVIDER_ATTEMPTED",
            "PARSING_REJECTED": "RESPONSE_CAPTURED",
        }
        if (
            any(
                state in result and predecessor not in result
                for state, predecessor in required.items()
            )
            or "UNKNOWN" in result
            and "RESPONSE_CAPTURED" in result
            or "CONSUMED" in result
            and any(state in result for state in ("UNKNOWN", "PARSING_REJECTED"))
        ):
            raise ValueError("P0_CHAIN_RECEIPT_SEQUENCE")
        if self.receipt.exists("DISPATCH"):
            dispatch = self.receipt.read("DISPATCH")
            closed(
                dispatch,
                {
                    "schema",
                    "grant",
                    "preflight",
                    "request_body_utf8",
                    "chain_preview",
                    "chain_consent",
                },
                "P0_CHAIN_DISPATCH_FIELDS",
            )
            raw = dispatch["request_body_utf8"]
            proof = dispatch["preflight"]
            preview, consent = dispatch["chain_preview"], dispatch["chain_consent"]
            if not isinstance(preview, Mapping) or not isinstance(consent, Mapping):
                raise ValueError("P0_CHAIN_CONSENT_BINDING")
            if (
                sha(canonical(preview)) != grant["preview_sha256"]
                or sha(canonical(consent)) != grant["consent_sha256"]
                or consent.get("preview_sha256") != grant["preview_sha256"]
                or consent.get("command_id") != grant["chain_command_id"]
                or consent.get("transfer_accepted") is not True
                or consent.get("cost_bound_accepted") is not True
                or grant["ordinal"] == 0
                and not utc(preview["issued_at_utc"])
                <= utc(grant["issued_at_utc"])
                < utc(preview["expires_at_utc"])
            ):
                raise ValueError("P0_CHAIN_CONSENT_BINDING")
            if (
                dispatch["schema"] != "P0-FINITE-EFFECT-DISPATCH-1.0"
                or dispatch["grant"] != self.slot["grant"]
                or not isinstance(raw, str)
                or sha(raw.encode()) != self.slot["request_sha256"]
                or len(raw.encode()) != grant["request_bytes"]
                or not isinstance(proof, Mapping)
                or sha(canonical(proof)) != self.slot["preflight_sha256"]
                or proof.get("cost_bound_usd") != self.slot["reserved_usd"]
            ):
                raise ValueError("P0_CHAIN_DISPATCH_BINDING")
        elif "PROVIDER_ATTEMPTED" in result:
            raise ValueError("P0_CHAIN_DISPATCH_REQUIRED")
        return tuple(result)
