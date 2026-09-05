"""ADCOS W054 system-composition orchestration boundary.

This package owns orchestration receipts and conformance mechanics only.
Canonical commercial/connectivity state remains in the existing authority
packages; W054 never becomes authoritative for those domains.
"""

from .model import (
    COMPOSITION_STAGES,
    CompositionError,
    CompositionReasonCode,
    CompositionRequest,
    CompositionResult,
    StageReceipt,
)
from .runtime import CompositionRuntime, InMemoryCompositionStore, StageExecutor

__all__ = [
    "COMPOSITION_STAGES",
    "CompositionError",
    "CompositionReasonCode",
    "CompositionRequest",
    "CompositionResult",
    "StageReceipt",
    "CompositionRuntime",
    "InMemoryCompositionStore",
    "StageExecutor",
]
