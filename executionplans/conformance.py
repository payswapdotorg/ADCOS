"""The M006 conformance-evidence surface — the harvested WORK-054
composition patterns, refactored onto the 1.1 authority.

HARVEST DISCLOSURE (the R7 charter M006 scope: ``composition/``
(harvest)): the two structural patterns of the WORK-054 System
Composition Conformance layer (``composition/``, DEC-0085/DEC-0086)
are harvested onto the Architecture 1.1 execution-plan authority:

- the **chain-orchestration pattern** — an ordered sequence of typed
  steps, each attributed to an owning surface, each advanced or failed
  closed deterministically (``composition.chain`` /
  ``composition.orchestrator``) — becomes the plan's typed execution
  sequence: ordered (segment, adapter-operation) steps over the frozen
  1.1 §6 capability-oriented vocabulary, attributed to segments that
  are attributable to exactly one canonical contract;
- the **conformance-evidence pattern** — derived-only evidence
  documents carrying a canonical-JSON SHA-256 digest, an explicit
  SOFTWARE evidence class, and a mandatory honesty disclaimer, never
  an authority (``composition.evidence``) — becomes the plan
  conformance document: derived evidence over a VERIFIED plan
  (``conformance_document`` fail-closes unless the plan preserves the
  contract's hard constraints, LOCK-108).

The direction of the harvest is one-way and authority-preserving:
``executionplans/`` imports NO composition code (the composition
import discipline also forbids the reverse direction — its frozen
battery-pinned allowlist). ``composition/`` stays exactly the WORK-054
conformance layer it was: a conformance/orchestration/evidence layer
over the legacy 1.0-era chain, creating no second authority, with
WORK-048 still accepted-not-restored (detected, fail-closed). The
execution-plan translation is the CANONICAL bridge from the
canonical ``ConnectivityContract`` to provider mechanisms (LOCK-109);
this module is where that bridge's derived conformance evidence
lives. Nothing here executes a provider mechanism, creates a session,
or claims production connectivity.

Determinism: no wall clock, no randomness, no UUIDs, no network, no
filesystem writes; the document is a pure function of (plan,
contract); digests follow the WORK-003 canonical-JSON SHA-256
convention.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Tuple

from protocol.canonicalization import canonical_json_bytes

from contracts import ConnectivityContract

from .model import ExecutionPlan, ExecutionSegment
from .translation import verify_plan_preserves_contract

__all__ = [
    "EVIDENCE_CLASS_SOFTWARE",
    "HARVEST_DISCLOSURE",
    "PLAN_BRIDGE_DISCLAIMER",
    "conformance_digest",
    "conformance_document",
    "execution_sequence",
]


#: The evidence class of every document this module produces (the
#: WORK-054 discipline: SOFTWARE only, never PHYSICAL).
EVIDENCE_CLASS_SOFTWARE = "SOFTWARE"

#: The mandatory honesty disclaimer carried by every plan-conformance
#: document (the harvested SEGMENT_CONFORMANCE_DISCLAIMER discipline).
PLAN_BRIDGE_DISCLAIMER = (
    "This document is DERIVED conformance evidence over an execution "
    "plan. It is not a contract authority, not an execution authority, "
    "and not a claim that any provider mechanism was engaged or that "
    "production connectivity was delivered: segments reference "
    "capability-oriented adapter operations by name only (the M007 "
    "adapter surface is a pending child and owns the actual "
    "mechanisms). The strict composition chain of the WORK-054 layer "
    "remains BLOCKED_MISSING_AUTHORITY at the containment edge "
    "(WORK-048 accepted-not-restored), and nothing in this document "
    "promotes the plan, the composition chain, or any segment into an "
    "authority."
)

#: The harvest disclosure carried by every plan-conformance document
#: (the M006 charter scope: composition/ (harvest) — disclosed here,
#: never silent).
HARVEST_DISCLOSURE = (
    "The chain-orchestration and conformance-evidence patterns of this "
    "document are harvested from the WORK-054 composition layer "
    "(composition/, DEC-0085/DEC-0086) onto the Architecture 1.1 "
    "execution-plan authority (executionplans/, M006, LOCK-109). "
    "composition/ itself remains the conformance layer it always was "
    "— no second authority is created on either side — and WORK-048 "
    "stays accepted-not-restored."
)


def execution_sequence(plan: ExecutionPlan) -> Tuple[Tuple[str, str], ...]:
    """The harvested chain-orchestration shape over one plan: the
    ordered (segment_id, adapter-operation) steps of the plan's
    realization, in the plan's deterministic segment order and the
    frozen canonical 1.1 §6 operation order. Pure derived data."""
    steps: list = []
    for segment in plan.segments:
        for operation in segment.operations:
            steps.append((segment.segment_id, operation))
    return tuple(steps)


def conformance_document(
    plan: ExecutionPlan, contract: ConnectivityContract
) -> Dict[str, Any]:
    """Build the derived plan-conformance document (fail-closed).

    The document never certifies an unverified plan:
    ``verify_plan_preserves_contract`` MUST pass first (LOCK-108 —
    a plan that drops, relaxes or re-interprets a hard contract
    constraint produces no evidence at all). Every member is a
    projection of the plan and the contract (public reads only); the
    document is never a state store and never authoritative for
    anything — it is SOFTWARE-class conformance evidence.
    """
    # fail closed first: no conformance evidence over a weakened plan
    verify_plan_preserves_contract(plan, contract)
    document: Dict[str, Any] = {
        "kind": "m006-execution-plan-conformance",
        "evidence_class": EVIDENCE_CLASS_SOFTWARE,
        "plan_id": plan.plan_id,
        "contract_id": plan.contract_id,
        "constraint_fingerprint": plan.constraint_fingerprint,
        "tie_break": list(plan.tie_break),
        "validity": plan.validity.to_dict(),
        "segments": [
            {
                "segment_id": segment.segment_id,
                "role": segment.role,
                "offer": segment.offer_reference.value,
                "operations": list(segment.operations),
                "state": segment.state,
            }
            for segment in plan.segments
        ],
        "execution_sequence": [
            {"step": index + 1, "segment_id": segment_id, "operation": operation}
            for index, (segment_id, operation) in enumerate(execution_sequence(plan))
        ],
        "disclaimer": PLAN_BRIDGE_DISCLAIMER,
        "harvest_disclosure": HARVEST_DISCLOSURE,
    }
    return document


def conformance_digest(document: Dict[str, Any]) -> str:
    """The WORK-003-convention content digest of a conformance
    document (canonical JSON, SHA-256, ``sha256:``-prefixed)."""
    return "sha256:" + hashlib.sha256(canonical_json_bytes(document)).hexdigest()
