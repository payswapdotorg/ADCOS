"""WORK-038 evidence model: the three-class separation.

The WORK-038 handoff's evidence classes, expressed over the ACCEPTED
WORK-032 ``EvidenceClass`` vocabulary (reused as DATA; no second
vocabulary):

- **A -- architecture conformance** (required now): the profile is an
  additive adapter/profile over the accepted contracts; no core
  schema change (registry digest-pinned); no vendor/PHY types in
  core; no authority duplicated;
- **B -- automated verification** (required now): what the
  deterministic synthetic conformance run observed (registration,
  the nine-operation contract exercise, unknown-id preservation,
  core equivalence -- all digested and replayable);
- **C -- physical/future-network interoperability**: **NOT
  APPLICABLE** to this synthetic work item, per the handoff's own
  class list.  This module enforces that verdict structurally: no
  in-repo artifact can ever mint class-C evidence for the future
  profile, and class C can never be "closed" -- there is nothing to
  close.  The hypothetical technology has no real network; claiming
  one would be fabrication (the W020 lesson applied to the
  inapplicable class).

The anti-fabrication guard is the mirror of WORK-037's
anti-promotion rule: classes A and B may never be presented as class
C, and for WORK-038 class C admits no closure path AT ALL (not even
an operator-attached gate outcome -- the work item's acceptance is
entirely synthetic by design).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .errors import FutureError, FutureReasonCode
from .model import FUTURE_EVIDENCE_CLASS_MAP

__all__ = [
    "FUTURE_EVIDENCE_STATUS",
    "SYNTHETIC_EVIDENCE_STATEMENT",
    "classify_future_evidence",
    "assert_no_real_world_claim",
]


#: The frozen three-class evidence disclosure for WORK-038: classes A
#: and B are closed in-repo; class C is NOT APPLICABLE (the work
#: item's verification requirement is entirely synthetic by the
#: frozen contract).
FUTURE_EVIDENCE_STATUS: Dict[str, str] = {
    "architecture_conformance": "supported-verified",
    "automated_verification": "supported-verified",
    "future_network_interop": "not-applicable",
}


#: The fixed statement recorded for the not-applicable class.
SYNTHETIC_EVIDENCE_STATEMENT = (
    "No real-world or future-network interoperability evidence is "
    "claimed, implied, or closable by this work item. WORK-038's "
    "acceptance is entirely synthetic (a synthetic future-profile "
    "conformance test over the accepted adapter/registry/core "
    "contracts); the hypothetical IMT-2030 technology has no radio, "
    "no vendor implementation, and no deployed network. When a real "
    "future IMT/6G system exists, its integration is a NEW work item "
    "with its own evidence contract -- the synthetic evidence here "
    "can never be promoted to it."
)


def assert_no_real_world_claim(*, claimed_class: str) -> None:
    """Fail-closed guard: no WORK-038 artifact may claim class C
    (real-world/future-network evidence) -- the anti-fabrication
    rule, enforced in code.

    Unlike WORK-037 (where class C was OPEN and closable by a real
    gate), WORK-038's class C is NOT APPLICABLE: there is no closure
    path at all, so even an operator-attached outcome is refused.
    """
    if claimed_class == "C":
        raise FutureError(
            FutureReasonCode.EVIDENCE_CLASS_VIOLATION,
            "classes A and B may never be promoted to class C, and "
            "class C (real-world/future-network evidence) is NOT "
            "APPLICABLE to WORK-038: the acceptance is entirely "
            "synthetic; there is no closure path, operator-attached "
            "or otherwise",
        )
    if claimed_class not in ("A", "B"):
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "claimed_class must be 'A' or 'B' (got %r)" % (claimed_class,),
        )


def classify_future_evidence(
    *,
    profile_validated: bool,
    contract_exercised: bool,
    run_digest: Optional[str],
    gate_outcome: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build the three-class evidence report (pure classification).

    Parameters
    ----------
    profile_validated:
        whether the profile declaration passed the fail-closed
        validation (class A input).
    contract_exercised:
        whether the synthetic conformance contract (the nine WORK-016
        operations, unknown-id preservation, core equivalence) was
        exercised by the class-B run.
    run_digest:
        the class-B run's ``future_digest()``.
    gate_outcome:
        REFUSED for this work item: any attempt to attach an
        operator-side "real future-network" outcome raises the typed
        anti-fabrication error -- class C is not applicable and has
        no closure path (the structural difference from WORK-037's
        open class C).

    Raises
    ------
    FutureError
        with ``future.evidence-class-violation`` when any class-C
        closure is attempted.
    """
    from .profile import profile_complete

    if gate_outcome is not None:
        raise FutureError(
            FutureReasonCode.EVIDENCE_CLASS_VIOLATION,
            "WORK-038 admits no class-C closure: physical/future-"
            "network evidence is not applicable to this synthetic "
            "work item (no gate outcome can be attached)",
        )

    class_a = {
        "class": "A",
        "evidence_class": FUTURE_EVIDENCE_CLASS_MAP["A"].value,
        "profile_validated": bool(profile_validated),
        "complete": profile_complete(
            validated=bool(profile_validated),
            contract_exercised=bool(contract_exercised),
        ),
        "coverage": (
            "additive adapter/profile over the accepted W016 SDK + "
            "W002 registry (digest-pinned, no schema change) + W005 "
            "capability references + W008 mapping kinds/units + W029 "
            "version coexistence + no vendor/PHY types in core + no "
            "second authority"
        ),
    }

    class_b = {
        "class": "B",
        "evidence_class": FUTURE_EVIDENCE_CLASS_MAP["B"].value,
        "contract_exercised": bool(contract_exercised),
        "run_digest": run_digest,
        "basis": (
            "deterministic synthetic future-profile conformance over "
            "the real accepted authorities (runtime, session store, "
            "registries, canonicalization)"
        ),
    }

    class_c = {
        "class": "C",
        "evidence_class": FUTURE_EVIDENCE_CLASS_MAP["C"].value,
        "status": FUTURE_EVIDENCE_STATUS["future_network_interop"],
        "statement": SYNTHETIC_EVIDENCE_STATEMENT,
    }

    return {
        "A": class_a,
        "B": class_b,
        "C": class_c,
        "status": dict(FUTURE_EVIDENCE_STATUS),
    }
