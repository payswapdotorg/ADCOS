"""ADCOS Future IMT / 6G adapter profile (WORK-038).

The synthetic future-profile conformance layer over the ACCEPTED
adapter/registry/core contracts: a hypothetical future access
technology (IMT-2030) integrated as an ADDITIVE adapter/profile and
proven to change nothing else:

- **no core schema change** -- the technology identifier is the
  registry's own RESERVED ``access.3gpp.nr.imt2030`` path (reserved
  since WORK-002 for exactly this additive future registration); the
  registry is digest-pinned across every run and never mutated;
- **additive capabilities** -- capability references (KNOWN and
  profile-scoped UNKNOWN_BUT_WELL_FORMED) are carried as DATA by
  reference; the WORK-005 authority's own open-world rule keeps them
  non-authoritative (a required unknown capability fails closed even
  when both peers carry the data);
- **routing/session/resource/policy unchanged** -- the synthetic
  conformance run digest-proves all four core layers byte-identical
  for the same fixed inputs before and after the future adapter was
  registered and fully exercised (the nine-operation WORK-016
  contract over a REAL runtime wired to a REAL WORK-012 store);
- **open-world safety** -- an arbitrary UNKNOWN-but-well-formed
  future identifier registers as DATA, is preserved verbatim, and
  provably gains no authority;
- **W029 coexistence preserved** -- the future profile adds nothing
  at the protocol-version line (envelope disposition and mixed-
  version negotiation are the accepted authorities' own verdicts).

The profile adds NO second authority of any kind and imports no
vendor SDK, radio/PHY type, or platform API (LOCK-016/LOCK-017; the
battery's purity audits pin this).  The frozen public API surface is
asserted by the battery.
"""

from __future__ import annotations

from .errors import FUTURE_PREFIX, FutureError, FutureReasonCode
from .model import (
    CANONICAL_FUTURE_TECHNOLOGY_ID,
    CORE_EQUIVALENCE_LAYERS,
    FUTURE_EVIDENCE_CLASS_MAP,
    UNKNOWN_FUTURE_TECHNOLOGY_ID,
    CoreEquivalenceRecord,
    FutureEvent,
    FutureEventType,
    FutureProfileDeclaration,
    FutureRunResult,
    canonical_future_profile,
    future_event_list_digest,
    future_events_canonical_bytes,
)
from .profile import (
    classify_technology_id,
    profile_complete,
    registry_untouched,
    unknown_id_gained_no_authority,
    validate_future_profile,
)
from .adapter import (
    FUTURE_ADAPTER_LABEL,
    STEP_CHARGES,
    FutureTechnologyAdapter,
    future_descriptor,
)
from .scenario import (
    CANONICAL_INSTANCE_LABEL,
    SCENARIO_START_INSTANT,
    UNKNOWN_ID_INSTANCE_LABEL,
    registry_file_digest,
    run_future_profile_conformance,
    scenario_summary,
    verify_future_replay,
)
from .evidence import (
    FUTURE_EVIDENCE_STATUS,
    SYNTHETIC_EVIDENCE_STATEMENT,
    assert_no_real_world_claim,
    classify_future_evidence,
)
from .coexistence import (
    FUTURE_PROTOCOL_MAJOR,
    FUTURE_PROFILE_PROTOCOL_PROFILE,
    FutureCapabilityNegotiation,
    coexistence_with_future_profile,
    future_capability_negotiation,
    future_envelope_disposition,
)

__all__ = [
    # errors
    "FUTURE_PREFIX",
    "FutureError",
    "FutureReasonCode",
    # vocabularies and value records
    "FutureEventType",
    "FUTURE_EVIDENCE_CLASS_MAP",
    "CORE_EQUIVALENCE_LAYERS",
    "FutureProfileDeclaration",
    "CANONICAL_FUTURE_TECHNOLOGY_ID",
    "canonical_future_profile",
    "UNKNOWN_FUTURE_TECHNOLOGY_ID",
    "FutureEvent",
    "future_events_canonical_bytes",
    "future_event_list_digest",
    "CoreEquivalenceRecord",
    "FutureRunResult",
    # profile validation
    "validate_future_profile",
    "classify_technology_id",
    "profile_complete",
    "registry_untouched",
    "unknown_id_gained_no_authority",
    # the future adapter (SDK bridge)
    "FUTURE_ADAPTER_LABEL",
    "STEP_CHARGES",
    "FutureTechnologyAdapter",
    "future_descriptor",
    # the synthetic conformance scenario (class B)
    "SCENARIO_START_INSTANT",
    "CANONICAL_INSTANCE_LABEL",
    "UNKNOWN_ID_INSTANCE_LABEL",
    "run_future_profile_conformance",
    "verify_future_replay",
    "registry_file_digest",
    "scenario_summary",
    # W029 coexistence (delegated verdicts)
    "FUTURE_PROTOCOL_MAJOR",
    "FUTURE_PROFILE_PROTOCOL_PROFILE",
    "FutureCapabilityNegotiation",
    "coexistence_with_future_profile",
    "future_capability_negotiation",
    "future_envelope_disposition",
    # evidence model
    "FUTURE_EVIDENCE_STATUS",
    "SYNTHETIC_EVIDENCE_STATEMENT",
    "assert_no_real_world_claim",
    "classify_future_evidence",
]
