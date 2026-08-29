"""WORK-039 evidence model: the three-class separation.

Expressed over the ACCEPTED WORK-032 ``EvidenceClass`` vocabulary
(reused as DATA; no second vocabulary -- the W037/W038 precedent;
WORK-033, a declared W039 dependency, composes WORK-032 the same way):

- **A -- architecture conformance** (closed in-repo): the harness
  composes ONLY the accepted WORK-015 federation authority (one real
  ``FederationStore`` per domain -- never a second, centralized
  federation authority), the accepted WORK-031 simulator primitives
  (``ScenarioClock`` + ``DeterministicStream`` -- the injected time
  base and documented PRNG), and the accepted WORK-033/W036 agent and
  appliance composition surfaces; no frozen protocol semantic is
  modified; simulation state never becomes protocol truth;

- **B -- automated verification** (closed in-repo): the deterministic
  large-scale multi-domain simulation (horizontal scaling with exact
  predicted object counts, bounded resource envelope, partition/
  failure injection with digest-proven failure-domain isolation,
  revocation propagation with explicit fail-closed convergence
  bounds, post-recovery convergence, TRUE replay verification) and
  the three-participant integration run over real agent/appliance
  surfaces -- all digested and replayable;

- **C -- real deployment evidence**: NOT REQUIRED by the frozen W039
  contract ("Real deployment evidence is not part of the frozen W039
  acceptance criterion unless a new ACR says otherwise").  This
  module enforces that verdict structurally: no in-repo artifact can
  ever mint class-C evidence for WORK-039, and the simulated/
  integration evidence of classes A/B can never be promoted to
  deployment evidence.  If a future ACR requires real deployment
  evidence, it arrives with its own contract -- nothing here
  pre-closes it.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .errors import ScaleError, ScaleReasonCode
from .model import SCALE_EVIDENCE_CLASS_MAP

__all__ = [
    "SCALE_EVIDENCE_STATUS",
    "DEPLOYMENT_EVIDENCE_STATEMENT",
    "classify_scale_evidence",
    "assert_no_deployment_claim",
]


#: The frozen three-class evidence disclosure for WORK-039: classes A
#: and B are closed in-repo; class C (real deployment evidence) is
#: NOT REQUIRED by the frozen contract and is not claimable by any
#: in-repo artifact.
SCALE_EVIDENCE_STATUS: Dict[str, str] = {
    "architecture_conformance": "supported-verified",
    "automated_verification": "supported-verified",
    "real_deployment": "not-required-not-claimable",
}


#: The fixed statement recorded for the not-required class.
DEPLOYMENT_EVIDENCE_STATEMENT = (
    "No real-deployment (multi-region production federation) evidence "
    "is claimed, implied, or closable by this work item: the frozen "
    "WORK-039 contract requires in-repo architecture conformance and "
    "automated large-scale simulation/integration only. The simulated "
    "multi-domain evidence of classes A/B can never be promoted to "
    "real-deployment evidence. If real deployment evidence becomes "
    "required, a new ACR defines its contract; nothing here pre-closes "
    "or pre-satisfies it."
)


def assert_no_deployment_claim(*, claimed_class: str) -> None:
    """Fail-closed guard: no WORK-039 artifact may claim class C
    (real-deployment evidence) -- the anti-promotion rule, enforced in
    code (the W020 lesson; the W037/W038 precedent).

    Classes A and B are the closable classes for this work item; any
    attempt to present them as, or promote them to, class C raises the
    typed evidence-class violation.
    """
    if claimed_class == "C":
        raise ScaleError(
            ScaleReasonCode.EVIDENCE_CLASS_VIOLATION,
            "classes A and B may never be promoted to class C, and "
            "class C (real-deployment evidence) is NOT REQUIRED by the "
            "frozen WORK-039 contract and is not claimable by any "
            "in-repo artifact",
        )
    if claimed_class not in ("A", "B"):
        raise ScaleError(
            ScaleReasonCode.INVALID_INPUT,
            "claimed_class must be 'A' or 'B' (got %r)" % (claimed_class,),
        )


def classify_scale_evidence(
    *,
    composition_validated: bool,
    simulation_run: bool,
    integration_run: bool,
    run_digest: Optional[str],
    deployment_outcome: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build the three-class evidence report (pure classification).

    Parameters
    ----------
    composition_validated:
        whether the harness's composition passed the fail-closed
        authority audit (only accepted surfaces composed; no second
        federation authority; no frozen semantic modified) -- the
        class-A input.
    simulation_run:
        whether the deterministic large-scale simulation produced its
        journaled result (class-B input).
    integration_run:
        whether the agent/appliance integration scenario produced its
        journaled result (class-B input).
    run_digest:
        the class-B runs' digest evidence.
    deployment_outcome:
        REFUSED for this work item: any attempt to attach a
        real-deployment outcome raises the typed anti-promotion error
        (class C is not required and not claimable).

    Raises
    ------
    ScaleError
        with ``scale.evidence-class-violation`` when any class-C
        claim or closure is attempted.
    """
    if deployment_outcome is not None:
        raise ScaleError(
            ScaleReasonCode.EVIDENCE_CLASS_VIOLATION,
            "WORK-039 admits no class-C closure: real-deployment "
            "evidence is not part of the frozen acceptance criterion "
            "and no in-repo artifact can attach a deployment outcome",
        )

    class_a = {
        "class": "A",
        "evidence_class": SCALE_EVIDENCE_CLASS_MAP["A"].value,
        "composition_validated": bool(composition_validated),
        "coverage": (
            "one real WORK-015 FederationStore per domain (never a "
            "second or centralized federation authority) + WORK-031 "
            "ScenarioClock/DeterministicStream injected-time/PRNG "
            "primitives + WORK-033 AgentRuntime and WORK-036 "
            "NetworkAppliance composition surfaces + delivery-plane-"
            "only failure model (simulation never becomes protocol "
            "truth) + no frozen protocol semantic modified"
        ),
    }

    class_b = {
        "class": "B",
        "evidence_class": SCALE_EVIDENCE_CLASS_MAP["B"].value,
        "simulation_run": bool(simulation_run),
        "integration_run": bool(integration_run),
        "run_digest": run_digest,
        "basis": (
            "deterministic large-scale multi-domain simulation (exact "
            "predicted object counts, bounded resource envelope, "
            "digest-proven failure-domain isolation, explicit "
            "revocation-convergence bounds with post-recovery drain, "
            "TRUE replay verification) + the three-participant "
            "integration run over real agent/appliance federation "
            "stores"
        ),
    }

    class_c = {
        "class": "C",
        "evidence_class": SCALE_EVIDENCE_CLASS_MAP["C"].value,
        "status": SCALE_EVIDENCE_STATUS["real_deployment"],
        "statement": DEPLOYMENT_EVIDENCE_STATEMENT,
    }

    return {
        "A": class_a,
        "B": class_b,
        "C": class_c,
        "status": dict(SCALE_EVIDENCE_STATUS),
    }
