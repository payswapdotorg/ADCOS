"""WORK-037 evidence model: the three-class separation.

The WORK-037 handoff's evidence classes, expressed over the ACCEPTED
WORK-032 ``EvidenceClass`` vocabulary (reused as DATA; no second
vocabulary):

- **A -- architecture conformance** (required now): the frozen
  contract surface the profile covers (components, reference points,
  ownership, import purity);
- **B -- automated verification** (required now): what the
  deterministic in-repo run observed (the class-B mixed-access
  scenario over the conformance peers);
- **C -- real interoperability** (required for the frozen acceptance
  claim): evidence gathered on a REAL 5G lab.  OPEN until the real
  lab gate (:mod:`interop.labgate`) passes.

The W020 lesson is enforced structurally, exactly as WORK-032
enforced it: an in-repo class-B record can NEVER mint class C.
:class:`classify_profile_evidence` refuses real-lab closure unless a
genuine gate outcome with status ``PASSED`` and a coherent session id
is supplied explicitly (operator-side attachment, the WORK-032
external-evidence discipline).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .errors import InteropError, InteropReasonCode
from .model import PROFILE_EVIDENCE_CLASS_MAP
from .profile import profile_complete

__all__ = [
    "PROFILE_EVIDENCE_STATUS",
    "REAL_LAB_EVIDENCE_STATEMENT",
    "classify_profile_evidence",
    "assert_no_real_lab_claim",
]

#: The frozen three-class evidence disclosure for WORK-037 (the
#: W020/W034/W035/W036 two-track discipline, generalized to the
#: profile's three classes).
PROFILE_EVIDENCE_STATUS: Dict[str, str] = {
    "architecture_conformance": "supported-verified",
    "automated_verification": "supported-verified",
    "real_interop_lab": "open",
}

#: The fixed statement recorded while class C is open.
REAL_LAB_EVIDENCE_STATEMENT = (
    "No real interoperability-lab evidence is established by in-repo "
    "runs. Architecture conformance and automated verification are "
    "recorded separately; the real-lab criterion requires an "
    "independent 5G lab (real Open5GS, real SDR-based RAN, real "
    "N3IWF path) supplied by the operator side and is closed only by "
    "the profile lab gate's PASSED outcome. RF simulation, OAI "
    "RFsim, software emulation, and synthetic interoperability can "
    "never be promoted to this criterion."
)


def assert_no_real_lab_claim(*, claimed_class: str) -> None:
    """Fail-closed guard: a class-B/A artifact may never claim to be
    class C (the anti-promotion rule, enforced in code)."""
    if claimed_class == "C":
        raise InteropError(
            InteropReasonCode.EVIDENCE_CLASS_VIOLATION,
            "classes A and B may never be promoted to class C (real "
            "interoperability); the real-lab criterion is closed only "
            "by the profile lab gate's PASSED outcome",
        )
    if claimed_class not in ("A", "B"):
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "claimed_class must be 'A' or 'B' (got %r)" % (claimed_class,),
        )


def classify_profile_evidence(
    *,
    profile_validated: bool,
    legs_verified: int,
    run_digest: Optional[str],
    gate_outcome: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build the three-class evidence report (pure classification).

    Parameters
    ----------
    profile_validated:
        whether the profile declaration passed the fail-closed
        validation (class A input).
    legs_verified:
        how many scenario legs verified byte-identical round trips
        (class B input).
    run_digest:
        the class-B scenario's run digest (``interop_digest()``).
    gate_outcome:
        OPTIONAL operator-side attachment: a genuine
        :class:`interop.labgate.ProfileLabOutcome` produced by
        ``run_profile_lab_gate`` on a REAL lab.  Class C closes ONLY
        when this outcome is ``PASSED`` with a coherent session id;
        anything else (including a class-B digest) leaves class C
        OPEN -- and attempting to close class C from class-B
        material raises the typed anti-promotion error.

    Raises
    ------
    InteropError
        with ``interop.evidence-class-violation`` when class-B
        material is offered as a class-C closure.
    """
    # Class A: architecture conformance (the frozen coverage).
    class_a = {
        "class": "A",
        "evidence_class": PROFILE_EVIDENCE_CLASS_MAP["A"].value,
        "profile_validated": bool(profile_validated),
        "complete": profile_complete(
            validated=bool(profile_validated), legs_verified=int(legs_verified)
        ),
        "coverage": (
            "5 components (W019 five-g-core, W020 ran, W021 "
            "non-threegpp-access, W032 conformance, W033 "
            "reference-agent) x 7 reference points x cross-family ref "
            "opacity x core purity"
        ),
    }

    # Class B: automated verification (what the deterministic run saw).
    class_b = {
        "class": "B",
        "evidence_class": PROFILE_EVIDENCE_CLASS_MAP["B"].value,
        "legs_verified": int(legs_verified),
        "run_digest": run_digest,
        "basis": (
            "deterministic mixed-access scenario over the in-repo "
            "conformance peers (real loopback sockets; honest "
            "engineering evidence)"
        ),
    }

    # Class C: real interoperability (OPEN unless a genuine PASSED
    # gate outcome is attached operator-side).
    if gate_outcome is None:
        class_c = {
            "class": "C",
            "evidence_class": PROFILE_EVIDENCE_CLASS_MAP["C"].value,
            "status": PROFILE_EVIDENCE_STATUS["real_interop_lab"],
            "statement": REAL_LAB_EVIDENCE_STATEMENT,
        }
    else:
        status = getattr(gate_outcome, "status", "")
        coherent = bool(getattr(gate_outcome, "session_coherent", False))
        if status == "PASSED" and coherent:
            class_c = {
                "class": "C",
                "evidence_class": PROFILE_EVIDENCE_CLASS_MAP["C"].value,
                "status": "closed",
                "basis": (
                    "operator-attached profile lab gate outcome PASSED "
                    "with a coherent session id (the only class-C "
                    "closure)"
                ),
            }
        else:
            class_c = {
                "class": "C",
                "evidence_class": PROFILE_EVIDENCE_CLASS_MAP["C"].value,
                "status": PROFILE_EVIDENCE_STATUS["real_interop_lab"],
                "statement": REAL_LAB_EVIDENCE_STATEMENT,
                "gate_status": status or "unknown",
            }

    return {
        "A": class_a,
        "B": class_b,
        "C": class_c,
        "status": dict(PROFILE_EVIDENCE_STATUS),
    }
