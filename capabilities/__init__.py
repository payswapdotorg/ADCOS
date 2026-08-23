"""ADCOS capability package — WORK-005: capability statements and negotiation.

Implements signed, versioned capability advertisements and deterministic
negotiation per spec/architecture.md section 6.4 and the frozen WORK-005
handoff. The central boundary:

    Capability statement  ≠  truth  ≠  trust  ≠  authorization
                         ≠  topology authority

A capability statement is a CLAIM about what a node/adapter may provide.
A signature establishes an ATTRIBUTABLE statement (provenance), never
truth, availability, authorization, or trust. Evidence references stay
opaque references; remote summaries remain claims by their reporter
(LOCK-008). Negotiation answers only "what mutually understood capability
can both parties support?" — never "is this peer authorized or trusted?"

Identifier authority is the WORK-002 capability registry
(spec/schemas/registries/capability-registry.json); classification is
KNOWN / UNKNOWN_BUT_WELL_FORMED / INVALID, never coerced. Validity uses
WORK-003 temporal primitives; signing uses the WORK-003 canonical
signature-input machinery and the WORK-004 provider abstraction.
"""

from __future__ import annotations

from .classification import CapabilityIdClass, classify_capability_id
from .model import (
    CapabilityError,
    CapabilityStatement,
    statement_from_mapping,
)
from .negotiation import (
    NegotiationOutcome,
    NegotiationResult,
    NegotiationSpec,
    RejectionReason,
    Requirement,
    negotiate,
)
from .registry import CapabilityRegistry, default_registry
from .serialization import (
    SerializationError,
    statement_from_bytes,
    statement_to_bytes,
    statement_to_dict,
)
from .signing import (
    sign_statement,
    statement_signature_input,
    verify_statement,
)
from .validity import (
    StatementStatus,
    ValidityError,
    evaluate_status,
    validate_validity,
)

__all__ = [
    "CapabilityError",
    "CapabilityIdClass",
    "CapabilityRegistry",
    "CapabilityStatement",
    "NegotiationOutcome",
    "NegotiationResult",
    "NegotiationSpec",
    "RejectionReason",
    "SerializationError",
    "StatementStatus",
    "ValidityError",
    "classify_capability_id",
    "default_registry",
    "evaluate_status",
    "negotiate",
    "sign_statement",
    "statement_from_bytes",
    "statement_from_mapping",
    "statement_signature_input",
    "statement_to_bytes",
    "statement_to_dict",
    "validate_validity",
    "verify_statement",
]
