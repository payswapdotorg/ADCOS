"""ADCOS 5G RAN integration adapter package (WORK-020).

A new sub-package WITHIN the frozen ``/adapters`` module boundary
(``spec/architecture.md`` §29; LOCK-002: 5G NR is implemented through
an access adapter -- 3GPP RAN/core functions remain outside the ADCOS
core domain; LOCK-016: external RAN/modem/SDR implementations remain
behind adapter/provider interfaces).  Peer of ``adapters.ip``
(WORK-018) and ``adapters.fivegc`` (WORK-019) -- it defines its OWN
:class:`RanContract` ABC (NOT a subtype of the WORK-016
:class:`adapters.contract.AdapterContract`), because the RAN domain
has its own vocabulary (gNB / CU / DU / RU / cell / RNTI / DRB / QFI /
F1 / E1 / fronthaul split), distinct from the W016
allocate/release/bearer vocabulary.  The WORK-016 SDK is USED, not
reinvented: the later bridge task implements the SDK's nine-op
``AdapterContract`` over any ``RanContract`` implementation.

Authority boundaries (the package's central invariants)::

    RAN INTEGRATION
        != SESSION AUTHORITY      (session_id is sacred and
                                   access-independent -- LOCK-006; the
                                   boundary never mints, mutates, or
                                   re-derives it)
        != RAN ROUTE IDENTITY     (bearer/RNTI/DRB are RAN-side
                                   opaque identity, never collapsed
                                   onto session_id -- R1 invariant,
                                   checked mechanically at the seam)
        != IDENTITY AUTHORITY     (WORK-004)
        != RESOURCE AUTHORITY     (WORK-008; PRB/DRB accounting is
                                   mapped DATA)
        != POLICY AUTHORITY       (caller-supplied policy DATA)
        != TOPOLOGY AUTHORITY     (CU/DU/RU boundary mapping is
                                   adapter-owned DATA)
        != ACCESS/VENDOR AUTHORITY (LOCK-016/017; concrete RAN stacks
                                   -- OpenAirInterface, O-CU/O-DU/O-RU
                                   style open implementations, future
                                   RAN -- plug in behind the seam)
        != RAN STATE AUTHORITY    (gNB/CU/DU/RU/cell/RRC state lives
                                   in the adapter, NEVER in core)

Foundation modules (W020-a1) + mediation and reference model
(W020-a2) + runtime/facade/SDK-bridge (W020-a3) + conformance peer,
production-shaped adapter, and the real SDR-lab interop gate
(W020-a4):
- contract.py    RanContract ABC (frozen 14-op surface) + RanContext
                 immutable least-authority facade (ran_integration_id +
                 injected instant + step budget) + BearerView/GnbView
                 secret-free projections + RAN_CONTRACT_OPERATIONS
- model.py       HealthState/CellState/DuplexMode/RanSplitOption/
                 LinkMetricName vocabularies, CellSpec/CellDescriptor,
                 Cu/Du/Ru elements + RanSplitTopology,
                 GnbProvisionRequest, RanHealthSnapshot/
                 RanResourceSnapshot/RanObservation, RanDrb/
                 RanUeContext (adapter-private), capability-id
                 REFERENCES (3GPP TS 38.300/38.401/38.473/38.463/
                 38.331/38.321/38.413/23.501 §5.4 and O-RAN.WG4
                 shapes as DATA; no radio, no vendor SDK)
- validation.py  seam validators: session-id shape, opaque-ref
                 grammar (ran:<kind>:<digest-or-counter>), the R1
                 mechanical separation check, LOCK-023
                 credential-like-material rejection, observation and
                 provision-request shape validators
- serialization.py  canonical-JSON for the outward-facing state
- errors.py      RanError + RanReasonCode + RanFailure
- sandbox.py     SandboxedRan: the failure-isolation mediator
                 (exception isolation incl. BaseException with class
                 name only, per-op contract-shape validation with
                 discard on violation, fixed STEP_CHARGES budget,
                 least-authority context per call) + RanOpResult
- engine.py      ReferenceRanEngine: the deterministic in-memory
                 reference model of the contract (NOT a real RAN
                 stack; content-derived refs, RNTI counter from
                 0x4601, DRB 1/QFI 5, 1-PRB bearer reservations,
                 byte-stable observations)
- manager.py     RanManager: the runtime -- register_implementation
                 wraps EACH impl in its OWN SandboxedRan (R4
                 per-binding ownership; make_default swaps the default
                 for NEW work only), the opaque adcos:ran:binding:
                 <hex> binding-token registry (callers never hold the
                 raw bearer ref), three-layer R1 identity-separation
                 enforcement (exact session_id storage, bearer/session
                 collapse rejection, requirements-map smuggling
                 rejection), content-derived event ids, and the B2
                 canonical snapshot (implementation_label excluded;
                 byte-identical across impls) + DEFAULT_INTEGRATION_ID
- session.py     AccessPathSession: the ordinary application facade
                 (connect/send/recv/close with standard session
                 semantics only -- LOCK-019 analog; no ADCOS/RAN
                 token, no RNTI/DRB/cell id ever visible; the WORK-020
                 definition-of-done surface: "ADCOS can provision/use
                 a standards-compliant 5G access path")
- bridge.py      RanTechnologyAdapter: the WORK-016 SDK bridge (the
                 adapter translation layer: RAN implementation ->
                 adapter translation -> generic AdapterContract ->
                 ADCOS capabilities/resources/session mapping);
                 imports ONLY AdapterContract+AdapterContext from the
                 SDK (the sanctioned dependency direction) and stays a
                 thin translation with no state beyond the label
- conformance.py ReferenceRanConformanceServer -- a REAL REST-over-
                 HTTP RAN control-plane peer that runs as user z (no
                 root, no Docker, no SDR); O1/E2-style reference
                 shapes (TS 38.413 NG setup analog, O-RAN.WG1 O1
                 management style, O-RAN.WG2 E2-style reporting) over
                 a real http.server thread; honestly disclosed as an
                 ADCOS test implementation, NOT a real RAN stack (it
                 cannot satisfy the frozen SDR-lab acceptance
                 criterion -- that is the interop gate's job)
- openran.py     OpenRanAdapter -- PRODUCTION-SHAPED real-HTTP
                 adapter targeting real OpenAirInterface / O-RAN-style
                 lab deployments through a configured HTTP control
                 endpoint (RAN_CONTROL_URL via the explicit from_env
                 opt-in); implements the 14-op RanContract with real
                 stdlib http.client requests; NOT itself a RAN stack
                 (LOCK-016/017); in-sandbox evidence path is the
                 conformance peer
- interop_env_probe.py  the SDR-lab environment-capability probe +
                 anti-faking peer-kind guard (the W019 hardening
                 mirrored): the explicit [SDR-LAB CAPABILITY MATRIX]
                 renderer and RAN_PEER_KIND FORBIDDEN short-circuit
                 that fires BEFORE any network probe
- openran_interop.py    the environment-gated REAL SDR-lab interop
                 gate (RAN_INTEROP=1): the frozen WORK-020 acceptance
                 path -- SKIP/FORBIDDEN/UNREACHABLE/FAILED/PASSED with
                 the six [SDR]/[CTRL]/[CELL]/[UE]/[DRB]/[IP] evidence
                 lines and full provenance; NO in-repo-peer fallback,
                 NO new PASSED path beyond the real phases

All instants are injected (WORK-003 grammar); no wall clock.  No
randomness anywhere in the family.  Integer-only accounting.
"""

