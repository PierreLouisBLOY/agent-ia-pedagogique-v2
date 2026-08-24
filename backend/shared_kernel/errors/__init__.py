"""Generic business error contracts."""

from backend.shared_kernel.errors.business_error import (
    BusinessError,
    BusinessErrorCategory,
    BusinessErrorCode,
    BusinessErrorDomain,
    BusinessErrorSeverity,
)

__all__ = [
    "BusinessError",
    "BusinessErrorCategory",
    "BusinessErrorCode",
    "BusinessErrorDomain",
    "BusinessErrorSeverity",
]
