"""ADCOS Open RAN/Core interoperability profile (WORK-037).

The interoperability PROFILE over the accepted Open RAN + 5G Core +
non-3GPP access stack: a declarative composition layer that

- declares the complete profile (the accepted W019/W020/W021 adapter
  families + the W032 conformance suite + the W033 reference agent)
  as validated DATA over seven reference points;
- demonstrates MIXED ACCESS at class-B strength (one sacred,
  access-independent ``session_id`` across the 3GPP core leg, the
  3GPP radio leg, the non-3GPP tunnel leg, and back -- byte-identical
  round trips on every leg, cross-family ref opacity, journaled
  access changes, replayable digests);
- composes the three accepted REAL interop gates into the class-C
  interoperability-lab gate (never re-implemented, never bypassed,
  never faked -- RF simulation and in-repo peers stay classes A/B);
- separates the evidence classes structurally (the W020 lesson:
  classes A/B are closed in-repo; class C is closed ONLY by the real
  lab gate's PASSED outcome).

The profile adds NO second authority of any kind: it never mints
identity, sessions, routing, multipath, policy, or transport
verdicts; the session under test is INPUT validated through a
read-only lookup.  Vendor/Open RAN implementation types never enter
ADCOS core (asserted by the battery's core-purity audit).  The
frozen public API surface is asserted by the battery.
"""

from .errors import INTEROP_PREFIX, InteropError, InteropReasonCode
from .model import (
    COMPONENT_FAMILY,
    COMPONENT_REFERENCE_POINTS,
    REQUIRED_REFERENCE_POINTS,
    PROFILE_EVIDENCE_CLASS_MAP,
    AccessLegKind,
    ComponentBinding,
    InteropEvent,
    InteropEventType,
    InteropRunResult,
    LegEvidence,
    ProfileComponentKind,
    ProfileDeclaration,
    ReferencePointKind,
    ScenarioLegName,
    canonical_profile,
    interop_event_list_digest,
    interop_events_canonical_bytes,
)
from .profile import (
    profile_complete,
    reference_points_for_component,
    validate_profile,
)
from .mixed import (
    DEFAULT_PROFILE_PAYLOAD,
    DEFAULT_START_INSTANT,
    SessionFacts,
    check_ref_opacity,
    run_profile_scenario,
    verify_interop_replay,
)
from .labgate import (
    DEFAULT_ORAN_INTEROP_SESSION_ID,
    ORAN_INTEROP_ENV,
    ORAN_INTEROP_SESSION_ID_ENV,
    PROFILE_LEG_SWITCHES,
    LegGateStatus,
    ProfileLabConfig,
    ProfileLabOutcome,
    aggregate_leg_outcomes,
    check_session_coherence,
    oran_interop_gate_enabled,
    profile_lab_runbook,
    run_profile_lab_gate,
)
from .evidence import (
    PROFILE_EVIDENCE_STATUS,
    REAL_LAB_EVIDENCE_STATEMENT,
    assert_no_real_lab_claim,
    classify_profile_evidence,
)

__all__ = [
    # errors
    "INTEROP_PREFIX",
    "InteropError",
    "InteropReasonCode",
    # vocabularies and value records
    "ProfileComponentKind",
    "ReferencePointKind",
    "AccessLegKind",
    "ScenarioLegName",
    "InteropEventType",
    "COMPONENT_FAMILY",
    "COMPONENT_REFERENCE_POINTS",
    "REQUIRED_REFERENCE_POINTS",
    "PROFILE_EVIDENCE_CLASS_MAP",
    "ComponentBinding",
    "ProfileDeclaration",
    "canonical_profile",
    "InteropEvent",
    "interop_events_canonical_bytes",
    "interop_event_list_digest",
    "LegEvidence",
    "InteropRunResult",
    # profile validation
    "validate_profile",
    "reference_points_for_component",
    "profile_complete",
    # class-B scenario
    "DEFAULT_PROFILE_PAYLOAD",
    "DEFAULT_START_INSTANT",
    "SessionFacts",
    "check_ref_opacity",
    "run_profile_scenario",
    "verify_interop_replay",
    # class-C lab gate
    "ORAN_INTEROP_ENV",
    "ORAN_INTEROP_SESSION_ID_ENV",
    "DEFAULT_ORAN_INTEROP_SESSION_ID",
    "PROFILE_LEG_SWITCHES",
    "ProfileLabConfig",
    "LegGateStatus",
    "ProfileLabOutcome",
    "oran_interop_gate_enabled",
    "check_session_coherence",
    "aggregate_leg_outcomes",
    "run_profile_lab_gate",
    "profile_lab_runbook",
    # evidence model
    "PROFILE_EVIDENCE_STATUS",
    "REAL_LAB_EVIDENCE_STATEMENT",
    "assert_no_real_lab_claim",
    "classify_profile_evidence",
]