from __future__ import annotations

from .contract import (
    RAN_CONTRACT_OPERATIONS,
    RAN_CONTEXT_SURFACE,
    BearerView,
    GnbView,
    RanContext,
    RanContract,
)
from .errors import RAN_PREFIX, RAN_REF_PREFIX, RanError, RanFailure, RanReasonCode
from .model import (
    RAN_CAPABILITY_CELL_FDD,
    RAN_CAPABILITY_CELL_TDD,
    RAN_CAPABILITY_CU_DU_SPLIT_F1,
    RAN_CAPABILITY_DRB_QOS_FLOW,
    RAN_CAPABILITY_GNB_PROVISION,
    RAN_CAPABILITY_O_RU_FRONTHAUL,
    RAN_CAPABILITY_REFERENCES,
    CellDescriptor,
    CellSpec,
    CellState,
    CuElement,
    DuplexMode,
    DuElement,
    GnbProvisionRequest,
    HealthState,
    LinkMetricName,
    RanDrb,
    RanHealthSnapshot,
    RanObservation,
    RanResourceSnapshot,
    RanSplitOption,
    RanSplitTopology,
    RanUeContext,
    RuElement,
)
from .serialization import to_canonical_bytes
from .validation import (
    assert_ref_session_separation,
    reject_credential_like_text,
    validate_gnb_provision_request,
    validate_opaque_ref,
    validate_ran_capability_reference,
    validate_ran_observation,
    validate_session_id,
)
from .sandbox import (
    DEFAULT_STEP_BUDGET,
    FAILURE_THRESHOLD_DEGRADED,
    FAILURE_THRESHOLD_FAILED,
    STEP_CHARGES,
    RanOpResult,
    SandboxedRan,
)
from .engine import (
    FIRST_RNTI,
    LAST_RNTI,
    RAN_ALLOCATION_KINDS,
    RAN_ALLOCATION_KIND_CELL,
    RAN_ALLOCATION_KIND_PRB,
    RAN_ALLOCATION_KIND_RADIO_CAPACITY,
    ReferenceRanEngine,
)
from .manager import (
    DEFAULT_INTEGRATION_ID,
    RanEvent,
    RanManager,
)
from .session import AccessPathSession
from .bridge import RanTechnologyAdapter
from .conformance import ReferenceRanConformanceServer
from .openran import (
    DEFAULT_RAN_CONTROL_URL,
    RAN_CONTROL_URL_ENV,
    OpenRanAdapter,
)
from .interop_env_probe import (
    RAN_PEER_KIND_ENV,
    RanCapabilityReport,
    RanCheck,
    RanEnvProbeConfig,
    probe_ran_interop_capability,
)
from .openran_interop import (
    DEFAULT_RAN_INTEROP_CELL_ID,
    DEFAULT_RAN_INTEROP_PAYLOAD,
    DEFAULT_RAN_INTEROP_SESSION_ID,
    RAN_INTEROP_CELL_ID_ENV,
    RAN_INTEROP_ENV,
    RAN_INTEROP_SESSION_ID_ENV,
    RanInteropConfig,
    RanInteropOutcome,
    ran_interop_gate_enabled,
    run_openran_interop,
)

