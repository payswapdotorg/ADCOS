"""ADCOS executionplans package — M006: Execution Plan.

The contract-to-execution-plan translation domain (LOCK-109): the
canonical bridge that translates an ACCEPTED canonical
``ConnectivityContract`` (the M002 ``contracts/`` domain — consumed by
reference, never modified, never duplicated) into a typed
``ExecutionPlan`` composed of typed ``ExecutionSegment`` records.

The central boundary (enforced throughout):

    EXECUTION PLAN
        = the bridge from contract to provider mechanisms (LOCK-109)
        != CONTRACT AUTHORITY (contracts/ stays the sole authority)
        != ADAPTER / PROVIDER SDK TYPES (LOCK-110: operations by name)
        != OPTIMIZER AUTHORITY (LOCK-111: replaceable, data-only input)
        != SESSION / PATH / TUNNEL AUTHORITY (LOCK-117: the plan rides
          as an opaque execution-artifact reference, never authority)
        != REPLAN / FAILOVER (M008: the M006 segment vocabulary stops
          at PLANNED/RESERVED/ACTIVATED/MEASURED/RELEASED)

Simple deployments: one contract -> one segment (frozen 1.1 §10:
Intent -> Offer -> Contract -> one ExecutionSegment -> Assurance).
Complex deployments: multiple providers/segments/access
mechanisms/failover alternatives under ONE contract (LOCK-116), each
segment typed and attributable to the contract.

LOCK-108 discipline: the translation NEVER weakens a hard contract
constraint — the plan's constraint set is the contract's own set,
preserved verbatim with the contract's own LOCK-108 fingerprint; every
weakening attempt (drop, relax, re-interpret, reorder) fails closed
with a typed error (``translation.verify_plan_preserves_contract`` is
the pure cross-authority gate; construction and deserialization carry
tamper evidence).

Harvest disclosure (R7 charter M006 scope: ``composition/`` (harvest)):
the chain-orchestration and conformance-evidence patterns of the
WORK-054 composition layer are harvested onto this 1.1 authority —
see ``conformance.py`` for the disclosed seam. composition/ stays the
WORK-054 conformance layer (DEC-0085/DEC-0086 preserved); WORK-048
stays accepted-not-restored; no second authority is created.

Determinism (LOCK-119): content-derived ids over canonical JSON;
injected instants only (no wall clock); no randomness, no UUIDs, no
network, no secrets; sorted and order-normalized iteration;
PYTHONHASHSEED-safe; canonical-JSON round-trips.
"""

from __future__ import annotations

from .errors import ExecutionPlanError, ExecutionPlanReason
from .model import (
    ADAPTER_OPERATIONS,
    DEFAULT_TIE_BREAK,
    PLANNABLE_CONTRACT_STATES,
    SEGMENT_ROLES,
    SEGMENT_STATES,
    SEGMENT_TERMINAL_STATES,
    SEGMENT_TRANSITIONS,
    TIE_BREAK_KEYS,
    ExecutionPlan,
    ExecutionSegment,
    apply_segment_transition,
    check_segment_transition,
    derive_plan_id,
    derive_segment_id,
)
from .translation import (
    SegmentInput,
    plan_reference,
    translate_contract,
    verify_plan_preserves_contract,
)
from .conformance import (
    EVIDENCE_CLASS_SOFTWARE,
    HARVEST_DISCLOSURE,
    PLAN_BRIDGE_DISCLAIMER,
    conformance_digest,
    conformance_document,
    execution_sequence,
)

__all__ = [
    # typed errors
    "ExecutionPlanError",
    "ExecutionPlanReason",
    # frozen vocabularies
    "ADAPTER_OPERATIONS",
    "DEFAULT_TIE_BREAK",
    "PLANNABLE_CONTRACT_STATES",
    "SEGMENT_ROLES",
    "SEGMENT_STATES",
    "SEGMENT_TERMINAL_STATES",
    "SEGMENT_TRANSITIONS",
    "TIE_BREAK_KEYS",
    # the plan model + segment state machine
    "ExecutionPlan",
    "ExecutionSegment",
    "apply_segment_transition",
    "check_segment_transition",
    "derive_plan_id",
    "derive_segment_id",
    # the LOCK-109 translation bridge
    "SegmentInput",
    "plan_reference",
    "translate_contract",
    "verify_plan_preserves_contract",
    # the harvested conformance-evidence surface
    "EVIDENCE_CLASS_SOFTWARE",
    "HARVEST_DISCLOSURE",
    "PLAN_BRIDGE_DISCLAIMER",
    "conformance_digest",
    "conformance_document",
    "execution_sequence",
]
