"""W054 bridge from the accepted Developer API shape to composition.

Authentication, authorization, rate limiting, API versioning, idempotency
admission, webhook admission, and canonical response semantics remain owned by
WORK-046. This adapter only translates an already-admitted developer request
into a W054 CompositionRequest and delegates execution.
"""

from __future__ import annotations

from typing import Any, Mapping

from .model import CompositionError, CompositionReasonCode, CompositionRequest
from .runtime import CompositionRuntime

_REQUIRED = frozenset({"request_id", "actor", "source", "intent"})


def compose_developer_request(
    *, runtime: CompositionRuntime, request: Mapping[str, Any]
):
    """Drive W054 from the canonical post-admission Developer API request shape.

    Unknown top-level request members are rejected so the bridge cannot invent
    a second request schema. WORK-046 remains responsible for authenticating
    the caller and determining the canonical request identity.
    """
    if not isinstance(request, Mapping):
        raise CompositionError(CompositionReasonCode.INVALID_INPUT, "developer request must be a mapping")
    unknown = sorted(set(request) - _REQUIRED)
    missing = sorted(_REQUIRED - set(request))
    if unknown or missing:
        raise CompositionError(
            CompositionReasonCode.INVALID_INPUT,
            "developer request shape mismatch; missing=%s unknown=%s" % (missing, unknown),
        )
    return runtime.compose(
        CompositionRequest(
            request_id=request["request_id"],
            actor=request["actor"],
            source=request["source"],
            intent=request["intent"],
        )
    )