__all__ = [
    # Contract surface
    "RanContract",
    "RanContext",
    "RAN_CONTEXT_SURFACE",
    "RAN_CONTRACT_OPERATIONS",
    "BearerView",
    "GnbView",
    # Model
    "HealthState",
    "CellState",
    "DuplexMode",
    "RanSplitOption",
    "LinkMetricName",
    "RAN_CAPABILITY_GNB_PROVISION",
    "RAN_CAPABILITY_CELL_TDD",
    "RAN_CAPABILITY_CELL_FDD",
    "RAN_CAPABILITY_DRB_QOS_FLOW",
    "RAN_CAPABILITY_CU_DU_SPLIT_F1",
    "RAN_CAPABILITY_O_RU_FRONTHAUL",
    "RAN_CAPABILITY_REFERENCES",
    "CellSpec",
    "CellDescriptor",
    "CuElement",
    "DuElement",
    "RuElement",
    "RanSplitTopology",
    "GnbProvisionRequest",
    "RanHealthSnapshot",
    "RanResourceSnapshot",
    "RanObservation",
    "RanDrb",
    "RanUeContext",
    # Validation (seam validators)
    "validate_session_id",
    "validate_opaque_ref",
    "assert_ref_session_separation",
    "reject_credential_like_text",
    "validate_ran_capability_reference",
    "validate_ran_observation",
    "validate_gnb_provision_request",
    # Errors
    "RanError",
    "RanFailure",
    "RanReasonCode",
    "RAN_PREFIX",
    "RAN_REF_PREFIX",
    # Serialization
    "to_canonical_bytes",
    # Sandbox (mediation / failure isolation)
    "SandboxedRan",
    "RanOpResult",
    "DEFAULT_STEP_BUDGET",
    "FAILURE_THRESHOLD_DEGRADED",
    "FAILURE_THRESHOLD_FAILED",
    "STEP_CHARGES",
    # Reference engine (deterministic in-memory model)
    "ReferenceRanEngine",
    "RAN_ALLOCATION_KIND_PRB",
    "RAN_ALLOCATION_KIND_CELL",
    "RAN_ALLOCATION_KIND_RADIO_CAPACITY",
    "RAN_ALLOCATION_KINDS",
    "FIRST_RNTI",
    "LAST_RNTI",
    # Runtime (the manager + binding registry)
    "RanManager",
    "RanEvent",
    "DEFAULT_INTEGRATION_ID",
    # App facade (LOCK-019 analog application transparency)
    "AccessPathSession",
    # WORK-016 SDK bridge (the adapter translation layer)
    "RanTechnologyAdapter",
    # Conformance peer (real-socket reference RAN control plane)
    "ReferenceRanConformanceServer",
    # Production-shaped real-HTTP Open RAN adapter
    "OpenRanAdapter",
    "DEFAULT_RAN_CONTROL_URL",
    "RAN_CONTROL_URL_ENV",
    # SDR-lab environment-capability probe + anti-faking guard
    "RAN_PEER_KIND_ENV",
    "RanCheck",
    "RanCapabilityReport",
    "RanEnvProbeConfig",
    "probe_ran_interop_capability",
    # Real SDR-lab interop gate (environment-gated, frozen acceptance)
    "RAN_INTEROP_ENV",
    "RAN_INTEROP_SESSION_ID_ENV",
    "RAN_INTEROP_CELL_ID_ENV",
    "DEFAULT_RAN_INTEROP_SESSION_ID",
    "DEFAULT_RAN_INTEROP_CELL_ID",
    "DEFAULT_RAN_INTEROP_PAYLOAD",
    "RanInteropConfig",
    "RanInteropOutcome",
    "ran_interop_gate_enabled",
    "run_openran_interop",
]
