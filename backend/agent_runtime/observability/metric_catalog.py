from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Final

from backend.agent_runtime.agents.evidence.retrieval_model import RetrievalChannel
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ErrorCategory,
    ErrorSeverity,
    ErrorSource,
    MetricDescriptor,
    MetricKind,
    MetricLabelSpec,
    MetricName,
    MetricUnit,
    ObservationCode,
    SecurityEventType,
    SecuritySeverity,
)
from backend.agent_runtime.recovery.budget import BudgetMetricCompleteness
from backend.agent_runtime.recovery.coordinator import RecoveryAction
from backend.agent_runtime.recovery.reconciliation import (
    EffectReconciliationDisposition,
)
from backend.agent_runtime.recovery.retry import RetryDisposition
from backend.agent_runtime.runtime.execution.directives import ExecutionDirectiveCode


class MetricCode(StrEnum):
    """Closed source registry for every Phase 12.13-E metric."""

    BUDGET_CONSUMED_TOKENS = "agent_runtime.budget.consumed_tokens"
    BUDGET_CONSUMED_COST = "agent_runtime.budget.consumed_cost"
    BUDGET_ACTIVE_RUNTIME = "agent_runtime.budget.active_runtime"
    BUDGET_STEPS_STARTED = "agent_runtime.budget.steps_started"
    BUDGET_RETRIES = "agent_runtime.budget.retries"
    BUDGET_TOOL_CALLS = "agent_runtime.budget.tool_calls"
    SECURITY_EVENTS = "agent_runtime.security.events"
    ERRORS = "agent_runtime.errors"
    RUNTIME_DIRECTIVES = "agent_runtime.runtime.directives"
    RETRIEVAL_RESULT_CANDIDATES = "agent_runtime.retrieval.result_candidates"
    EVIDENCE_MATERIALIZED_ITEMS = "agent_runtime.evidence.materialized_items"
    RECOVERY_DECISIONS = "agent_runtime.recovery.decisions"
    RETRY_DECISIONS = "agent_runtime.recovery.retry_decisions"
    RECONCILIATIONS = "agent_runtime.recovery.reconciliations"


MAX_SERIES_PER_DESCRIPTOR: Final = 256
MAX_CATALOG_SERIES: Final = 512


def _values(enum_type: type[StrEnum]) -> tuple[str, ...]:
    return tuple(item.value for item in enum_type)


_COMPLETENESS = MetricLabelSpec(
    "completeness", _values(BudgetMetricCompleteness)
)
_EVENT_TYPE = MetricLabelSpec("event_type", _values(SecurityEventType))
_SECURITY_SEVERITY = MetricLabelSpec("severity", _values(SecuritySeverity))
_ERROR_CATEGORY = MetricLabelSpec("category", _values(ErrorCategory))
_ERROR_SOURCE = MetricLabelSpec("source", _values(ErrorSource))
_ERROR_SEVERITY = MetricLabelSpec("severity", _values(ErrorSeverity))
_DIRECTIVE = MetricLabelSpec("directive", _values(ExecutionDirectiveCode))
_RETRIEVAL_CHANNEL = MetricLabelSpec("channel", _values(RetrievalChannel))
_RECOVERY_ACTION = MetricLabelSpec("action", _values(RecoveryAction))
_RETRY_DISPOSITION = MetricLabelSpec("disposition", _values(RetryDisposition))
_RECONCILIATION_DISPOSITION = MetricLabelSpec(
    "disposition", _values(EffectReconciliationDisposition)
)


def _descriptor(
    code: MetricCode,
    kind: MetricKind,
    unit: str,
    *labels: MetricLabelSpec,
) -> MetricDescriptor:
    return MetricDescriptor(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        name=MetricName(code.value),
        kind=kind,
        unit=MetricUnit(unit),
        description_code=ObservationCode(f"METRIC.{code.name}"),
        allowed_labels=labels,
    )


METRIC_CATALOG: Final[tuple[MetricDescriptor, ...]] = (
    _descriptor(
        MetricCode.BUDGET_CONSUMED_TOKENS,
        MetricKind.GAUGE,
        "tokens",
        _COMPLETENESS,
    ),
    _descriptor(
        MetricCode.BUDGET_CONSUMED_COST,
        MetricKind.GAUGE,
        "currency_units",
        _COMPLETENESS,
    ),
    _descriptor(
        MetricCode.BUDGET_ACTIVE_RUNTIME,
        MetricKind.GAUGE,
        "s",
    ),
    _descriptor(MetricCode.BUDGET_STEPS_STARTED, MetricKind.GAUGE, "items"),
    _descriptor(MetricCode.BUDGET_RETRIES, MetricKind.GAUGE, "items"),
    _descriptor(MetricCode.BUDGET_TOOL_CALLS, MetricKind.GAUGE, "items"),
    _descriptor(
        MetricCode.SECURITY_EVENTS,
        MetricKind.COUNTER,
        "events",
        _EVENT_TYPE,
        _SECURITY_SEVERITY,
    ),
    _descriptor(
        MetricCode.ERRORS,
        MetricKind.COUNTER,
        "errors",
        _ERROR_CATEGORY,
        _ERROR_SOURCE,
        _ERROR_SEVERITY,
    ),
    _descriptor(
        MetricCode.RUNTIME_DIRECTIVES,
        MetricKind.COUNTER,
        "directives",
        _DIRECTIVE,
    ),
    _descriptor(
        MetricCode.RETRIEVAL_RESULT_CANDIDATES,
        MetricKind.HISTOGRAM,
        "items",
        _RETRIEVAL_CHANNEL,
    ),
    _descriptor(
        MetricCode.EVIDENCE_MATERIALIZED_ITEMS,
        MetricKind.HISTOGRAM,
        "items",
    ),
    _descriptor(
        MetricCode.RECOVERY_DECISIONS,
        MetricKind.COUNTER,
        "decisions",
        _RECOVERY_ACTION,
    ),
    _descriptor(
        MetricCode.RETRY_DECISIONS,
        MetricKind.COUNTER,
        "decisions",
        _RETRY_DISPOSITION,
    ),
    _descriptor(
        MetricCode.RECONCILIATIONS,
        MetricKind.COUNTER,
        "decisions",
        _RECONCILIATION_DISPOSITION,
    ),
)

_DESCRIPTORS: Final = MappingProxyType(
    {MetricCode(descriptor.name.value): descriptor for descriptor in METRIC_CATALOG}
)


def metric_descriptor(code: MetricCode) -> MetricDescriptor:
    if not isinstance(code, MetricCode):
        raise TypeError("code must be a MetricCode")
    return _DESCRIPTORS[code]
