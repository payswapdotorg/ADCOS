"""WORK-038 synthetic conformance scenario (class B).

The deterministic in-repo run that closes the work item's automated
acceptance dimensions.  It composes ONLY accepted authorities through
their public contracts (the WORK-032 ``conformance.world`` pattern:
sanctioned transitive composition, never a second authority) and
observes, journals, and digests four facts:

1. **No core schema change** -- the WORK-002 access-profile registry
   file is digest-pinned before and after the run; the reserved
   ``access.3gpp.nr.imt2030`` identifier is used exactly as reserved
   (status ``reserved`` -- the profile never activates, mutates, or
   extends the registry).
2. **Additive registration** -- the future profile's descriptor +
   adapter register on a REAL ``AdapterRuntime`` wired exactly like
   the reference agent wires it (``AdapterRuntime(session_store=...)``
   over a REAL WORK-012 store), and the full nine-operation WORK-016
   contract is exercised through the runtime, including binding a
   REAL established session (read-only verification; the store's
   canonical bytes are digest-proven unchanged across the binding).
3. **Open-world safety** -- a second adapter over an arbitrary
   UNKNOWN-but-well-formed future identifier registers as DATA, is
   preserved verbatim, and provably gains no authority (it stays
   absent from the known-id set; classification stays UNKNOWN).
4. **Core equivalence** -- the routing, session, resource, and policy
   layers produce byte-identical canonical digests for the SAME fixed
   inputs before and after the future adapter was registered and
   exercised (the handoff's byte-identity criterion, as a digest
   record).

Determinism: fixed instants, fixed node ids, fixed key-free fixtures;
no wall clock, no randomness, no network, no environment reads.  Two
honest runs of the same profile always produce the same
``future_digest`` (replay verification re-runs and compares).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from adapters import AdapterRuntime, GenericAdapter
from adapters.validation import (
    ACCESS_PROFILE_REGISTRY_PATH,
    classify_access_technology_id,
)

from .adapter import FutureTechnologyAdapter, future_descriptor
from .errors import FutureError, FutureReasonCode
from .model import (
    CANONICAL_FUTURE_TECHNOLOGY_ID,
    UNKNOWN_FUTURE_TECHNOLOGY_ID,
    CoreEquivalenceRecord,
    FutureEvent,
    FutureEventType,
    FutureProfileDeclaration,
    FutureRunResult,
    canonical_future_profile,
)
from .profile import (
    classify_technology_id,
    registry_untouched,
    unknown_id_gained_no_authority,
    validate_future_profile,
)

__all__ = [
    "SCENARIO_START_INSTANT",
    "UNKNOWN_ID_INSTANCE_LABEL",
    "CANONICAL_INSTANCE_LABEL",
    "run_future_profile_conformance",
    "verify_future_replay",
    "registry_file_digest",
]

#: The injected scenario instants (never wall clock).
SCENARIO_START_INSTANT = "2026-06-01T00:00:00Z"

#: Fixed instance labels (deterministic adapter ids).
CANONICAL_INSTANCE_LABEL = "future-radio-0"
UNKNOWN_ID_INSTANCE_LABEL = "future-radio-x"

_T0 = "2026-06-01T00:00:00Z"
_NOW = "2026-06-01T12:00:00Z"
_FRESH = "2026-12-31T23:59:59Z"

_NODE_A = "adcos:node:test.future.v1:" + "a" * 64
_NODE_B = "adcos:node:test.future.v1:" + "b" * 64


def registry_file_digest() -> str:
    """The sha256 digest of the WORK-002 access-profile registry file.

    Pins the registry BYTES (the no-core-schema-change substrate):
    ``spec/schemas/registries/access-profile-registry.json`` consumed
    read-only exactly as ``adapters.validation`` consumes it.
    """
    return "sha256:" + hashlib.sha256(
        ACCESS_PROFILE_REGISTRY_PATH.read_bytes()
    ).hexdigest()


# ----------------------------------------------------------------------
# The real authority world (the WORK-032 conformance-world pattern)
# ----------------------------------------------------------------------


def _policy_decision() -> Any:
    """A genuine WORK-010 policy decision over fixed inputs (the
    routing/session INPUT surface; not a policy authority itself)."""
    from policy.model import PolicyDecision

    placeholder = PolicyDecision(
        decision_id="0" * 64, effect="allow", code="allow", detail="fixture",
        matched_rule_ids=("r1",), policy_set_id="ps-1", policy_set_version=2,
        evaluation_instant=_NOW,
    )
    digest = hashlib.sha256(placeholder.canonical_bytes()).hexdigest()
    return PolicyDecision(
        decision_id=digest, effect="allow", code="allow", detail="fixture",
        matched_rule_ids=("r1",), policy_set_id="ps-1", policy_set_version=2,
        evaluation_instant=_NOW,
    )


def _build_world() -> Tuple[Dict[str, str], Any, str]:
    """Build the fixed core world: topology + routing decision + an
    ESTABLISHED real WORK-012 session over a real WORK-008 resource
    store.  The SAME fixed inputs always yield the same digests."""
    from resources import ResourceStore
    from routing import LinkMetrics, RoutingContext, RoutingEngine
    from sessions import SessionState, SessionStore
    from topology import (
        ClaimType,
        SourceClass,
        TopologyClaim,
        TopologyGraph,
        make_link_subject,
    )

    graph = TopologyGraph()
    graph.merge(TopologyClaim(
        subject=make_link_subject(_NODE_A, _NODE_B), reporter=_NODE_A,
        claim_type=ClaimType.LINK_STATE, value="up",
        source_class=SourceClass.SELF_ADVERTISEMENT,
        issued_at=_T0, freshness_until=_FRESH, sequence=1, provenance="",
    ))
    graph.merge(TopologyClaim(
        subject=_NODE_B, reporter=_NODE_A,
        claim_type=ClaimType.REACHABLE, value="true",
        source_class=SourceClass.DIRECT_OBSERVATION,
        issued_at=_T0, freshness_until=_FRESH, sequence=1, provenance="",
    ))
    resources = ResourceStore()
    decision = _policy_decision()
    context = RoutingContext(
        source_node_id=_NODE_A, destination_node_id=_NODE_B,
        topology=graph, resources=resources, evaluation_instant=_NOW,
        policy_decision=decision,
        link_metrics={
            make_link_subject(_NODE_A, _NODE_B): LinkMetrics(
                latency_ms=10, loss_basis_points=0, capacity_bps=1_000_000,
                energy_cost_millijoules=100, confidence_basis_points=10_000,
                observed_at=_T0, freshness_until=_FRESH,
            ),
        },
    )
    result = RoutingEngine().evaluate(context)
    if result.decision is None or result.decision.selected is None:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "fixture routing evaluation failed: %s" % (result.code,),
        )
    store = SessionStore()
    created = store.create(
        result.decision, decision,
        source_node_id=_NODE_A, destination_node_id=_NODE_B,
        creation_instant=_NOW,
    )
    if not created.ok or created.session is None:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "fixture session creation failed",
        )
    session_id = created.session.session_id
    store.transition(session_id, SessionState.AUTHORIZED, event_instant=_NOW)
    store.transition(session_id, SessionState.ESTABLISHED, event_instant=_NOW)

    digests = {
        "routing": "sha256:" + hashlib.sha256(
            _canon(result.decision.to_dict())
        ).hexdigest(),
        "sessions": "sha256:" + hashlib.sha256(
            store.to_canonical_bytes()
        ).hexdigest(),
        "resources": "sha256:" + hashlib.sha256(
            resources.to_canonical_bytes()
        ).hexdigest(),
        "policy": "sha256:" + hashlib.sha256(
            decision.canonical_bytes()
        ).hexdigest(),
    }
    return digests, store, session_id


def _canon(value: Any) -> bytes:
    from protocol.canonicalization import canonical_json_bytes

    return canonical_json_bytes(value)


# ----------------------------------------------------------------------
# The journal
# ----------------------------------------------------------------------


class _Journal:
    """The append-only event journal (deterministic sequence)."""

    def __init__(self) -> None:
        self._events: List[FutureEvent] = []

    def record(self, event_type: str, instant: str, detail: str) -> None:
        self._events.append(FutureEvent(
            sequence=len(self._events) + 1,
            event_type=event_type,
            instant=instant,
            detail=detail,
        ))

    def events(self) -> Tuple[FutureEvent, ...]:
        return tuple(self._events)


# ----------------------------------------------------------------------
# The scenario
# ----------------------------------------------------------------------


def run_future_profile_conformance(
    profile: Optional[FutureProfileDeclaration] = None,
    *,
    start_instant: str = SCENARIO_START_INSTANT,
) -> FutureRunResult:
    """Run the synthetic future-profile conformance scenario.

    Class B (automated verification) over REAL accepted authorities:
    the registry is pinned, the profile validated, the adapter
    registered and fully exercised over a real runtime + real
    established session, the unknown-id path demonstrated, and the
    four core layers digest-proven equivalent.  The returned record is
    pure DATA; nothing about any authority is mutated.
    """
    if profile is None:
        profile = canonical_future_profile()
    if not isinstance(start_instant, str) or not start_instant:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "start_instant must be a non-empty injected instant string",
        )

    journal = _Journal()

    # 1. Validate the declaration (fail closed).
    validated = validate_future_profile(profile)
    journal.record(
        FutureEventType.PROFILE_VALIDATED, start_instant,
        "declaration validated: technology=%s versions=%s capabilities=%d "
        "digest=%s"
        % (profile.technology_id, ",".join(profile.profile_versions),
           len(profile.capability_references), profile.digest()),
    )

    # 2. Classify the technology id through the ACCEPTED WORK-002 rule.
    classification = classify_technology_id(profile.technology_id)
    journal.record(
        FutureEventType.TECHNOLOGY_CLASSIFIED, start_instant,
        "technology %s classifies %s (registry verdict, read-only)"
        % (profile.technology_id, classification),
    )

    # 3. Pin the registry BEFORE (no core schema change: substrate).
    registry_before = registry_file_digest()

    # 4. Baseline core world + digests (the "before" probe).
    before_digests, store, session_id = _build_world()
    sessions_before = before_digests["sessions"]

    # 5. The composed runtime: wired exactly like the reference agent
    #    wires its AdapterRuntime (agent/runtime.py: a real WORK-012
    #    store, read-only binding verification).
    runtime = AdapterRuntime(session_store=store)

    # 6. Register the future adapter (the technology enters as DATA).
    descriptor = future_descriptor(profile, CANONICAL_INSTANCE_LABEL)
    implementation = FutureTechnologyAdapter(profile.capability_references)
    runtime.register(descriptor, implementation, now=start_instant)
    adapter_id = descriptor.adapter_id
    journal.record(
        FutureEventType.ADAPTER_REGISTERED, start_instant,
        "future adapter registered as DATA: %s (technology=%s, no "
        "registry/schema change)" % (adapter_id, profile.technology_id),
    )

    # 7. Register the UNKNOWN future id adapter (open-world path).
    unknown_descriptor = future_descriptor(
        _unknown_profile(), UNKNOWN_ID_INSTANCE_LABEL
    )
    runtime.register(
        unknown_descriptor, GenericAdapter(), now=start_instant
    )
    unknown_adapter_id = unknown_descriptor.adapter_id

    # 8. Exercise the nine WORK-016 contract operations through the
    #    runtime over the canonical adapter.
    opened = runtime.open_adapter(adapter_id, now=start_instant)
    if not opened.ok:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "future adapter failed to open: %s" % (opened.failure,),
        )
    journal.record(
        FutureEventType.ADAPTER_OPENED, start_instant,
        "adapter opened through the runtime (budget-mediated)",
    )

    capabilities = runtime.capabilities(adapter_id, now=start_instant)
    if tuple(capabilities) != tuple(profile.capability_references):
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "exposed capabilities drifted from the declaration",
        )
    journal.record(
        FutureEventType.CAPABILITIES_EXPOSED, start_instant,
        "capabilities exposed by reference: %s"
        % ",".join(capabilities),
    )

    observed = runtime.observe(adapter_id, now=start_instant)
    if not observed.ok:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "observe failed: %s" % (observed.failure,),
        )
    journal.record(
        FutureEventType.LINK_OBSERVED, start_instant,
        "generic link metrics observed (data, never topology truth)",
    )

    allocation = runtime.allocate(
        adapter_id, kind=profile.resource_kind, quantity=10,
        unit=profile.resource_unit, purpose="future-conformance",
        now=start_instant,
    )
    if not allocation.ok or allocation.value is None:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "allocate failed: %s" % (allocation.failure,),
        )
    allocation_id = allocation.value.allocation_id
    journal.record(
        FutureEventType.CAPACITY_ALLOCATED, start_instant,
        "adapter-scoped capacity allocated (mapping only, never "
        "WORK-008 accounting): %s" % allocation_id,
    )

    released = runtime.release(allocation_id, now=start_instant)
    if not released.ok:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "release failed: %s" % (released.failure,),
        )
    journal.record(
        FutureEventType.CAPACITY_RELEASED, start_instant,
        "adapter-scoped capacity released",
    )

    binding = runtime.bind_session(
        adapter_id, session_id=session_id, now=start_instant
    )
    if not binding.ok or binding.value is None:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "bind_session failed: %s" % (binding.failure,),
        )
    binding_id = binding.value.binding_id
    journal.record(
        FutureEventType.SESSION_BOUND, start_instant,
        "REAL established session bound read-only: %s (session store "
        "canonical bytes digest-proven unchanged)" % binding_id,
    )

    # The read-only proof: binding added nothing to the session store.
    sessions_after_bind = (
        "sha256:" + hashlib.sha256(store.to_canonical_bytes()).hexdigest()
    )
    if sessions_after_bind != sessions_before:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "session binding mutated the WORK-012 store (read-only "
            "violation)",
        )

    unbound = runtime.unbind_session(binding_id, now=start_instant)
    if not unbound.ok:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "unbind_session failed: %s" % (unbound.failure,),
        )
    journal.record(
        FutureEventType.SESSION_UNBOUND, start_instant,
        "bearer unbound (explicit teardown)",
    )

    health = runtime.health(adapter_id, now=start_instant)
    journal.record(
        FutureEventType.HEALTH_REPORTED, start_instant,
        "health reported (adapter-local, never authoritative): %s"
        % health.state,
    )

    closed = runtime.close_adapter(adapter_id, now=start_instant)
    if not closed.ok:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "close failed: %s" % (closed.failure,),
        )
    journal.record(
        FutureEventType.ADAPTER_CLOSED, start_instant,
        "adapter closed through the runtime",
    )

    # 9. The unknown-id authority facts (open-world safety).
    unknown_classification = classify_access_technology_id(
        UNKNOWN_FUTURE_TECHNOLOGY_ID
    )
    still_unknown = unknown_id_gained_no_authority(
        technology_id=UNKNOWN_FUTURE_TECHNOLOGY_ID,
        classification=unknown_classification,
    )
    if not still_unknown:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "the unknown future id unexpectedly gained authority",
        )
    snapshot = runtime.snapshot()
    preserved_verbatim = any(
        entry.get("descriptor", {}).get("access_technology_id")
        == UNKNOWN_FUTURE_TECHNOLOGY_ID
        for entry in snapshot.get("adapters", ())
    )
    if not preserved_verbatim:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "the unknown future id was not preserved verbatim in the "
            "runtime snapshot",
        )
    journal.record(
        FutureEventType.UNKNOWN_ID_PRESERVED, start_instant,
        "unknown-but-well-formed id %s registered as DATA, preserved "
        "verbatim, classification stays %s, absent from the known-id "
        "set (no authority gained)"
        % (UNKNOWN_FUTURE_TECHNOLOGY_ID, unknown_classification),
    )

    # 10. Pin the registry AFTER (no core schema change: the fact).
    registry_after = registry_file_digest()
    if not registry_untouched(
        digest_before=registry_before, digest_after=registry_after
    ):
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "the access-profile registry changed during the run "
            "(core schema change)",
        )
    journal.record(
        FutureEventType.REGISTRY_PINNED, start_instant,
        "access-profile registry digest-stable across the run: %s "
        "(no core schema change)" % registry_before,
    )

    # 11. Core equivalence: the SAME fixed inputs, fresh world, AFTER
    #     the future adapter was registered and exercised.
    after_digests, _store_b, _sid_b = _build_world()
    sessions_after = (
        "sha256:" + hashlib.sha256(store.to_canonical_bytes()).hexdigest()
    )
    equivalence = CoreEquivalenceRecord(
        layers=(
            ("routing", before_digests["routing"], after_digests["routing"],
             before_digests["routing"] == after_digests["routing"]),
            ("sessions", sessions_before, sessions_after,
             sessions_before == sessions_after),
            ("resources", before_digests["resources"],
             after_digests["resources"],
             before_digests["resources"] == after_digests["resources"]),
            ("policy", before_digests["policy"], after_digests["policy"],
             before_digests["policy"] == after_digests["policy"]),
        )
    )
    if not equivalence.all_equal():
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "core layers drifted across the future-adapter exercise",
        )
    journal.record(
        FutureEventType.CORE_EQUIVALENCE_VERIFIED, start_instant,
        "routing/sessions/resources/policy canonical digests "
        "byte-identical for the same inputs before and after the "
        "future adapter registration + full contract exercise",
    )

    journal.record(
        FutureEventType.PROFILE_VERIFIED, start_instant,
        "synthetic future-profile conformance verified (class B)",
    )

    return FutureRunResult(
        profile_digest=profile.digest(),
        technology_classification=classification,
        registry_digest_before=registry_before,
        registry_digest_after=registry_after,
        adapter_ids=(adapter_id, unknown_adapter_id),
        unknown_id=UNKNOWN_FUTURE_TECHNOLOGY_ID,
        unknown_id_classification=unknown_classification,
        unknown_id_still_unknown=still_unknown,
        core_equivalence=equivalence,
        events=journal.events(),
    )


def _unknown_profile() -> FutureProfileDeclaration:
    """The demonstration profile over an arbitrary unknown future id.

    Same shape as the canonical declaration, different identifier and
    resource name: an OPEN-WORLD registration (the architecture
    section 8 ``access.3gpp.future.unknown`` example).  Capability
    references stay profile-scoped and unknown-but-well-formed.
    """
    return FutureProfileDeclaration(
        technology_id=UNKNOWN_FUTURE_TECHNOLOGY_ID,
        profile_versions=("future-study-1",),
        capability_references=(
            "capability.profile.imt2030.data-transfer",
        ),
        technology_resource="future-unknown:bandwidth",
        resource_kind="bandwidth",
        resource_unit="mbps",
        resource_quantity=50,
        security_profile="baseline",
        credential_slots=("technology-credential",),
        extensions={},
    )


def verify_future_replay(
    result: FutureRunResult,
    *,
    start_instant: str = SCENARIO_START_INSTANT,
) -> bool:
    """Replay verification: re-run the canonical scenario and compare
    digests (a TRUE replay, not a self-comparison)."""
    if not isinstance(result, FutureRunResult):
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "replay verification needs a FutureRunResult",
        )
    replay = run_future_profile_conformance(start_instant=start_instant)
    if replay.future_digest() != result.future_digest():
        raise FutureError(
            FutureReasonCode.REPLAY_DIVERGENCE,
            "replayed run digest %s != recorded %s"
            % (replay.future_digest(), result.future_digest()),
        )
    return True


def scenario_summary(result: FutureRunResult) -> Dict[str, Any]:
    """A compact human summary of a run (pure projection)."""
    return {
        "technology_classification": result.technology_classification,
        "registry_unchanged": (
            result.registry_digest_before == result.registry_digest_after
        ),
        "adapters": list(result.adapter_ids),
        "unknown_id": result.unknown_id,
        "unknown_id_still_unknown": result.unknown_id_still_unknown,
        "core_equivalence_all_equal": result.core_equivalence.all_equal(),
        "events": len(result.events),
        "future_digest": result.future_digest(),
    }
