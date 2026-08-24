from __future__ import annotations

from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef

type ContractRef = str | TypedEntityRef | ObjectVersionRef


def require_contract_ref(value: ContractRef, field_name: str) -> None:
    if isinstance(value, str):
        require_non_empty(value, field_name)
        return
    if isinstance(value, (TypedEntityRef, ObjectVersionRef)):
        return
    raise TypeError(f"{field_name} must be a string or typed reference")
