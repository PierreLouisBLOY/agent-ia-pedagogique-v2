from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.shared_kernel._strings import require_non_empty


class TaskType(StrEnum):
    RUNTIME_CONTRACT = "RUNTIME_CONTRACT"


class TaskStatus(StrEnum):
    COMPLETED = "COMPLETED"


@dataclass(frozen=True, slots=True)
class TaskObjectiveRef:
    value: str

    def __post_init__(self) -> None:
        require_non_empty(self.value, "value")
        if len(self.value) > 256:
            raise ValueError("value must contain at most 256 characters")


@dataclass(frozen=True, slots=True)
class TaskPersistenceValues:
    """Application-owned values supplied to the task persistence adapter."""

    task_type: TaskType
    objective_ref: TaskObjectiveRef
    status: TaskStatus

    def __post_init__(self) -> None:
        if not isinstance(self.task_type, TaskType):
            raise TypeError("task_type must be a TaskType")
        if not isinstance(self.objective_ref, TaskObjectiveRef):
            raise TypeError("objective_ref must be a TaskObjectiveRef")
        if not isinstance(self.status, TaskStatus):
            raise TypeError("status must be a TaskStatus")
