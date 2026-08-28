#!/usr/bin/env python3
"""ADCOS upgrade / rollback / compatibility self-test (WORK-029).

The focused mixed-version integration battery for the ``upgrade``
family, mapping the WORK-029 work-item contract to discriminating
cases:

- the four governance version kinds never conflated;
  SoftwareVersion/ProtocolProfile grammars structurally
  disjoint; Architecture Version not a model dimension
                                                      -> case_01
- canonical MAJOR.MINOR.PATCH grammar (leading zeros,
  wrong arity, signs, "0.0.0" all rejected)          -> case_02
- ProtocolProfile consumes the REAL WORK-003 artifact
  read-only (known majors, file bytes unchanged)     -> case_03
- common profile = shared known major at the
  additive-evolution floor min(minor heads)          -> case_04
- incompatible versions fail closed (major mismatch:
  NO fallback; unknown major: WORK-003 verdict)      -> case_05
- STRUCTURAL red proof: a forged "selected" profile
  across mismatched majors is not a constructible
  value (the model itself rejects it)                -> case_06
- mixed-version capability interop through the REAL
  WORK-005 machinery (delegated coexistence report)  -> case_07
- the capability dimension is DELEGATION, not
  re-implementation: same inputs -> byte-identical
  outcomes as calling WORK-005 directly; unknown
  required capability fails closed through the
  composed surface                                   -> case_08
- VersionInventory COMPLETE-CONTENT tamper matrix    -> case_09
- migration step discipline (additive = exactly +1
  minor; breaking = exactly +1 major, minor 0;
  no-ops and duplicate edges rejected)               -> case_10
- reversible migration round-trip is byte-identical;
  input state untouched (purity)                     -> case_11
- multi-step chains forward/backward                 -> case_12
- unknown migration paths fail closed                -> case_13
- declared non-reversible steps are never reversed
  (fail closed, not best-effort undo)                -> case_14
- migration determinism (input key order cannot
  change canonical outcomes)                         -> case_15
- UpgradePlan invariants (upgrades only; floor in
  range; gates required, labels distinct; complete-
  content tamper matrix)                             -> case_16
- submit_plan validation matrix (wrong node/version;
  below-floor start; unknown protocol major; schema
  mismatch; one active plan) -- every rejection
  audited                                            -> case_17
- the staged ladder happy path with exact event
  order and floor ratchet                            -> case_18
- gates require REAL SELF-SOURCED RECORDED telemetry
  evidence (duck-typed fakes rejected however
  complete; unrecorded/cross-store/tampered
  injections rejected -- provenance is the
  WORK-026 store's verdict; absent -> fail
  closed; foreign-sourced claims never count --
  LOCK-008)                                          -> case_19
- stale evidence fails closed (stage unchanged)      -> case_20
- gate thresholds enforced; the deterministic LATEST
  observation decides                                -> case_21
- commit requires ROLLING + final gate PASS          -> case_22
- rollback restores the pre-plan truth byte-identical
  (schema state reverse-migrated)                    -> case_23
- post-commit rollback window closed (a new plan,
  never a silent re-open)                            -> case_24
- the floor ratchet blocks plans from below the
  floor                                              -> case_25
- THE mixed-version integration scenario: a four-node
  rolling upgrade 2.0.0 -> 2.1.0 with canary
  discipline, all committed                          -> case_26
- mid-rollout mixed-version coexistence reports for
  EVERY pair (canary 2.1.0/profile 1.1 vs the
  2.0.0/profile 1.0 population)                      -> case_27
- wire-level interop through the REAL WORK-003
  validation pipeline: v1 accepted; additive optional
  content from a 1.1 speaker preserved (KNOWN_ADDITIVE);
  v2 envelope REJECTED_INCOMPATIBLE_MAJOR            -> case_28
- canary rollout-gate failure halts the rollout;
  later batches never advance; canary rolled back    -> case_29
- a per-node staging failure rolls back EVERY begun
  node                                               -> case_30
- a commit-time failure rolls back only the
  un-committed nodes (committed windows stay closed);
  the resulting mixed population still coexists      -> case_31
- population downgrade protection: rollback below
  the floor DOWNGRADE_BLOCKED (audited); the staged
  origin target succeeds                             -> case_32
- import discipline: the family consumes only the
  composed authorities as DATA; nothing else imports
  it; no file writes anywhere in the family          -> case_33
- no vendor/access symbols (LOCK-001/002/003)        -> case_34
- DETERMINISM: composed scenario identical across
  hash seeds (0/1/7919)                              -> case_35
- frozen spec/ byte-identical to origin/main; docs/
  additions limited to the WORK-029 handoff          -> case_36
- py_compile clean                                   -> case_37
- CI wiring (this battery + every prior battery)     -> case_38
- canonical serialization round-trips; truncated
  DATA fails closed                                  -> case_39
- schema-state isolation: state handed out is a copy;
  internal state byte-identical after a full staged
  cycle                                              -> case_40
- live migration application is TRANSACTIONALLY
  isolated: raising / invalid-returning / partially-
  applying migration chains (arbitrary callables,
  honest in rehearsal, hostile live) leave live
  state byte-identical; the rollback proof-walk is
  isolated too (PR #31 review blocker 2)            -> case_41

Run: python3 tools/upgrade_selftest.py   (exit 0 = PASS)
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from upgrade import (  # noqa: E402
    EventKind,
    GateVerdict,
    HealthGateResult,
    HealthGateSpec,
    MigrationDescriptor,
    ProtocolProfile,
    SoftwareVersion,
    UpgradeError,
    UpgradeEvent,
    UpgradePlan,
    UpgradeReasonCode,
    UpgradeStage,
    VersionInventory,
    VersionKind,
    derive_event_id,
    derive_inventory_id,
    derive_migration_id,
    derive_plan_id,
)
from upgrade.compatibility import (  # noqa: E402
    CoexistenceReport,
    ProfileNegotiation,
    coexistence_report,
    envelope_version_disposition,
    negotiate_protocol_profile,
)
from upgrade.manager import UpgradeManager  # noqa: E402
from upgrade.migrations import Migration, MigrationRegistry  # noqa: E402
from upgrade.population import RolloutCoordinator, RolloutTemplate  # noqa: E402
from upgrade.serialization import (  # noqa: E402
    health_gate_result_from_dict,
    health_gate_spec_from_dict,
    migration_descriptor_from_dict,
    upgrade_event_from_dict,
    upgrade_plan_from_dict,
    version_inventory_from_dict,
)
from capabilities.model import CapabilityStatement  # noqa: E402
from capabilities.negotiation import (  # noqa: E402
    NegotiationSpec,
    RejectionReason,
    Requirement,
    negotiate as work005_negotiate,
)
from protocol.envelope import Envelope, envelope_from_mapping  # noqa: E402
from protocol.validation import (  # noqa: E402
    AcceptOutcome,
    ParsePolicy,
    UnknownTypePolicy,
    validate as work003_validate,
)
from protocol.versioning import Classification, protocol_metadata  # noqa: E402
from telemetry.model import (  # noqa: E402
    TelemetryObservation,
    TelemetrySourceClass,
    derive_observation_id,
)
from telemetry.store import TelemetryStore  # noqa: E402

Result = Tuple[str, bool, str]

_NOW = "2026-09-01T12:00:00Z"
_LATER = "2026-09-01T13:00:00Z"
_EARLIER = "2026-09-01T11:00:00Z"
_NEGOTIATION_NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)

# Nodes: A = the deterministic canary; B/C/D = the rollout population.
NODE_A = "adcos:node:test.profile.v1:" + "a" * 64
NODE_B = "adcos:node:test.profile.v1:" + "b" * 64
NODE_C = "adcos:node:test.profile.v1:" + "c" * 64
NODE_D = "adcos:node:test.profile.v1:" + "d" * 64

# Opaque per-node subjects (local names on every node; observations
# are distinguished by their SELF-advertised source, LOCK-008).
ADAPTER_REF = "adapter:primary"
UPLINK_REF = "path:uplink"


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def _never_reverse(state: Any) -> Any:
    """The honest guard on a declared non-reversible step: it is
    never invoked (the registry refuses the reversal first)."""
    raise AssertionError("declared non-reversible steps are never reversed")


def _registry() -> MigrationRegistry:
    """The node.config schema-version line:

    1.0 -> 1.1 (additive, reversible): add heartbeat_seconds
    1.1 -> 1.2 (additive, reversible): add label
    1.2 -> 2.0 (breaking, NOT reversible): drop legacy_mode
    """
    registry = MigrationRegistry()
    registry.register_step(
        "node.config", "1.0", "1.1", reversible=True, breaking=False,
        forward=lambda s: dict(s, heartbeat_seconds=30),
        backward=lambda s: {k: v for k, v in s.items() if k != "heartbeat_seconds"},
    )
    registry.register_step(
        "node.config", "1.1", "1.2", reversible=True, breaking=False,
        forward=lambda s: dict(s, label="node"),
        backward=lambda s: {k: v for k, v in s.items() if k != "label"},
    )
    registry.register_step(
        "node.config", "1.2", "2.0", reversible=False, breaking=True,
        forward=lambda s: {k: v for k, v in s.items() if k != "legacy_mode"},
        backward=_never_reverse,
    )
    return registry


_STATE_1_1 = {"legacy_mode": True, "heartbeat_seconds": 30}


def _manager(
    node_id: str,
    *,
    software: str = "2.0.0",
    profile: Tuple[int, int] = (1, 0),
    schema: str = "1.1",
    floor: Optional[str] = None,
    registry: Optional[MigrationRegistry] = None,
    schemas: Optional[Dict[str, str]] = None,
    state: Optional[Dict[str, Dict[str, Any]]] = None,
    store: Optional[TelemetryStore] = None,
) -> UpgradeManager:
    # Every manager owns its node's genuine WORK-026 telemetry store:
    # gate-evidence provenance is resolved against the recorded set
    # (PR #31 Architect review blocker 1).  The fixture registers the
    # store per node so observation builders record evidence into the
    # store of the manager under test.
    telemetry_store = store if store is not None else TelemetryStore()
    _STORES[node_id] = telemetry_store
    return UpgradeManager(
        node_id=node_id,
        software_version=SoftwareVersion.parse(software),
        protocol_profile=ProtocolProfile(major=profile[0], max_minor=profile[1]),
        schema_versions=schemas if schemas is not None else {"node.config": schema},
        schema_state=state if state is not None else {"node.config": dict(_STATE_1_1)},
        migration_registry=registry if registry is not None else _registry(),
        telemetry_store=telemetry_store,
        minimum_version_floor=SoftwareVersion.parse(floor) if floor else None,
    )


def _template(
    *,
    to_software: str = "2.1.0",
    to_profile: Tuple[int, int] = (1, 1),
    to_schema: str = "1.2",
    floor: str = "2.0.0",
) -> RolloutTemplate:
    return RolloutTemplate(
        to_version=SoftwareVersion.parse(to_software),
        target_protocol_profile=ProtocolProfile(major=to_profile[0], max_minor=to_profile[1]),
        target_schema_versions=(("node.config", to_schema),),
        minimum_version_floor=SoftwareVersion.parse(floor),
        canary_gate=HealthGateSpec(
            "canary-adapter-health", "adapter-health", ADAPTER_REF, "health-state", 1,
        ),
        rollout_gate=HealthGateSpec(
            "rollout-path-loss", "path", UPLINK_REF, "loss-bp", 500,
        ),
        final_gate=HealthGateSpec(
            "final-adapter-failures", "adapter-health", ADAPTER_REF,
            "consecutive-failures", 0,
        ),
    )


# The per-node telemetry stores of the managers under test (the
# provenance oracle every gate now verifies against; PR #31
# Architect review blocker 1), and the per-(store, stream) monotone
# sequence allocator mirroring the store's ingest ledger discipline.
_STORES: Dict[str, TelemetryStore] = {}
_SEQ: Dict[Tuple[int, str, str, str, str], int] = {}


def _observation(
    node: str,
    subject_kind: str,
    subject_ref: str,
    metric: str,
    value: int,
    *,
    at: str = _NOW,
    seq: Optional[int] = None,
    fresh_for_seconds: int = 3600,
    source: Optional[str] = None,
    record: bool = True,
) -> TelemetryObservation:
    """A REAL WORK-026 telemetry observation (self-advertised by
    default; ``source`` lets the battery build foreign-sourced
    claims for the LOCK-008 regression).

    The fixture RECORDS the observation into the consuming node's
    telemetry store (``node`` is the manager under test; a foreign
    source is a claim ABOUT that node's subject, recorded in its
    store and still excluded as foreign evidence): gates now verify
    provenance against the recorded set, so unrecorded evidence is
    only ever built deliberately (``record=False``) for the
    provenance-boundary red tests.  Sequences auto-advance per
    (store, subject, source, metric) stream, mirroring the store's
    ingest ledger."""
    observed = datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    fresh = (
        observed + timedelta(seconds=fresh_for_seconds)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    source_node = source if source is not None else node
    store = _STORES.get(node)
    if seq is None:
        if store is None:
            raise AssertionError(
                "fixture discipline: build the manager for %r before its "
                "observations (the store is the provenance oracle)" % (node,)
            )
        key = (id(store), subject_kind, subject_ref, source_node, metric)
        seq = _SEQ.get(key, 0) + 1
        _SEQ[key] = seq
    observation = TelemetryObservation(
        observation_id=derive_observation_id(
            subject_kind, subject_ref, source_node,
            TelemetrySourceClass.SELF_ADVERTISED, metric, value, 9_000,
            at, fresh, seq,
        ),
        subject_kind=subject_kind,
        subject_ref=subject_ref,
        source_node_id=source_node,
        source_class=TelemetrySourceClass.SELF_ADVERTISED,
        metric=metric,
        value=value,
        confidence_basis_points=9_000,
        observed_at=at,
        freshness_until=fresh,
        sequence=seq,
    )
    if record:
        if store is None:
            raise AssertionError(
                "fixture discipline: no telemetry store registered for %r" % (node,)
            )
        store.record_observation(observation, now=at)
    return observation


def _healthy_observations(node: str, *, at: str = _NOW) -> Tuple[Any, ...]:
    """Self-sourced evidence that passes every template gate (recorded
    in the consuming node's store: recorded evidence only)."""
    return (
        _observation(node, "adapter-health", ADAPTER_REF, "health-state", 0, at=at),
        _observation(node, "path", UPLINK_REF, "loss-bp", 120, at=at),
        _observation(node, "adapter-health", ADAPTER_REF, "consecutive-failures", 0, at=at),
    )


def _statement(provider: str, *, schema_version: str = "1.1") -> CapabilityStatement:
    return CapabilityStatement(
        capability_id="capability.core.multipath",
        schema_version=schema_version,
        provider_identity=provider,
        valid_from="2026-01-01T00:00:00Z",
        expires_at="2027-01-01T00:00:00Z",
        parameters={"max_paths": 4},
    )


def _requirement(min_schema_version: str = "1.0") -> Requirement:
    return Requirement(
        capability_id="capability.core.multipath",
        min_schema_version=min_schema_version,
    )


def _population(
    registry: Optional[MigrationRegistry] = None,
) -> Dict[str, UpgradeManager]:
    reg = registry if registry is not None else _registry()
    return {
        NODE_A: _manager(NODE_A, registry=reg),
        NODE_B: _manager(NODE_B, registry=reg),
        NODE_C: _manager(NODE_C, registry=reg),
        NODE_D: _manager(NODE_D, registry=reg),
    }


def _expect_reject(name: str, problems: List[str], call, reason: str, label: str) -> None:
    try:
        call()
    except UpgradeError as error:
        if error.reason != reason:
            problems.append(
                "%s: expected reason %r, got %r (%s)" % (label, reason, error.reason, error)
            )
    else:
        problems.append("%s: expected UpgradeError(%s) was not raised" % (label, reason))


# --------------------------------------------------------------------------
# 1-3: version kinds, grammars, the real WORK-003 artifact
# --------------------------------------------------------------------------

def case_01_version_kinds_structurally_separated() -> Result:
    name = "case_01_version_kinds_structurally_separated"
    problems: List[str] = []
    # The frozen four-kind taxonomy (governance section 3).
    if VersionKind.ALL_VALUES != frozenset(
        {"architecture", "protocol", "schema", "implementation"}
    ):
        problems.append("version-kind taxonomy is not the frozen four")
    # SoftwareVersion (Implementation Version line) parses ONLY
    # MAJOR.MINOR.PATCH; a protocol-style "1.1" is rejected.
    for bad in ("1.1", "1", "1.1.1.1"):
        try:
            SoftwareVersion.parse(bad)
            problems.append("SoftwareVersion accepted protocol-style %r" % bad)
        except UpgradeError:
            pass
    # A MAJOR.MINOR dotted pair rejects an implementation version.
    from upgrade.validation import parse_dotted_pair

    try:
        parse_dotted_pair("1.1.1", "probe")
        problems.append("dotted pair accepted implementation-style '1.1.1'")
    except UpgradeError:
        pass
    # A SoftwareVersion is never accepted as a ProtocolProfile and
    # vice versa (structural kind separation at the record level).
    _expect_reject(
        name, problems,
        lambda: VersionInventory(
            node_id=NODE_A,
            software_version=ProtocolProfile(major=1, max_minor=0),
            protocol_profile=ProtocolProfile(major=1, max_minor=0),
        ),
        UpgradeReasonCode.VERSION_KIND_CONFLATED,
        "software_version as ProtocolProfile",
    )
    _expect_reject(
        name, problems,
        lambda: VersionInventory(
            node_id=NODE_A,
            software_version=SoftwareVersion.parse("2.0.0"),
            protocol_profile=SoftwareVersion.parse("2.0.0"),  # type: ignore[arg-type]
        ),
        UpgradeReasonCode.VERSION_KIND_CONFLATED,
        "protocol_profile as SoftwareVersion",
    )
    # The Architecture Version is NOT a dimension of this model: no
    # canonical record carries it (it is declared only in
    # spec/architecture.md and changes only through an ACR).
    inventory = _manager(NODE_A).inventory()
    plan_dict = _template().plan_for(NODE_A, SoftwareVersion.parse("2.0.0")).to_dict()
    for record in (inventory.to_dict(), plan_dict):
        leaked = [key for key in record if "architecture" in key.lower()]
        if leaked:
            problems.append("architecture-version leakage in record: %r" % leaked)
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "four version kinds structurally disjoint; architecture kind not a model dimension")


def case_02_software_version_canonical_grammar() -> Result:
    name = "case_02_software_version_canonical_grammar"
    problems: List[str] = []
    for bad in ("01.2.3", "1.02.3", "1.2.03", "-1.0.0", "1.-2.0", " 1.2.3", "1.2.3 ",
                "v1.2.3", "1.2.x", "", "1.2.3.4", "0.0.0", 1.5, None, b"1.2.3"):
        try:
            SoftwareVersion.parse(bad)  # type: ignore[arg-type]
            problems.append("accepted malformed version %r" % (bad,))
        except UpgradeError:
            pass
    # Ordering is the integer triple order.
    if not (
        SoftwareVersion.parse("2.0.0") < SoftwareVersion.parse("2.0.1")
        < SoftwareVersion.parse("2.1.0") < SoftwareVersion.parse("3.0.0")
    ):
        problems.append("version ordering broken")
    # One canonical spelling: round-trip through str is exact.
    for text in ("0.1.0", "2.0.0", "10.20.30"):
        if str(SoftwareVersion.parse(text)) != text:
            problems.append("non-canonical spelling for %r" % text)
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "canonical MAJOR.MINOR.PATCH grammar; malformed versions fail closed")


def case_03_protocol_profile_real_work003_artifact() -> Result:
    name = "case_03_protocol_profile_real_work003_artifact"
    problems: List[str] = []
    artifact = os.path.join(_ROOT, "spec", "schemas", "protocol.json")
    before = hashlib.sha256(open(artifact, "rb").read()).hexdigest()
    metadata = protocol_metadata()
    # The REAL artifact's truth (known majors) drives the family.
    if metadata.known_major_versions != frozenset({1}):
        problems.append(
            "unexpected known majors %r (artifact changed?)" % (sorted(metadata.known_major_versions),)
        )
    if envelope_version_disposition(1) != Classification.KNOWN_COMPATIBLE:
        problems.append("major 1 must be known-compatible")
    for unknown in (2, 3, 9, 99):
        if envelope_version_disposition(unknown) != Classification.REJECTED_INCOMPATIBLE_MAJOR:
            problems.append("major %d must be rejected-incompatible" % unknown)
    # Profile negotiation consults the artifact, read-only.
    verdict = negotiate_protocol_profile(ProtocolProfile(1, 2), ProtocolProfile(1, 0))
    if not verdict.succeeded or str(verdict.selected) != "1.0":
        problems.append("known-major negotiation failed: %r" % (verdict,))
    unknown_major = negotiate_protocol_profile(ProtocolProfile(9, 1), ProtocolProfile(9, 4))
    if unknown_major.succeeded or unknown_major.reason != UpgradeReasonCode.MAJOR_UNKNOWN:
        problems.append("unknown major 9 must fail closed with MAJOR_UNKNOWN")
    after = hashlib.sha256(open(artifact, "rb").read()).hexdigest()
    if before != after:
        problems.append("the protocol artifact was modified (read-only violated)")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "profile truth from the REAL artifact, consumed read-only (bytes unchanged)")


# --------------------------------------------------------------------------
# 4-8: mixed-version coexistence and negotiation delegation
# --------------------------------------------------------------------------

def case_04_common_profile_additive_floor() -> Result:
    name = "case_04_common_profile_additive_floor"
    problems: List[str] = []
    cases = [
        ((1, 3), (1, 1), "1.1"),
        ((1, 1), (1, 3), "1.1"),
        ((1, 0), (1, 2), "1.0"),
        ((1, 2), (1, 2), "1.2"),
        ((1, 0), (1, 0), "1.0"),
    ]
    for local, peer, expected in cases:
        verdict = negotiate_protocol_profile(
            ProtocolProfile(major=local[0], max_minor=local[1]),
            ProtocolProfile(major=peer[0], max_minor=peer[1]),
        )
        if not verdict.succeeded or str(verdict.selected) != expected:
            problems.append(
                "negotiate %s/%s -> %r (expected %s)"
                % (local, peer, verdict.selected, expected)
            )
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "common profile = shared known major at min(minor heads), both directions")


def case_05_incompatible_majors_fail_closed() -> Result:
    name = "case_05_incompatible_majors_fail_closed"
    problems: List[str] = []
    for local, peer in (((1, 4), (2, 0)), ((2, 0), (1, 4)), ((1, 0), (9, 1))):
        verdict = negotiate_protocol_profile(
            ProtocolProfile(major=local[0], max_minor=local[1]),
            ProtocolProfile(major=peer[0], max_minor=peer[1]),
        )
        if verdict.succeeded or verdict.selected is not None:
            problems.append("majors %d/%d produced a selection (no fallback!)" % (local[0], peer[0]))
        if verdict.reason not in (UpgradeReasonCode.MAJOR_MISMATCH, UpgradeReasonCode.MAJOR_UNKNOWN):
            problems.append("majors %d/%d: unexpected reason %r" % (local[0], peer[0], verdict.reason))
    # The mismatch reason is exact for known-but-different majors.
    mismatch = negotiate_protocol_profile(ProtocolProfile(1, 0), ProtocolProfile(2, 0))
    if mismatch.reason != UpgradeReasonCode.MAJOR_MISMATCH:
        problems.append("1.x vs 2.x must be MAJOR_MISMATCH")
    # Same unknown major on both sides still fails closed.
    unknown = negotiate_protocol_profile(ProtocolProfile(9, 1), ProtocolProfile(9, 3))
    if unknown.succeeded or unknown.reason != UpgradeReasonCode.MAJOR_UNKNOWN:
        problems.append("unknown major 9 must fail closed")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "mismatched and unknown majors fail closed with explicit reasons (no fallback)")


def case_06_forged_selection_not_constructible() -> Result:
    name = "case_06_forged_selection_not_constructible"
    problems: List[str] = []
    local = ProtocolProfile(major=1, max_minor=3)
    peer = ProtocolProfile(major=2, max_minor=0)
    # A rogue negotiator that "finds" a common profile across
    # mismatched majors cannot express its result: the record itself
    # rejects the forged selection (structural fail-closed).
    _expect_reject(
        name, problems,
        lambda: ProfileNegotiation(
            local=local, peer=peer,
            selected=ProtocolProfile(major=1, max_minor=0), reason=None, detail="forged",
        ),
        UpgradeReasonCode.MAJOR_MISMATCH,
        "forged cross-major selection",
    )
    # A selection that is not the additive floor is rejected too.
    _expect_reject(
        name, problems,
        lambda: ProfileNegotiation(
            local=ProtocolProfile(major=1, max_minor=3),
            peer=ProtocolProfile(major=1, max_minor=1),
            selected=ProtocolProfile(major=1, max_minor=2),  # NOT min(3, 1)
            reason=None, detail="wrong floor",
        ),
        UpgradeReasonCode.INVALID_INPUT,
        "selection off the additive floor",
    )
    # A rejection without a reason is not constructible.
    _expect_reject(
        name, problems,
        lambda: ProfileNegotiation(
            local=local, peer=peer, selected=None, reason=None, detail="?",
        ),
        UpgradeReasonCode.INVALID_INPUT,
        "rejection without reason",
    )
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "forged cross-major/floor-off selections are not constructible values")


def case_07_mixed_version_capability_interop_delegated() -> Result:
    name = "case_07_mixed_version_capability_interop_delegated"
    problems: List[str] = []
    # A 2.1.0 canary (profile 1.1) coexisting with a 2.0.0 node
    # (profile 1.0): common profile 1.0, real WORK-005 capability
    # interop over a registered capability.
    canary = _manager(NODE_A, software="2.1.0", profile=(1, 1)).inventory()
    stable = _manager(NODE_B, software="2.0.0", profile=(1, 0)).inventory()
    report = coexistence_report(
        canary, stable,
        peer_statements=(_statement(NODE_B, schema_version="1.1"),),
        requirements=(_requirement("1.0"),),
        now=_NEGOTIATION_NOW,
    )
    if not report.coexist:
        problems.append("mixed-version coexistence failed: %r" % (report.to_dict(),))
    if str(report.profile.selected) != "1.0":
        problems.append("common profile expected 1.0, got %r" % (report.profile.selected,))
    if not report.capability_succeeded:
        problems.append("capability interop failed: %r" % (report.capability_failure_reasons,))
    # The same-major version-incompatible statement fails the
    # capability dimension -> coexistence is False (fail closed
    # through the composed surface, never best-effort).
    incompatible = coexistence_report(
        canary, stable,
        peer_statements=(_statement(NODE_B, schema_version="1.0"),),
        requirements=(_requirement("1.1"),),
        now=_NEGOTIATION_NOW,
    )
    if incompatible.coexist or incompatible.capability_succeeded:
        problems.append("version-incompatible capability must fail closed")
    if not any(
        RejectionReason.VERSION_INCOMPATIBLE in reason
        for reason in incompatible.capability_failure_reasons
    ):
        problems.append(
            "expected WORK-005 VERSION_INCOMPATIBLE reason, got %r"
            % (incompatible.capability_failure_reasons,)
        )
    # Mismatched protocol majors fail coexistence even with perfect
    # capability statements.
    future = _manager(NODE_B, software="3.0.0", profile=(2, 0)).inventory()
    cross_major = coexistence_report(
        canary, future,
        peer_statements=(_statement(NODE_B),),
        requirements=(_requirement(),),
        now=_NEGOTIATION_NOW,
    )
    if cross_major.coexist:
        problems.append("cross-major peers must not coexist")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "2.1.0/profile-1.1 + 2.0.0/profile-1.0 coexist at 1.0 with real WORK-005 "
        "interoperation; incompatible capability/major fail closed",
    )


def case_08_negotiation_is_delegation_not_reimplementation() -> Result:
    name = "case_08_negotiation_is_delegation_not_reimplementation"
    problems: List[str] = []
    local = _manager(NODE_A, software="2.1.0", profile=(1, 1)).inventory()
    peer = _manager(NODE_B, software="2.0.0", profile=(1, 0)).inventory()
    scenarios = [
        # (statements, requirements)
        ((_statement(NODE_B, schema_version="1.1"),), (_requirement("1.0"),)),
        ((), (_requirement("1.0"),)),  # absent capability: fails
        ((_statement(NODE_B, schema_version="1.0"),), (_requirement("1.1"),)),
        ((_statement(NODE_B),), (Requirement("capability.core.local-breakout"),)),
    ]
    for statements, requirements in scenarios:
        report = coexistence_report(
            local, peer, peer_statements=statements, requirements=requirements,
            now=_NEGOTIATION_NOW,
        )
        direct = work005_negotiate(
            NegotiationSpec(
                requirements=tuple(requirements),
                peer_statements=tuple(statements),
                now=_NEGOTIATION_NOW,
            )
        )
        if report.capability_succeeded != direct.succeeded:
            problems.append("delegated verdict diverges from WORK-005 (succeeded)")
        if report.capability_failure_reasons != tuple(direct.failure_reasons):
            problems.append(
                "delegated failure reasons diverge: %r vs %r"
                % (report.capability_failure_reasons, direct.failure_reasons)
            )
    # The unknown REQUIRED capability fails closed through the
    # composed surface with WORK-005's frozen reason.
    unknown_required = coexistence_report(
        local, peer,
        peer_statements=(),
        requirements=(Requirement("capability.profile.future-unknown"),),
        now=_NEGOTIATION_NOW,
    )
    if unknown_required.coexist:
        problems.append("unknown required capability must fail closed")
    if not any(
        RejectionReason.UNKNOWN_REQUIRED_CAPABILITY in reason
        for reason in unknown_required.capability_failure_reasons
    ):
        problems.append("expected WORK-005 UNKNOWN_REQUIRED_CAPABILITY reason")
    # Static proof of delegation: the compatibility module imports
    # the real WORK-005 machinery (and the family never re-implements
    # the version-compatibility predicate under a private name).
    source = open(
        os.path.join(_ROOT, "upgrade", "compatibility.py"), encoding="utf-8"
    ).read()
    if "from capabilities.negotiation import" not in source:
        problems.append("compatibility.py does not import capabilities.negotiation")
    if "_version_compatible" in source:
        problems.append("compatibility.py re-implements WORK-005 version compatibility")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "capability dimension is byte-identical WORK-005 delegation; no re-implementation")


# --------------------------------------------------------------------------
# 9: complete-content identity
# --------------------------------------------------------------------------

def case_09_inventory_complete_content_tamper_matrix() -> Result:
    name = "case_09_inventory_complete_content_tamper_matrix"
    problems: List[str] = []
    base = _manager(NODE_A).inventory()
    # Distinct content -> distinct ids.
    other = _manager(NODE_A, software="2.0.1").inventory()
    if base.inventory_id == other.inventory_id:
        problems.append("distinct software versions share an inventory id")
    # The complete-content tamper matrix: mutate ANY field while
    # retaining the id -> rejected at construction.
    mutations = {
        "node_id": base.to_dict() | {"node_id": NODE_B},
        "software_version": base.to_dict() | {"software_version": "9.9.9"},
        "protocol_profile": base.to_dict() | {"protocol_profile": [1, 9]},
        "schema_versions": base.to_dict() | {"schema_versions": [["node.config", "1.2"]]},
    }
    for field, data in mutations.items():
        _expect_reject(
            name, problems,
            lambda data=data: version_inventory_from_dict(data),
            UpgradeReasonCode.INVALID_INPUT,
            "tampered %s retains the id" % field,
        )
    # Round-trip is byte-identical.
    rebuilt = version_inventory_from_dict(base.to_dict())
    if rebuilt.to_dict() != base.to_dict():
        problems.append("inventory round-trip not byte-identical")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "per-field tamper matrix rejected; round-trip byte-identical")


# --------------------------------------------------------------------------
# 10-15: migrations
# --------------------------------------------------------------------------

def case_10_migration_step_discipline() -> Result:
    name = "case_10_migration_step_discipline"
    problems: List[str] = []
    good_additive = ("node.config", "1.0", "1.1", True, False)
    good_breaking = ("node.config", "1.2", "2.0", False, True)
    for bad in (
        ("node.config", "1.0", "1.2", True, False),   # additive must be +1 minor
        ("node.config", "1.0", "2.0", True, False),   # major bump declared additive
        ("node.config", "1.2", "2.1", False, True),   # breaking must reset minor
        ("node.config", "1.2", "3.0", False, True),   # breaking must be +1 major
        ("node.config", "1.1", "1.1", True, False),   # no-op
        ("node.config", "1.2", "1.1", True, False),   # downgrade edge
    ):
        _expect_reject(
            name, problems,
            lambda bad=bad: MigrationDescriptor(*bad),
            UpgradeReasonCode.MIGRATION_INVALID_STEP,
            "step shape %r" % (bad,),
        )
    # Good descriptors construct and carry complete-content ids.
    for good in (good_additive, good_breaking):
        descriptor = MigrationDescriptor(*good)
        if not descriptor.migration_id.startswith("upgrade:migration:"):
            problems.append("migration id prefix wrong: %r" % descriptor.migration_id[:32])
    # Duplicate edges fail closed.
    registry = MigrationRegistry()
    registry.register_step(*good_additive,
                           forward=lambda s: s, backward=lambda s: s)
    _expect_reject(
        name, problems,
        lambda: registry.register_step(*good_additive,
                                       forward=lambda s: s, backward=lambda s: s),
        UpgradeReasonCode.MIGRATION_DUPLICATE_EDGE,
        "duplicate edge",
    )
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "additive/breaking step shapes enforced; no-ops and duplicates rejected")


def case_11_migration_reversible_round_trip() -> Result:
    name = "case_11_migration_reversible_round_trip"
    registry = _registry()
    state = {"legacy_mode": True, "heartbeat_seconds": 30}
    forward = registry.migrate_forward(state, "node.config", "1.1", "1.2")
    if forward != {"legacy_mode": True, "heartbeat_seconds": 30, "label": "node"}:
        return fail(name, "forward migration produced %r" % (forward,))
    if state != {"legacy_mode": True, "heartbeat_seconds": 30}:
        return fail(name, "migration MUTATED its input (purity violated)")
    backward = registry.migrate_backward(forward, "node.config", "1.2", "1.1")
    if backward != state:
        return fail(name, "round-trip not byte-identical: %r vs %r" % (backward, state))
    # The generic migrate() picks the direction from the versions.
    if registry.migrate(state, "node.config", "1.1", "1.2") != forward:
        return fail(name, "generic migrate() forward diverges")
    if registry.migrate(forward, "node.config", "1.2", "1.1") != state:
        return fail(name, "generic migrate() backward diverges")
    return ok(name, "forward+backward round-trip byte-identical; input purity holds")


def case_12_migration_chain_multi_step() -> Result:
    name = "case_12_migration_chain_multi_step"
    registry = _registry()
    state_v10 = {"legacy_mode": True}
    # 1.0 -> 1.2 is a two-step chain (fewest edges).
    path = registry.path("node.config", "1.0", "1.2")
    if [d.to_version for d in path] != ["1.1", "1.2"]:
        return fail(name, "unexpected chain %r" % ([d.to_version for d in path],))
    forward = registry.migrate_forward(state_v10, "node.config", "1.0", "1.2")
    if forward != {"legacy_mode": True, "heartbeat_seconds": 30, "label": "node"}:
        return fail(name, "chained forward produced %r" % (forward,))
    backward = registry.migrate_backward(forward, "node.config", "1.2", "1.0")
    if backward != state_v10:
        return fail(name, "chained round-trip not byte-identical")
    # The chain through the declared non-reversible step works
    # forward but is honestly irreversible backward.
    forward_all = registry.migrate_forward(state_v10, "node.config", "1.0", "2.0")
    if forward_all != {"heartbeat_seconds": 30, "label": "node"}:
        return fail(name, "1.0 -> 2.0 forward produced %r" % (forward_all,))
    if registry.path_is_reversible("node.config", "1.0", "2.0"):
        return fail(name, "1.0 -> 2.0 must not be reversible")
    if not registry.path_is_reversible("node.config", "1.0", "1.2"):
        return fail(name, "1.0 -> 1.2 must be reversible")
    return ok(name, "two-step chain forward/backward; mixed chains honestly classified")


def case_13_unknown_path_fails_closed() -> Result:
    name = "case_13_unknown_path_fails_closed"
    registry = _registry()
    problems: List[str] = []
    _expect_reject(
        name, problems,
        lambda: registry.path("node.config", "1.0", "9.9"),
        UpgradeReasonCode.MIGRATION_PATH_UNKNOWN,
        "unknown target",
    )
    _expect_reject(
        name, problems,
        lambda: registry.path("other.artifact", "1.0", "1.1"),
        UpgradeReasonCode.MIGRATION_PATH_UNKNOWN,
        "unknown schema",
    )
    _expect_reject(
        name, problems,
        lambda: registry.path("node.config", "1.1", "1.1"),
        UpgradeReasonCode.MIGRATION_INVALID_STEP,
        "no-op path",
    )
    _expect_reject(
        name, problems,
        lambda: registry.migrate_forward({"a": 1}, "node.config", "1.0", "9.9"),
        UpgradeReasonCode.MIGRATION_PATH_UNKNOWN,
        "unknown migrate target",
    )
    # A migration function returning a non-Mapping fails closed.
    bad = MigrationRegistry()
    bad.register_step(
        "x.artifact", "1.0", "1.1", reversible=True, breaking=False,
        forward=lambda s: 42, backward=lambda s: s,
    )
    _expect_reject(
        name, problems,
        lambda: bad.migrate_forward({}, "x.artifact", "1.0", "1.1"),
        UpgradeReasonCode.MIGRATION_INVALID_STEP,
        "non-Mapping return",
    )
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "unknown paths/no-ops/non-Mapping steps all fail closed")


def case_14_non_reversible_reverse_fails_closed() -> Result:
    name = "case_14_non_reversible_reverse_fails_closed"
    registry = _registry()
    problems: List[str] = []
    state_v12 = {"legacy_mode": True, "heartbeat_seconds": 30, "label": "node"}
    _expect_reject(
        name, problems,
        lambda: registry.migrate_backward(state_v12, "node.config", "2.0", "1.2"),
        UpgradeReasonCode.MIGRATION_NOT_REVERSIBLE,
        "reverse the breaking step",
    )
    _expect_reject(
        name, problems,
        lambda: registry.migrate_backward(state_v12, "node.config", "2.0", "1.0"),
        UpgradeReasonCode.MIGRATION_NOT_REVERSIBLE,
        "reverse through the breaking step",
    )
    # Forward past the breaking step still works (irreversible
    # forward evolution is legal; only the reversal is refused).
    migrated = registry.migrate_forward(state_v12, "node.config", "1.2", "2.0")
    if migrated != {"heartbeat_seconds": 30, "label": "node"}:
        problems.append("breaking forward migration wrong: %r" % (migrated,))
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "declared non-reversible steps are never reversed (fail closed)")


def case_15_migration_determinism() -> Result:
    name = "case_15_migration_determinism"
    registry = _registry()
    # Same content, different insertion order: canonical outcomes
    # are byte-identical.
    a = {"legacy_mode": True, "heartbeat_seconds": 30}
    b = {"heartbeat_seconds": 30, "legacy_mode": True}
    out_a = registry.migrate_forward(a, "node.config", "1.1", "1.2")
    out_b = registry.migrate_forward(b, "node.config", "1.1", "1.2")
    if json.dumps(out_a, sort_keys=True) != json.dumps(out_b, sort_keys=True):
        return fail(name, "input key order changed the canonical outcome")
    # Repeat runs are identical.
    if json.dumps(out_a, sort_keys=True) != json.dumps(
        registry.migrate_forward(a, "node.config", "1.1", "1.2"), sort_keys=True
    ):
        return fail(name, "repeat run diverged")
    return ok(name, "migration outcomes independent of input ordering and repeats")


# --------------------------------------------------------------------------
# 16-17: plan invariants and submission
# --------------------------------------------------------------------------

def case_16_plan_invariants() -> Result:
    name = "case_16_plan_invariants"
    problems: List[str] = []
    gates = dict(
        canary_gate=HealthGateSpec("canary-adapter-health", "adapter-health", ADAPTER_REF, "health-state", 1),
        rollout_gate=HealthGateSpec("rollout-path-loss", "path", UPLINK_REF, "loss-bp", 500),
        final_gate=HealthGateSpec("final-adapter-failures", "adapter-health", ADAPTER_REF, "consecutive-failures", 0),
    )
    base = dict(
        node_id=NODE_A,
        from_version=SoftwareVersion.parse("2.0.0"),
        to_version=SoftwareVersion.parse("2.1.0"),
        target_protocol_profile=ProtocolProfile(major=1, max_minor=1),
        target_schema_versions=(("node.config", "1.2"),),
        minimum_version_floor=SoftwareVersion.parse("2.0.0"),
        **gates,
    )
    UpgradePlan(**base)  # constructs
    # Downgrade plans are not constructible.
    _expect_reject(
        name, problems,
        lambda: UpgradePlan(**(base | {"to_version": SoftwareVersion.parse("2.0.0")})),
        UpgradeReasonCode.NOT_AN_UPGRADE,
        "to == from",
    )
    _expect_reject(
        name, problems,
        lambda: UpgradePlan(**(base | {"to_version": SoftwareVersion.parse("1.9.9")})),
        UpgradeReasonCode.NOT_AN_UPGRADE,
        "to < from",
    )
    # Floor must be within [from, to].
    _expect_reject(
        name, problems,
        lambda: UpgradePlan(**(base | {"minimum_version_floor": SoftwareVersion.parse("1.0.0")})),
        UpgradeReasonCode.PLAN_INVALID,
        "floor below from",
    )
    _expect_reject(
        name, problems,
        lambda: UpgradePlan(**(base | {"minimum_version_floor": SoftwareVersion.parse("2.2.0")})),
        UpgradeReasonCode.PLAN_INVALID,
        "floor above to",
    )
    # Gates are required; labels distinct.
    _expect_reject(
        name, problems,
        lambda: UpgradePlan(**(base | {"final_gate": None})),
        UpgradeReasonCode.PLAN_INVALID,
        "missing final gate",
    )
    _expect_reject(
        name, problems,
        lambda: UpgradePlan(**(base | {"final_gate": gates["rollout_gate"]})),
        UpgradeReasonCode.PLAN_INVALID,
        "duplicate gate labels",
    )
    # Complete-content tamper matrix on the derived plan.
    plan = UpgradePlan(**base)
    tampered = plan.to_dict() | {"to_version": "9.9.9"}
    _expect_reject(
        name, problems,
        lambda: upgrade_plan_from_dict(tampered),
        UpgradeReasonCode.INVALID_INPUT,
        "tampered plan retains the id",
    )
    rebuilt = upgrade_plan_from_dict(plan.to_dict())
    if rebuilt.to_dict() != plan.to_dict():
        problems.append("plan round-trip not byte-identical")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "upgrade-only plans; floor range; gates; complete-content id")


def case_17_submit_validation_matrix() -> Result:
    name = "case_17_submit_validation_matrix"
    problems: List[str] = []
    manager = _manager(NODE_A)
    template = _template()
    # Wrong node.
    _expect_reject(
        name, problems,
        lambda: manager.submit_plan(template.plan_for(NODE_B, SoftwareVersion.parse("2.0.0")), _NOW),
        UpgradeReasonCode.PLAN_INVALID,
        "wrong node",
    )
    # Wrong from_version.
    _expect_reject(
        name, problems,
        lambda: manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("1.9.0")), _NOW),
        UpgradeReasonCode.PLAN_VERSION_MISMATCH,
        "wrong from_version",
    )
    # Unknown protocol major in the target profile.
    future = _template(to_profile=(2, 0), to_schema="1.2")
    _expect_reject(
        name, problems,
        lambda: manager.submit_plan(future.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW),
        UpgradeReasonCode.MAJOR_UNKNOWN,
        "unknown target major",
    )
    # Schema key mismatch (node has node.config; plan targets another).
    odd = RolloutTemplate(
        to_version=SoftwareVersion.parse("2.1.0"),
        target_protocol_profile=ProtocolProfile(major=1, max_minor=1),
        target_schema_versions=(("other.config", "1.2"),),
        minimum_version_floor=SoftwareVersion.parse("2.0.0"),
        canary_gate=HealthGateSpec("canary-adapter-health", "adapter-health", ADAPTER_REF, "health-state", 1),
        rollout_gate=HealthGateSpec("rollout-path-loss", "path", UPLINK_REF, "loss-bp", 500),
        final_gate=HealthGateSpec("final-adapter-failures", "adapter-health", ADAPTER_REF, "consecutive-failures", 0),
    )
    _expect_reject(
        name, problems,
        lambda: manager.submit_plan(odd.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW),
        UpgradeReasonCode.PLAN_INVALID,
        "schema key mismatch",
    )
    # Non-reversible chain cannot be staged: a plan targeting 2.0
    # crosses the breaking irreversible step.
    irreversible = _template(to_schema="2.0")
    _expect_reject(
        name, problems,
        lambda: manager.submit_plan(irreversible.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW),
        UpgradeReasonCode.MIGRATION_NOT_REVERSIBLE,
        "non-reversible chain",
    )
    # A valid plan is accepted, and a second concurrent plan is not.
    manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW)
    _expect_reject(
        name, problems,
        lambda: manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW),
        UpgradeReasonCode.ACTIVE_PLAN_EXISTS,
        "second concurrent plan",
    )
    # Every rejection left an audit event.
    kinds = [event.kind for event in manager.events()]
    for expected in (EventKind.PLAN_REJECTED, EventKind.PLAN_ACCEPTED):
        if expected not in kinds:
            problems.append("missing audit event %r (saw %r)" % (expected, kinds))
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "submission matrix fails closed per rule; every rejection audited")


# --------------------------------------------------------------------------
# 18-25: the staged ladder on one node
# --------------------------------------------------------------------------

def case_18_staged_ladder_happy_path() -> Result:
    name = "case_18_staged_ladder_happy_path"
    manager = _manager(NODE_A)
    template = _template()
    manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW)
    if manager.stage != UpgradeStage.PLANNED:
        return fail(name, "submit must land in PLANNED, got %r" % manager.stage)
    manager.begin(_NOW)
    if manager.stage != UpgradeStage.PREPARED:
        return fail(name, "begin must land in PREPARED")
    # PREPARED is staged, NOT live: version truth unchanged.
    if manager.software_version != SoftwareVersion.parse("2.0.0"):
        return fail(name, "PREPARED must not switch the live version")
    obs = _healthy_observations(NODE_A)
    manager.advance(_NOW, obs)  # canary gate
    if manager.stage != UpgradeStage.CANARY:
        return fail(name, "canary gate PASS must land in CANARY, got %r" % manager.stage)
    inventory = manager.inventory()
    if (
        inventory.software_version != SoftwareVersion.parse("2.1.0")
        or inventory.protocol_profile != ProtocolProfile(major=1, max_minor=1)
        or dict(inventory.schema_versions)["node.config"] != "1.2"
    ):
        return fail(name, "CANARY must be live at the plan targets: %r" % (inventory.to_dict(),))
    if manager.schema_state("node.config") != {
        "legacy_mode": True, "heartbeat_seconds": 30, "label": "node",
    }:
        return fail(name, "canary schema state wrong: %r" % manager.schema_state("node.config"))
    manager.advance(_NOW, obs)  # rollout gate
    if manager.stage != UpgradeStage.ROLLING:
        return fail(name, "rollout gate PASS must land in ROLLING")
    result = manager.advance(_NOW, obs)  # final gate
    if result.verdict != GateVerdict.PASS or manager.stage != UpgradeStage.ROLLING:
        return fail(name, "final gate PASS must leave commit-ready ROLLING")
    # Commit is not yet allowed to be skipped: commit() closes the
    # window and ratchets the floor.
    manager.commit(_LATER)
    if manager.stage != UpgradeStage.COMMITTED:
        return fail(name, "commit must land in COMMITTED")
    if manager.minimum_version_floor != SoftwareVersion.parse("2.0.0"):
        return fail(name, "commit must ratchet the floor to the plan floor")
    # Exact event order for the happy path.
    kinds = [event.kind for event in manager.events()]
    expected = [
        EventKind.PLAN_ACCEPTED, EventKind.STAGE_ADVANCED,      # begin
        EventKind.GATE_PASS, EventKind.STAGE_ADVANCED,          # canary
        EventKind.GATE_PASS, EventKind.STAGE_ADVANCED,          # rollout
        EventKind.GATE_PASS, EventKind.GATE_PASS,               # final (+commit-ready)
        EventKind.COMMITTED,
    ]
    if kinds != expected:
        return fail(name, "event order %r != %r" % (kinds, expected))
    return ok(name, "PLANNED->PREPARED->CANARY->ROLLING->COMMITTED with exact event order")


def case_19_gate_requires_real_self_telemetry() -> Result:
    name = "case_19_gate_requires_real_self_telemetry"
    manager = _manager(NODE_A)
    template = _template()
    manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW)
    manager.begin(_NOW)
    # Non-telemetry evidence fails closed.
    class FakeObservation:
        subject_kind = "adapter-health"
        subject_ref = ADAPTER_REF
        metric = "health-state"
        value = 0

    _expect_reject(
        name, [],
        lambda: manager.evaluate_gate(template.canary_gate, [FakeObservation()], _NOW),  # type: ignore[list-item]
        UpgradeReasonCode.INVALID_INPUT,
        "non-telemetry evidence",
    )
    # PR #31 Architect review blocker 1, red test (a): a FULLY
    # POPULATED attribute-shaped fake is still not telemetry --
    # duck typing never establishes provenance, no matter how
    # complete the shape is.
    class CompleteFakeObservation:
        subject_kind = "adapter-health"
        subject_ref = ADAPTER_REF
        metric = "health-state"
        value = 0
        observed_at = _NOW
        freshness_until = "2026-09-01T13:00:00Z"
        sequence = 1
        observation_id = "telemetry:observation:forged"
        source_node_id = NODE_A
        source_class = "self-advertised"
        confidence_basis_points = 9000
        privacy_class = "internal"

    _expect_reject(
        name, [],
        lambda: manager.evaluate_gate(
            template.canary_gate, [CompleteFakeObservation()], _NOW,  # type: ignore[list-item]
        ),
        UpgradeReasonCode.INVALID_INPUT,
        "fully populated fake observation",
    )
    # PR #31 Architect review blocker 1, red test (b): a VALID,
    # constructor-genuine TelemetryObservation (complete-content id
    # and all) that was NEVER RECORDED by the telemetry authority is
    # caller-injected evidence -- integrity is not provenance -- and
    # is rejected even though every field is internally valid.
    unrecorded = _observation(
        NODE_A, "adapter-health", ADAPTER_REF, "health-state", 0,
        record=False,
    )
    _expect_reject(
        name, [],
        lambda: manager.evaluate_gate(template.canary_gate, [unrecorded], _NOW),
        UpgradeReasonCode.INVALID_INPUT,
        "unrecorded genuine observation",
    )
    # Recorded in ANOTHER node's store, supplied to this node's
    # manager: provenance is resolved against THIS node's telemetry
    # authority, so cross-store injection is rejected too.
    _manager(NODE_B)  # registers NODE_B's own provenance oracle
    cross_store = _observation(
        NODE_B, "adapter-health", ADAPTER_REF, "health-state", 0,
    )
    _expect_reject(
        name, [],
        lambda: manager.evaluate_gate(template.canary_gate, [cross_store], _NOW),
        UpgradeReasonCode.INVALID_INPUT,
        "cross-store observation",
    )
    # A TAMPERED VARIANT of a genuinely recorded observation (same
    # recorded id, mutated content): only the exact recorded bytes
    # are evidence, so the forgery is rejected outright.
    recorded = _observation(
        NODE_A, "adapter-health", ADAPTER_REF, "health-state", 0,
    )
    tampered = copy.copy(recorded)
    object.__setattr__(tampered, "value", 1)  # same id, different content
    _expect_reject(
        name, [],
        lambda: manager.evaluate_gate(template.canary_gate, [tampered], _NOW),
        UpgradeReasonCode.INVALID_INPUT,
        "tampered variant of a recorded observation",
    )
    # Every provenance rejection left the stage untouched.
    if manager.stage != UpgradeStage.PREPARED:
        return fail(name, "provenance rejections must leave the stage unchanged")
    # No evidence at all -> INSUFFICIENT_EVIDENCE, stage unchanged.
    try:
        manager.advance(_NOW, [])
        return fail(name, "advance with no evidence must fail closed")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.GATE_INSUFFICIENT_EVIDENCE:
            return fail(name, "expected GATE_INSUFFICIENT_EVIDENCE, got %r" % error.reason)
    if manager.stage != UpgradeStage.PREPARED:
        return fail(name, "stage must be unchanged after insufficient evidence")
    # A FOREIGN-sourced healthy observation (genuinely RECORDED in
    # this node's store) is a claim by another node (LOCK-008) -- it
    # passes provenance but can still never satisfy this node's gate.
    foreign = _observation(
        NODE_A, "adapter-health", ADAPTER_REF, "health-state", 0,
        source=NODE_B,
    )
    try:
        manager.advance(_NOW, [foreign])
        return fail(name, "foreign-sourced evidence must not pass the gate")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.GATE_INSUFFICIENT_EVIDENCE:
            return fail(name, "foreign evidence must yield GATE_INSUFFICIENT_EVIDENCE, got %r" % error.reason)
        if "foreign" not in error.detail:
            return fail(name, "the foreign-evidence detail must say so: %r" % error.detail)
    # Real SELF-sourced RECORDED evidence passes and advances.
    manager.advance(_NOW, _healthy_observations(NODE_A))
    if manager.stage != UpgradeStage.CANARY:
        return fail(name, "self-sourced evidence must advance to CANARY")
    return ok(
        name,
        "gates demand recorded self-sourced telemetry: fakes (complete or "
        "not), unrecorded/cross-store/tampered injections, foreign claims, "
        "and absences all fail closed",
    )


def case_20_stale_evidence_fails_closed() -> Result:
    name = "case_20_stale_evidence_fails_closed"
    manager = _manager(NODE_A)
    template = _template()
    manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW)
    manager.begin(_NOW)
    # The observation's freshness window ended before _LATER.
    stale = _observation(
        NODE_A, "adapter-health", ADAPTER_REF, "health-state", 0,
        at=_EARLIER, fresh_for_seconds=1800,  # fresh until 11:30 < 13:00
    )
    try:
        manager.advance(_LATER, [stale])
        return fail(name, "stale evidence must fail closed")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.GATE_INSUFFICIENT_EVIDENCE:
            return fail(name, "expected GATE_INSUFFICIENT_EVIDENCE, got %r" % error.reason)
    if manager.stage != UpgradeStage.PREPARED:
        return fail(name, "stage must be unchanged after stale evidence")
    kinds = [event.kind for event in manager.events()]
    if EventKind.GATE_INSUFFICIENT_EVIDENCE not in kinds:
        return fail(name, "the stale verdict must be audited")
    return ok(name, "stale evidence is no evidence: the gate fails closed")


def case_21_gate_threshold_and_latest_evidence() -> Result:
    name = "case_21_gate_threshold_and_latest_evidence"
    manager = _manager(NODE_A)
    template = _template()
    manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW)
    manager.begin(_NOW)
    # A FAILED adapter (ordinal 2) exceeds the canary threshold 1.
    failed = _observation(NODE_A, "adapter-health", ADAPTER_REF, "health-state", 2)
    try:
        manager.advance(_NOW, [failed])
        return fail(name, "health-state 2 must fail the gate")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.GATE_NOT_PASSED:
            return fail(name, "expected GATE_NOT_PASSED, got %r" % error.reason)
    if manager.stage != UpgradeStage.PREPARED:
        return fail(name, "stage must be unchanged after a gate failure")
    # The deterministic LATEST observation decides: an older healthy
    # sample cannot rescue a newer degraded one...  (sequences
    # auto-advance per stream in build order, mirroring the store's
    # ingest ledger)
    older_ok = _observation(NODE_A, "adapter-health", ADAPTER_REF, "health-state", 0, at=_EARLIER)
    newer_bad = _observation(NODE_A, "adapter-health", ADAPTER_REF, "health-state", 1, at=_NOW)
    verdict = manager.evaluate_gate(template.canary_gate, [older_ok, newer_bad], _NOW)
    if verdict.verdict != GateVerdict.PASS or verdict.observed_value != 1:
        return fail(name, "latest=1 within threshold 1 must PASS: %r" % (verdict,))
    newest_bad = _observation(NODE_A, "adapter-health", ADAPTER_REF, "health-state", 2, at=_NOW)
    verdict2 = manager.evaluate_gate(template.canary_gate, [older_ok, newest_bad], _NOW)
    if verdict2.verdict != GateVerdict.FAIL or verdict2.observed_value != 2:
        return fail(name, "latest=2 must FAIL: %r" % (verdict2,))
    # ...and an older degraded sample cannot block a newer healthy one.
    older_bad = _observation(NODE_A, "adapter-health", ADAPTER_REF, "health-state", 2, at=_EARLIER)
    newer_ok = _observation(NODE_A, "adapter-health", ADAPTER_REF, "health-state", 0, at=_NOW)
    verdict3 = manager.evaluate_gate(template.canary_gate, [older_bad, newer_ok], _NOW)
    if verdict3.verdict != GateVerdict.PASS or verdict3.observed_value != 0:
        return fail(name, "latest=0 must PASS: %r" % (verdict3,))
    # Gate spec thresholds are bounded by the REAL metric registry.
    _expect_reject(
        name, [],
        lambda: HealthGateSpec("impossible", "adapter-health", ADAPTER_REF, "health-state", 99),
        UpgradeReasonCode.INVALID_INPUT,
        "threshold beyond the metric range",
    )
    _expect_reject(
        name, [],
        lambda: HealthGateSpec("bogus-metric", "adapter-health", ADAPTER_REF, "not-a-metric", 1),
        UpgradeReasonCode.INVALID_INPUT,
        "unregistered metric",
    )
    return ok(name, "thresholds enforced; the deterministic latest observation decides")


def case_22_commit_requires_final_gate() -> Result:
    name = "case_22_commit_requires_final_gate"
    manager = _manager(NODE_A)
    template = _template()
    obs = _healthy_observations(NODE_A)
    manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW)
    manager.begin(_NOW)
    # Commit is refused before ROLLING.
    _expect_reject(
        name, [], lambda: manager.commit(_NOW),
        UpgradeReasonCode.WRONG_STAGE, "commit from PREPARED",
    )
    manager.advance(_NOW, obs)
    _expect_reject(
        name, [], lambda: manager.commit(_NOW),
        UpgradeReasonCode.WRONG_STAGE, "commit from CANARY",
    )
    manager.advance(_NOW, obs)  # -> ROLLING
    # Commit is refused with the final gate unpassed.
    _expect_reject(
        name, [], lambda: manager.commit(_NOW),
        UpgradeReasonCode.WRONG_STAGE, "commit before the final gate",
    )
    manager.advance(_NOW, obs)  # final gate -> commit-ready
    manager.commit(_NOW)
    if manager.stage != UpgradeStage.COMMITTED:
        return fail(name, "commit after the final gate must succeed")
    return ok(name, "commit requires ROLLING + final gate PASS (no shortcuts)")


def case_23_rollback_restores_state() -> Result:
    name = "case_23_rollback_restores_state"
    manager = _manager(NODE_A)
    template = _template()
    obs = _healthy_observations(NODE_A)
    state_before = json.dumps(manager.schema_state("node.config"), sort_keys=True)
    manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW)
    manager.begin(_NOW)
    manager.advance(_NOW, obs)
    manager.advance(_NOW, obs)  # ROLLING
    before = manager.inventory().to_dict()
    if before["software_version"] != "2.1.0":
        return fail(name, "fixture sanity: the canary must be live pre-rollback")
    manager.rollback(_LATER)
    if manager.stage != UpgradeStage.ROLLED_BACK:
        return fail(name, "rollback must land in ROLLED_BACK, got %r" % manager.stage)
    restored = manager.inventory()
    if restored.software_version != SoftwareVersion.parse("2.0.0"):
        return fail(name, "rollback must restore the software version")
    if restored.protocol_profile != ProtocolProfile(major=1, max_minor=0):
        return fail(name, "rollback must restore the protocol profile")
    if dict(restored.schema_versions)["node.config"] != "1.1":
        return fail(name, "rollback must restore the schema version")
    if json.dumps(manager.schema_state("node.config"), sort_keys=True) != state_before:
        return fail(name, "rollback must reverse-migrate the schema state byte-identically")
    if restored.software_version == SoftwareVersion.parse("2.1.0"):
        return fail(name, "rollback left the canary version live")
    # ROLLED_BACK is terminal.
    _expect_reject(
        name, [], lambda: manager.advance(_NOW, obs),
        UpgradeReasonCode.WRONG_STAGE, "advance after rollback",
    )
    _expect_reject(
        name, [], lambda: manager.rollback(_NOW),
        UpgradeReasonCode.WRONG_STAGE, "rollback after rollback",
    )
    return ok(name, "rollback restores the pre-plan truth byte-identically; terminal")


def case_24_post_commit_window_closed() -> Result:
    name = "case_24_post_commit_window_closed"
    manager = _manager(NODE_A)
    template = _template()
    obs = _healthy_observations(NODE_A)
    manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW)
    manager.begin(_NOW)
    manager.advance(_NOW, obs)
    manager.advance(_NOW, obs)
    manager.advance(_NOW, obs)
    manager.commit(_NOW)
    try:
        manager.rollback(_LATER)
        return fail(name, "post-commit rollback must be refused")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.ROLLBACK_WINDOW_CLOSED:
            return fail(name, "expected ROLLBACK_WINDOW_CLOSED, got %r" % error.reason)
    if manager.stage != UpgradeStage.COMMITTED:
        return fail(name, "COMMITTED must survive the refused rollback")
    if manager.minimum_version_floor != SoftwareVersion.parse("2.0.0"):
        return fail(name, "the floor must survive the refused rollback")
    kinds = [event.kind for event in manager.events()]
    if kinds.count(EventKind.COMMITTED) != 1:
        return fail(name, "exactly one commit event expected, saw %r" % kinds)
    return ok(name, "post-commit rollback window closed; a further change is a new plan")


def case_25_floor_ratchet_blocks_below_floor_plans() -> Result:
    name = "case_25_floor_ratchet_blocks_below_floor_plans"
    manager = _manager(NODE_A, software="1.9.0", profile=(1, 0), schema="1.1")
    template = _template(to_software="2.0.0", to_schema="1.2", floor="2.0.0")
    obs = _healthy_observations(NODE_A)
    manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("1.9.0")), _NOW)
    manager.begin(_NOW)
    manager.advance(_NOW, obs)
    manager.advance(_NOW, obs)
    manager.advance(_NOW, obs)
    manager.commit(_NOW)
    if manager.minimum_version_floor != SoftwareVersion.parse("2.0.0"):
        return fail(name, "commit must ratchet the floor to 2.0.0")
    # A stale node rejoining below the floor: the manager refuses an
    # in-band plan starting below the floor (fail closed, audited).
    stale = _manager(NODE_B, software="1.9.0", profile=(1, 0), schema="1.1",
                     floor="2.0.0")
    try:
        stale.submit_plan(template.plan_for(NODE_B, SoftwareVersion.parse("1.9.0")), _NOW)
        return fail(name, "a plan from below the floor must be refused")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.FLOOR_VIOLATION:
            return fail(name, "expected FLOOR_VIOLATION, got %r" % error.reason)
    if [event.kind for event in stale.events()] != [EventKind.DOWNGRADE_BLOCKED]:
        return fail(name, "the floor rejection must be audited as DOWNGRADE_BLOCKED")
    return ok(name, "floor ratchets on commit; below-floor starts fail closed and audited")


# --------------------------------------------------------------------------
# 26-32: the population integration scenarios
# --------------------------------------------------------------------------

def case_26_rolling_upgrade_population() -> Result:
    name = "case_26_rolling_upgrade_population"
    population = _population()
    coordinator = RolloutCoordinator(population)
    template = _template()
    canary = coordinator.stage_canary(
        template, _NOW, _healthy_observations(NODE_A),
    )
    if canary != NODE_A:
        return fail(name, "the deterministic canary is the first node id")
    if coordinator.distinct_software_versions() != (
        SoftwareVersion.parse("2.0.0"), SoftwareVersion.parse("2.1.0"),
    ):
        return fail(name, "population must be mixed after the canary")
    coordinator.stage_remaining(
        template, _NOW,
        {node: _healthy_observations(node) for node in (NODE_A, NODE_B, NODE_C, NODE_D)},
    )
    committed = coordinator.commit_population(
        _LATER,
        {node: _healthy_observations(node, at=_LATER) for node in (NODE_A, NODE_B, NODE_C, NODE_D)},
    )
    if committed != (NODE_A, NODE_B, NODE_C, NODE_D):
        return fail(name, "commit order %r" % (committed,))
    for node_id, manager in population.items():
        if manager.stage != UpgradeStage.COMMITTED:
            return fail(name, "%r not COMMITTED (%r)" % (node_id, manager.stage))
        inventory = manager.inventory()
        if inventory.software_version != SoftwareVersion.parse("2.1.0"):
            return fail(name, "%r not at 2.1.0" % node_id)
        if inventory.protocol_profile != ProtocolProfile(major=1, max_minor=1):
            return fail(name, "%r not at profile 1.1" % node_id)
        if manager.schema_state("node.config") != {
            "legacy_mode": True, "heartbeat_seconds": 30, "label": "node",
        }:
            return fail(name, "%r schema state wrong" % node_id)
    if coordinator.distinct_software_versions() != (SoftwareVersion.parse("2.1.0"),):
        return fail(name, "population must be uniform after commit")
    return ok(name, "4-node rolling upgrade: canary -> staged -> committed, uniform at 2.1.0")


def case_27_mixed_version_coexistence_mid_rollout() -> Result:
    name = "case_27_mixed_version_coexistence_mid_rollout"
    population = _population()
    coordinator = RolloutCoordinator(population)
    coordinator.stage_canary(_template(), _NOW, _healthy_observations(NODE_A))
    # Mid-rollout the population is MIXED by design: the canary at
    # 2.1.0/profile 1.1 coexists with every 2.0.0/profile 1.0 peer.
    canary_inventory = population[NODE_A].inventory()
    for node_id in (NODE_B, NODE_C, NODE_D):
        peer_inventory = population[node_id].inventory()
        report = coexistence_report(
            canary_inventory, peer_inventory,
            peer_statements=(_statement(node_id, schema_version="1.1"),),
            requirements=(_requirement("1.0"),),
            now=_NEGOTIATION_NOW,
        )
        if not report.coexist:
            return fail(
                name, "mixed-version pair (%s) failed coexistence: %r"
                % (node_id, report.to_dict())
            )
        if str(report.profile.selected) != "1.0":
            return fail(name, "common profile mid-rollout must be 1.0")
    # And the mixed population is observable as mixed.
    if len(coordinator.distinct_software_versions()) != 2:
        return fail(name, "population must show two distinct versions mid-rollout")
    return ok(name, "the canary coexists with every 2.0.0 peer mid-rollout at profile 1.0")


def case_28_mixed_version_envelope_interop() -> Result:
    name = "case_28_mixed_version_envelope_interop"
    problems: List[str] = []
    # A real envelope at the negotiated common profile (major 1)
    # interoperates through the REAL WORK-003 validation pipeline.
    envelope = Envelope(
        version=1,
        message_type="capability.advertise",
        message_id="msg-0001",
        sender=NODE_A,
        issued_at=_NOW,
        expires_at="2026-09-02T12:00:00Z",
        payload={"capability": "capability.core.multipath"},
        signature="test-signature",
    )
    policy = ParsePolicy(unknown_type=UnknownTypePolicy.FORWARD_OPAQUE)
    verdict = work003_validate(
        envelope, now=_NEGOTIATION_NOW, policy=policy,
    )
    if not verdict.accepted or verdict.classification != Classification.KNOWN_COMPATIBLE:
        problems.append("v1 envelope not accepted as known-compatible: %r" % (verdict.detail,))
    # Additive evolution on the wire: a 1.1-speaker's optional
    # extension is preserved by a 1.0 receiver (KNOWN_ADDITIVE).
    additive = Envelope(
        version=1,
        message_type="capability.advertise",
        message_id="msg-0002",
        sender=NODE_A,
        issued_at=_NOW,
        expires_at="2026-09-02T12:00:00Z",
        extensions={"future-optional-feature": {"value": 7}},
        payload={},
        signature="test-signature",
    )
    additive_verdict = work003_validate(additive, now=_NEGOTIATION_NOW, policy=policy)
    if not additive_verdict.accepted or additive_verdict.classification != Classification.KNOWN_ADDITIVE:
        problems.append("additive envelope not KNOWN_ADDITIVE: %r" % (additive_verdict.detail,))
    # A v2 (un-invented major) envelope FAILS CLOSED at a profile-1.x
    # receiver, exactly as the WORK-003 pipeline dictates.
    future = Envelope(
        version=2,
        message_type="capability.advertise",
        message_id="msg-0003",
        sender=NODE_A,
        issued_at=_NOW,
        expires_at="2026-09-02T12:00:00Z",
        payload={},
        signature="test-signature",
    )
    future_verdict = work003_validate(future, now=_NEGOTIATION_NOW, policy=policy)
    if future_verdict.accepted or future_verdict.classification != Classification.REJECTED_INCOMPATIBLE_MAJOR:
        problems.append("v2 envelope must fail closed: %r" % (future_verdict.classification,))
    # The negotiated common profile of the mid-rollout mixed pair is
    # exactly the major the pipeline accepts.
    negotiation = negotiate_protocol_profile(ProtocolProfile(1, 1), ProtocolProfile(1, 0))
    if negotiation.selected is None or negotiation.selected.major != 1:
        problems.append("mid-rollout common profile must be major 1")
    # Round-trip through the real codec surface.
    rebuilt = envelope_from_mapping(envelope.to_dict())
    if rebuilt.to_dict() != envelope.to_dict():
        problems.append("envelope round-trip not byte-identical")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "common-profile v1 accepted; optional 1.1 content preserved (KNOWN_ADDITIVE); "
        "v2 rejected incompatible-major",
    )


def case_29_canary_failure_halts_rollout() -> Result:
    name = "case_29_canary_failure_halts_rollout"
    population = _population()
    coordinator = RolloutCoordinator(population)
    template = _template()
    # The canary stages (its canary gate is healthy)...
    coordinator.stage_canary(template, _NOW, _healthy_observations(NODE_A))
    # ...but its uplink then degrades: the rollout gate fails.
    degraded = (
        _observation(NODE_A, "adapter-health", ADAPTER_REF, "health-state", 0),
        _observation(NODE_A, "path", UPLINK_REF, "loss-bp", 9_000),  # >> 500
        _observation(NODE_A, "adapter-health", ADAPTER_REF, "consecutive-failures", 0),
    )
    try:
        coordinator.stage_remaining(
            template, _LATER, {NODE_A: degraded},
        )
        return fail(name, "an unhealthy canary must halt the rollout")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.GATE_NOT_PASSED:
            return fail(name, "expected GATE_NOT_PASSED, got %r" % error.reason)
    # The canary was rolled back; the later batches never began.
    if population[NODE_A].stage != UpgradeStage.ROLLED_BACK:
        return fail(name, "canary must be ROLLED_BACK, got %r" % population[NODE_A].stage)
    for node_id in (NODE_B, NODE_C, NODE_D):
        if population[node_id].stage is not None:
            return fail(name, "%r must never have begun (%r)" % (node_id, population[node_id].stage))
    if coordinator.distinct_software_versions() != (SoftwareVersion.parse("2.0.0"),):
        return fail(name, "population must be back to uniform 2.0.0")
    return ok(name, "unhealthy canary: rollout halted, canary rolled back, batches never began")


def case_30_per_node_failure_rolls_back_all() -> Result:
    name = "case_30_per_node_failure_rolls_back_all"
    population = _population()
    coordinator = RolloutCoordinator(population)
    template = _template()
    coordinator.stage_canary(template, _NOW, _healthy_observations(NODE_A))
    # Node C's adapter fails while staging the remaining nodes.
    broken_c = (
        _observation(NODE_C, "adapter-health", ADAPTER_REF, "health-state", 2),  # FAILED
        _observation(NODE_C, "path", UPLINK_REF, "loss-bp", 100),
        _observation(NODE_C, "adapter-health", ADAPTER_REF, "consecutive-failures", 5),
    )
    observations = {node: _healthy_observations(node) for node in (NODE_A, NODE_B, NODE_D)}
    observations[NODE_C] = broken_c
    try:
        coordinator.stage_remaining(template, _LATER, observations)
        return fail(name, "node C's failed canary gate must halt the rollout")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.GATE_NOT_PASSED:
            return fail(name, "expected GATE_NOT_PASSED, got %r" % error.reason)
    # EVERY begun node was rolled back (A, B live; C staged).
    for node_id, expected in (
        (NODE_A, UpgradeStage.ROLLED_BACK),
        (NODE_B, UpgradeStage.ROLLED_BACK),
        (NODE_C, UpgradeStage.ROLLED_BACK),
    ):
        if population[node_id].stage != expected:
            return fail(name, "%r must be %r, got %r" % (node_id, expected, population[node_id].stage))
    if population[NODE_D].stage is not None:
        return fail(name, "node D must never have begun")
    if coordinator.distinct_software_versions() != (SoftwareVersion.parse("2.0.0"),):
        return fail(name, "population must be uniform 2.0.0 after the halt")
    # The halt is auditable on every affected node.
    for node_id in (NODE_A, NODE_B, NODE_C):
        kinds = [event.kind for event in population[node_id].events()]
        if EventKind.ROLLBACK_COMPLETED not in kinds:
            return fail(name, "%r rollback not audited" % node_id)
    return ok(name, "per-node staging failure rolled back every begun node; D never began")


def case_31_commit_failure_leaves_committed_windows_closed() -> Result:
    name = "case_31_commit_failure_leaves_committed_windows_closed"
    population = _population()
    coordinator = RolloutCoordinator(population)
    template = _template()
    coordinator.stage_canary(template, _NOW, _healthy_observations(NODE_A))
    observations = {node: _healthy_observations(node) for node in population}
    coordinator.stage_remaining(template, _NOW, observations)
    # Node D's final gate fails at commit time (its adapter started
    # failing AFTER staging).
    observations_later = {
        node: _healthy_observations(node, at=_LATER) for node in population
    }
    observations_later[NODE_D] = (
        _observation(NODE_D, "adapter-health", ADAPTER_REF, "health-state", 0, at=_LATER),
        _observation(NODE_D, "path", UPLINK_REF, "loss-bp", 80, at=_LATER),
        _observation(
            NODE_D, "adapter-health", ADAPTER_REF, "consecutive-failures", 4,
            at=_LATER,
        ),
    )
    try:
        coordinator.commit_population(_LATER, observations_later)
        return fail(name, "node D's failed final gate must halt the commit phase")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.GATE_NOT_PASSED:
            return fail(name, "expected GATE_NOT_PASSED, got %r" % error.reason)
    # A/B/C committed BEFORE the failure: their windows stay closed
    # (committed is irreversible); only D rolled back.
    for node_id in (NODE_A, NODE_B, NODE_C):
        if population[node_id].stage != UpgradeStage.COMMITTED:
            return fail(name, "%r must stay COMMITTED" % node_id)
    if population[NODE_D].stage != UpgradeStage.ROLLED_BACK:
        return fail(name, "node D must be ROLLED_BACK, got %r" % population[NODE_D].stage)
    # The resulting MIXED population still coexists (this is the no-
    # flag-day property: a failed batch never forks the fabric).
    report = coexistence_report(
        population[NODE_A].inventory(), population[NODE_D].inventory(),
        peer_statements=(_statement(NODE_D, schema_version="1.1"),),
        requirements=(_requirement("1.0"),),
        now=_NEGOTIATION_NOW,
    )
    if not report.coexist or str(report.profile.selected) != "1.0":
        return fail(name, "post-failure mixed population must coexist: %r" % (report.to_dict(),))
    return ok(name, "committed windows stay closed; only the failed node rolled back; mixed fabric coexists")


def case_32_population_downgrade_protection() -> Result:
    name = "case_32_population_downgrade_protection"
    population = _population()
    coordinator = RolloutCoordinator(population)
    template = _template()
    observations = {node: _healthy_observations(node) for node in population}
    coordinator.stage_canary(template, _NOW, observations[NODE_A])
    coordinator.stage_remaining(template, _NOW, observations)
    coordinator.commit_population(_NOW, observations)
    # Cycle 2: stage a canary from 2.1.0 to 2.2.0 (no schema change).
    template2 = _template(to_software="2.2.0", to_schema="1.2", floor="2.1.0")
    coordinator.stage_canary(template2, _LATER, _healthy_observations(NODE_A, at=_LATER))
    # A population rollback BELOW the floor (2.0.0 < floor 2.0.0?
    # floors ratcheted to 2.0.0 on commit; 1.9.0 < 2.0.0) fails
    # closed and is audited on the node.
    try:
        coordinator.rollback_population(_LATER, SoftwareVersion.parse("1.9.0"))
        return fail(name, "rollback below the floor must be blocked")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.DOWNGRADE_BLOCKED:
            return fail(name, "expected DOWNGRADE_BLOCKED, got %r" % error.reason)
    kinds = [event.kind for event in population[NODE_A].events()]
    if EventKind.DOWNGRADE_BLOCKED not in kinds:
        return fail(name, "the blocked population rollback must be audited")
    # The canary is still staged (the block changed nothing).
    if population[NODE_A].stage != UpgradeStage.CANARY:
        return fail(name, "the blocked rollback must leave the canary staged")
    # The staged ORIGIN (2.1.0) rolls back cleanly.
    rolled = coordinator.rollback_population(_LATER, SoftwareVersion.parse("2.1.0"))
    if rolled != (NODE_A,):
        return fail(name, "rollback of the staged origin returned %r" % (rolled,))
    if population[NODE_A].stage != UpgradeStage.ROLLED_BACK:
        return fail(name, "canary must be ROLLED_BACK at the origin")
    if population[NODE_A].software_version != SoftwareVersion.parse("2.1.0"):
        return fail(name, "canary must be back at 2.1.0")
    return ok(name, "below-floor population rollback blocked+audited; origin rollback succeeds")


# --------------------------------------------------------------------------
# 33-40: boundaries, determinism, frozen surfaces, wiring
# --------------------------------------------------------------------------

def case_33_authority_boundaries_imports() -> Result:
    name = "case_33_authority_boundaries_imports"
    allowed_roots = {
        # stdlib
        "__future__", "ast", "hashlib", "json", "dataclasses", "typing",
        "re", "datetime",
        # composed authorities (consumed read-only as DATA) + the
        # canonical machinery
        "protocol", "capabilities", "telemetry",
    }
    offenders: List[str] = []
    upgrade_dir = os.path.join(_ROOT, "upgrade")
    for filename in sorted(os.listdir(upgrade_dir)):
        if not filename.endswith(".py"):
            continue
        with open(os.path.join(upgrade_dir, filename), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            roots = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue  # intra-package relative import (self)
                if node.module:
                    roots = [node.module.split(".")[0]]
            for root in roots:
                if root not in allowed_roots:
                    offenders.append("%s imports %s" % (filename, root))
    if offenders:
        return fail(name, "; ".join(offenders))
    # The family never touches the engines of the composed
    # authorities: only model/versioning/negotiation DATA surfaces,
    # plus -- the PR #31 Architect review blocker 1 correction,
    # deliberate and flagged -- the WORK-026 TelemetryStore's
    # recorded-observation PROVENANCE boundary (telemetry.store
    # is_recorded: the store is the only origin of gate evidence;
    # upgrade never calls any other store surface).
    for filename in sorted(os.listdir(upgrade_dir)):
        if not filename.endswith(".py"):
            continue
        with open(os.path.join(upgrade_dir, filename), encoding="utf-8") as handle:
            source = handle.read()
        for forbidden in (
            "from policy.evaluation", "from routing.engine",
            "from sessions.", "from topology.", "from identity.", "from energy.",
            "from adapters.", "import adapters", "import sessions", "import topology",
        ):
            if forbidden in source:
                return fail(name, "%s reaches into a foreign authority (%s)" % (filename, forbidden))
        # telemetry.store usage is pinned to the provenance surface
        # ONLY: the manager imports the store class and calls
        # is_recorded() -- never record/query/promotion ingest paths.
        if "from telemetry.store" in source:
            for banned in (
                ".record_observation(", ".query_observations(",
                ".authorize_topology_promotion(", ".snapshot()",
            ):
                if banned in source:
                    return fail(
                        name,
                        "%s uses a non-provenance telemetry.store surface "
                        "(%s) -- data-boundary discipline" % (filename, banned),
                    )
    # The family never writes files (no open-for-write anywhere).
    for filename in sorted(os.listdir(upgrade_dir)):
        if not filename.endswith(".py"):
            continue
        with open(os.path.join(upgrade_dir, filename), encoding="utf-8") as handle:
            source = handle.read()
        if re.search(r"open\(", source):
            return fail(name, "%s performs file I/O (the family is read-only over spec/)" % filename)
    # Nothing outside tools/ imports the family (the selftest is the
    # composition root; upgrade is the composer, never the composed).
    # WORK-033 amendment (deliberate, flagged in its PR): the Linux
    # reference agent family is a dependency-graph-sanctioned
    # DOWNSTREAM consumer of upgrade (spec/work-items.md: WORK-033
    # declares WORK-029 among its frozen dependencies); the agent
    # composes the real UpgradeManager/coexistence/migration surfaces
    # and never re-implements version semantics.
    for family in sorted(os.listdir(_ROOT)):
        family_path = os.path.join(_ROOT, family)
        if (
            not os.path.isdir(family_path)
            or family in ("upgrade", "tools", "agent")
            or family.startswith(".")
        ):
            continue
        for filename in sorted(os.listdir(family_path)):
            if not filename.endswith(".py"):
                continue
            with open(os.path.join(family_path, filename), encoding="utf-8") as handle:
                source = handle.read()
            if re.search(r"^\s*(from\s+upgrade|import\s+upgrade)\b", source, re.M):
                return fail(name, "%s/%s imports upgrade" % (family, filename))
    return ok(name, "family imports only composed-authority DATA; read-only; nothing imports it back")


def case_34_no_vendor_symbols() -> Result:
    name = "case_34_no_vendor_symbols"
    forbidden = (
        "5g", "fivegc", "open5gs", "wifi", "wlan", "lte", "gnb", "enb",
        "amf", "smf", "upf", "n3iwf", "kubernetes", "k8s", "docker",
        "prometheus", "grpc", "snmp", "ocudu", "srsran", "android", "ios",
    )
    upgrade_dir = os.path.join(_ROOT, "upgrade")
    for filename in sorted(os.listdir(upgrade_dir)):
        if not filename.endswith(".py"):
            continue
        with open(os.path.join(upgrade_dir, filename), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            tokens: List[str] = []
            if isinstance(node, ast.Name):
                tokens.append(node.id)
            elif isinstance(node, ast.Attribute):
                tokens.append(node.attr)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                tokens.append(node.name)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                tokens.append(node.value)
            for token in tokens:
                for bad in forbidden:
                    if re.search(r"\b%s\b" % re.escape(bad), token, re.IGNORECASE):
                        return fail(name, "%s carries vendor/access symbol %r" % (filename, token))
    return ok(name, "no vendor/access symbols in upgrade/ (word-boundary matched)")


def _scenario_fingerprint() -> str:
    """A canonical fingerprint of the whole composed scenario (used by
    the determinism case)."""
    registry = _registry()
    population = _population(registry)
    coordinator = RolloutCoordinator(population)
    template = _template()
    observations = {node: _healthy_observations(node) for node in population}
    coordinator.stage_canary(template, _NOW, observations[NODE_A])
    mid_mix = sorted(
        str(version) for version in coordinator.distinct_software_versions()
    )
    coordinator.stage_remaining(template, _NOW, observations)
    coordinator.commit_population(_NOW, observations)
    plan = template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0"))
    negotiation = negotiate_protocol_profile(ProtocolProfile(1, 1), ProtocolProfile(1, 0))
    parts = [
        plan.plan_id,
        negotiation.to_dict().__repr__(),
        json.dumps(mid_mix),
        json.dumps(
            coordinator.inventories()[0].to_dict(), sort_keys=True
        ),
        json.dumps(population[NODE_A].schema_state("node.config"), sort_keys=True),
        population[NODE_A].ledger_digest(),
        population[NODE_D].ledger_digest(),
        json.dumps(
            registry.migrate_forward(_STATE_1_1, "node.config", "1.1", "1.2"),
            sort_keys=True,
        ),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def case_35_determinism_across_hash_seeds() -> Result:
    name = "case_35_determinism_across_hash_seeds"
    script = (
        "import sys; sys.path.insert(0, %r); "
        "import tools.upgrade_selftest as t; "
        "print(t._scenario_fingerprint())" % (_ROOT,)
    )
    digests = []
    for seed in ("0", "1", "7919"):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, cwd=_ROOT,
            env=dict(os.environ, PYTHONHASHSEED=seed),
        )
        if proc.returncode != 0:
            return fail(name, "seed %s failed: %s" % (seed, proc.stderr.strip()[-300:]))
        digests.append(proc.stdout.strip())
    if len(set(digests)) != 1:
        return fail(name, "fingerprints diverge across seeds: %r" % (digests,))
    return ok(name, "composed scenario fingerprint identical across seeds 0/1/7919")


def case_36_frozen_spec_intact() -> Result:
    name = "case_36_frozen_spec_intact"
    # spec/ is FROZEN: byte-identical to origin/main.
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "spec/"],
        capture_output=True, text=True, cwd=_ROOT,
    )
    if status.stdout.strip():
        return fail(name, "uncommitted spec/ changes: %s" % status.stdout.strip())
    ref_check = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, text=True, cwd=_ROOT,
    )
    if ref_check.returncode == 0:
        spec_diff = subprocess.run(
            ["git", "diff", "--name-only", "origin/main", "HEAD", "--", "spec/"],
            capture_output=True, text=True, cwd=_ROOT,
        )
        if spec_diff.stdout.strip():
            return fail(name, "spec/ differs from origin/main: %s" % spec_diff.stdout.strip())
        docs_diff = subprocess.run(
            ["git", "diff", "--name-only", "origin/main", "HEAD", "--", "docs/"],
            capture_output=True, text=True, cwd=_ROOT,
        )
        changed = {line for line in docs_diff.stdout.splitlines() if line.strip()}
        allowed = {"docs/WORK-029-handoff.md"}  # the W023/024/025/028 handoff precedent
        if not changed <= allowed:
            return fail(name, "docs/ changes beyond the handoff: %r" % sorted(changed))
        return ok(name, "spec/ byte-identical to origin/main; docs/ additions = the W029 handoff only")
    # Degraded mode (no origin/main ref in this checkout): the
    # working tree must still be clean over spec/ and docs/.
    tree = subprocess.run(
        ["git", "status", "--porcelain", "--", "spec/", "docs/"],
        capture_output=True, text=True, cwd=_ROOT,
    )
    if tree.stdout.strip():
        return fail(name, "working tree dirty over frozen surfaces: %s" % tree.stdout.strip())
    return ok(name, "spec/ clean (origin/main ref unavailable; working tree clean)")


def case_37_py_compile_clean() -> Result:
    name = "case_37_py_compile_clean"
    import py_compile

    targets = [
        os.path.join(_ROOT, "upgrade", f)
        for f in sorted(os.listdir(os.path.join(_ROOT, "upgrade")))
        if f.endswith(".py")
    ]
    targets.append(os.path.abspath(__file__))
    for target in targets:
        try:
            py_compile.compile(target, doraise=True)
        except py_compile.PyCompileError as exc:
            return fail(name, "%s: %s" % (os.path.basename(target), exc))
    return ok(name, "py_compile clean for upgrade/ + selftest")


def case_38_ci_wiring() -> Result:
    name = "case_38_ci_wiring"
    workflow = os.path.join(_ROOT, ".github", "workflows", "spec-check.yml")
    with open(workflow, encoding="utf-8") as handle:
        source = handle.read()
    expected = [
        "tools/spec_check.py", "tools/spec_check_selftest.py",
        "tools/schema_check.py", "tools/schema_selftest.py",
        "tools/envelope_selftest.py", "tools/identity_selftest.py",
        "tools/capability_selftest.py", "tools/discovery_selftest.py",
        "tools/topology_selftest.py", "tools/resource_selftest.py",
        "tools/intent_selftest.py", "tools/policy_selftest.py",
        "tools/routing_selftest.py", "tools/session_selftest.py",
        "tools/multipath_selftest.py", "tools/mobility_selftest.py",
        "tools/federation_selftest.py", "tools/adapter_selftest.py",
        "tools/transport_selftest.py", "tools/ipintegration_selftest.py",
        "tools/fivegc_selftest.py", "tools/wifi_selftest.py",
        "tools/backhaul_selftest.py", "tools/mesh_selftest.py",
        "tools/distcore_selftest.py", "tools/service_selftest.py",
        "tools/telemetry_selftest.py", "tools/energy_selftest.py",
        "tools/security_selftest.py", "tools/upgrade_selftest.py",
    ]
    missing = [battery for battery in expected if battery not in source]
    if missing:
        return fail(name, "batteries missing from CI: %r" % missing)
    return ok(name, "CI runs all 30 batteries including the upgrade battery")


def case_39_serialization_round_trips() -> Result:
    name = "case_39_serialization_round_trips"
    problems: List[str] = []
    manager = _manager(NODE_A)
    inventory = manager.inventory()
    plan = _template().plan_for(NODE_A, SoftwareVersion.parse("2.0.0"))
    descriptor = MigrationDescriptor("node.config", "1.1", "1.2", True, False)
    event = UpgradeEvent(
        kind=EventKind.PLAN_ACCEPTED, plan_id=plan.plan_id, node_id=NODE_A,
        stage=UpgradeStage.PLANNED, at=_NOW, detail="probe",
    )
    gate_result = HealthGateResult(
        label="probe", verdict=GateVerdict.PASS, observed_value=1,
        observation_id="telemetry:observation:probe", observed_at=_NOW,
        freshness_until="2026-09-01T13:00:00Z", detail="probe detail",
    )
    pairs = [
        (version_inventory_from_dict, inventory),
        (upgrade_plan_from_dict, plan),
        (migration_descriptor_from_dict, descriptor),
        (upgrade_event_from_dict, event),
        (health_gate_spec_from_dict, _template().canary_gate),
        (health_gate_result_from_dict, gate_result),
    ]
    for from_dict, record in pairs:
        data = record.to_dict()
        rebuilt = from_dict(data)
        if rebuilt.to_dict() != data:
            problems.append(
                "round-trip not byte-identical for %s" % type(record).__name__
            )
    # Truncated DATA fails closed.
    truncated = inventory.to_dict()
    truncated.pop("schema_versions")
    try:
        version_inventory_from_dict(truncated)
        problems.append("truncated inventory accepted")
    except UpgradeError:
        pass
    # The gate-result verdict vocabulary is frozen on parse.
    forged = gate_result.to_dict() | {"verdict": "PROBABLY_FINE"}
    try:
        health_gate_result_from_dict(forged)
        problems.append("forged verdict accepted")
    except UpgradeError:
        pass
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "all record round-trips byte-identical; truncated/forged DATA fails closed")


def case_40_schema_state_isolation() -> Result:
    name = "case_40_schema_state_isolation"
    manager = _manager(NODE_A)
    original = json.dumps(manager.schema_state("node.config"), sort_keys=True)
    # The handed-out state is a COPY: mutating it cannot touch the node.
    leak = manager.schema_state("node.config")
    leak["legacy_mode"] = False
    leak["injected"] = True
    if json.dumps(manager.schema_state("node.config"), sort_keys=True) != original:
        return fail(name, "schema_state() handed out internal mutable state")
    # A full staged cycle leaves the internal state byte-identical to
    # its pre-cycle self (advance applies to copies; rollback restores).
    template = _template()
    obs = _healthy_observations(NODE_A)
    manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW)
    manager.begin(_NOW)
    manager.advance(_NOW, obs)
    manager.advance(_NOW, obs)
    manager.rollback(_LATER)
    if json.dumps(manager.schema_state("node.config"), sort_keys=True) != original:
        return fail(name, "internal schema state diverged after a full staged cycle")
    if json.dumps(dict(manager.inventory().to_dict()), sort_keys=True) != json.dumps(
        dict(_manager(NODE_A).inventory().to_dict()), sort_keys=True
    ):
        return fail(name, "inventory diverged after the rolled-back cycle")
    return ok(name, "state handed out is a copy; internal truth invariant across the cycle")


def case_41_live_migration_transactional_isolation() -> Result:
    """PR #31 Architect review blocker 2: the live PREPARED->CANARY
    migration application must be transactionally isolated.

    The registry accepts ARBITRARY migration callables, and
    ``begin()``'s rehearsal proves nothing about the later LIVE call
    (a callable is free to behave differently once it is handed live
    state).  The manager therefore never hands live state to a
    migration: the complete chain runs on isolated deep copies and
    live schema state / version metadata swap only after the entire
    chain succeeds.  Every sub-case here uses a callable that is
    HONEST during the ``begin()`` rehearsal and HOSTILE during the
    live transition -- the exact hazard class the review flagged
    (a mutating migration that raises or returns invalid data must
    never leave live state partially modified before version
    metadata advances)."""
    name = "case_41_live_migration_transactional_isolation"
    problems: List[str] = []
    template = _template()

    def _flaky(hostile):
        """A migration callable that behaves honestly on the first
        call (the begin() rehearsal) and runs ``hostile`` on every
        later call (the live application)."""
        calls = {"count": 0}

        def forward(state: Any) -> Any:
            calls["count"] += 1
            if calls["count"] > 1:
                return hostile(state)
            return dict(state, label="node")  # honest rehearsal

        return forward

    def _mutate_and_raise(state: Any) -> Any:
        state["injected"] = True  # mutate the RECEIVED mapping in place
        raise RuntimeError("impure migration explodes on live state")

    def _mutate_and_return_invalid(state: Any) -> Any:
        state["injected"] = True  # mutate the RECEIVED mapping in place
        return ["not", "a", "mapping"]

    def _armed_registry(forward: Any) -> MigrationRegistry:
        registry = MigrationRegistry()
        registry.register_step(
            "node.config", "1.1", "1.2", reversible=True, breaking=False,
            forward=forward,
            backward=lambda s: {k: v for k, v in s.items() if k != "label"},
        )
        return registry

    def _armed_manager(registry: MigrationRegistry) -> UpgradeManager:
        manager = _manager(NODE_A, registry=registry)
        manager.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW)
        manager.begin(_NOW)  # rehearsal: the callable is still honest
        if manager.stage != UpgradeStage.PREPARED:
            raise AssertionError("fixture sanity: begin() must reach PREPARED")
        return manager

    # (1) mutate-and-RAISE during the live transition: live state
    # byte-identical, version truth unmoved, stage unchanged.
    manager = _armed_manager(_armed_registry(_flaky(_mutate_and_raise)))
    live_before = json.dumps(manager.schema_state("node.config"), sort_keys=True)
    inventory_before = manager.inventory().to_dict()
    try:
        manager.advance(_NOW, _healthy_observations(NODE_A))
        problems.append("mutating+raising live migration must abort the transition")
    except RuntimeError:
        pass  # the callable's own error surfaces; nothing may be applied
    if json.dumps(manager.schema_state("node.config"), sort_keys=True) != live_before:
        problems.append("live schema state corrupted by mutate-and-raise")
    if manager.inventory().to_dict() != inventory_before:
        problems.append("version truth moved despite the aborted transition")
    if manager.stage != UpgradeStage.PREPARED:
        problems.append("stage advanced despite the aborted transition")

    # (2) mutate-and-return-INVALID-DATA during the live transition:
    # same isolation (MIGRATION_INVALID_STEP, nothing applied).
    manager2 = _armed_manager(_armed_registry(_flaky(_mutate_and_return_invalid)))
    live2_before = json.dumps(manager2.schema_state("node.config"), sort_keys=True)
    inventory2_before = manager2.inventory().to_dict()
    try:
        manager2.advance(_NOW, _healthy_observations(NODE_A))
        problems.append("invalid-returning live migration must abort the transition")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.MIGRATION_INVALID_STEP:
            problems.append("expected MIGRATION_INVALID_STEP, got %r" % error.reason)
    if json.dumps(manager2.schema_state("node.config"), sort_keys=True) != live2_before:
        problems.append("live schema state corrupted by mutate-and-invalid-return")
    if manager2.inventory().to_dict() != inventory2_before:
        problems.append("version truth moved despite the invalid return")
    if manager2.stage != UpgradeStage.PREPARED:
        problems.append("stage advanced despite the invalid return")

    # (3) MULTI-ARTIFACT partial application: the first artifact
    # migrates honestly during the live transition, the second is
    # hostile -- NEITHER may be applied (no partial live
    # modification before version metadata advances).
    calls_metrics = {"count": 0}

    def flaky_metrics(state: Any) -> Any:
        calls_metrics["count"] += 1
        if calls_metrics["count"] > 1:
            return _mutate_and_raise(state)
        return dict(state, precision=2)  # honest rehearsal

    two_artifacts = MigrationRegistry()
    two_artifacts.register_step(
        "node.config", "1.1", "1.2", reversible=True, breaking=False,
        forward=lambda s: dict(s, label="node"),
        backward=lambda s: {k: v for k, v in s.items() if k != "label"},
    )
    two_artifacts.register_step(
        "node.metrics", "1.0", "1.1", reversible=True, breaking=False,
        forward=flaky_metrics,
        backward=lambda s: {k: v for k, v in s.items() if k != "precision"},
    )
    two_template = RolloutTemplate(
        to_version=SoftwareVersion.parse("2.1.0"),
        target_protocol_profile=ProtocolProfile(major=1, max_minor=1),
        target_schema_versions=(("node.config", "1.2"), ("node.metrics", "1.1")),
        minimum_version_floor=SoftwareVersion.parse("2.0.0"),
        canary_gate=HealthGateSpec(
            "canary-adapter-health", "adapter-health", ADAPTER_REF, "health-state", 1,
        ),
        rollout_gate=HealthGateSpec(
            "rollout-path-loss", "path", UPLINK_REF, "loss-bp", 500,
        ),
        final_gate=HealthGateSpec(
            "final-adapter-failures", "adapter-health", ADAPTER_REF,
            "consecutive-failures", 0,
        ),
    )
    manager3 = _manager(
        NODE_A, registry=two_artifacts,
        schemas={"node.config": "1.1", "node.metrics": "1.0"},
        state={"node.config": dict(_STATE_1_1), "node.metrics": {"window": 10}},
    )
    manager3.submit_plan(
        two_template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW,
    )
    manager3.begin(_NOW)  # both rehearsals honest
    config_before = json.dumps(manager3.schema_state("node.config"), sort_keys=True)
    metrics_before = json.dumps(manager3.schema_state("node.metrics"), sort_keys=True)
    inventory3_before = manager3.inventory().to_dict()
    try:
        manager3.advance(_NOW, _healthy_observations(NODE_A))
        problems.append("the hostile second artifact must abort the transition")
    except RuntimeError:
        pass
    if json.dumps(manager3.schema_state("node.config"), sort_keys=True) != config_before:
        problems.append("PARTIAL APPLICATION: the honest first artifact went live")
    if json.dumps(manager3.schema_state("node.metrics"), sort_keys=True) != metrics_before:
        problems.append("live metrics state corrupted by the hostile artifact")
    if manager3.inventory().to_dict() != inventory3_before:
        problems.append("version truth moved despite the aborted multi-artifact chain")
    if manager3.stage != UpgradeStage.PREPARED:
        problems.append("stage advanced despite the aborted multi-artifact chain")

    # (4) ROLLBACK isolation: a backward migration that mutates and
    # raises during the reverse proof-walk must never corrupt the
    # live (canary-live) state; the rollback simply fails with the
    # stage and live truth unchanged.
    rollback_hostile = MigrationRegistry()
    rollback_hostile.register_step(
        "node.config", "1.1", "1.2", reversible=True, breaking=False,
        forward=lambda s: dict(s, label="node"),  # honest, always
        backward=_mutate_and_raise,  # hostile at rollback time
    )
    manager4 = _manager(NODE_A, registry=rollback_hostile)
    manager4.submit_plan(template.plan_for(NODE_A, SoftwareVersion.parse("2.0.0")), _NOW)
    manager4.begin(_NOW)
    manager4.advance(_NOW, _healthy_observations(NODE_A))  # -> CANARY (live)
    canary_state = json.dumps(manager4.schema_state("node.config"), sort_keys=True)
    canary_inventory = manager4.inventory().to_dict()
    try:
        manager4.rollback(_LATER)
        problems.append("a hostile backward migration must abort the rollback")
    except RuntimeError:
        pass
    if json.dumps(manager4.schema_state("node.config"), sort_keys=True) != canary_state:
        problems.append("live canary state corrupted by the hostile backward walk")
    if manager4.inventory().to_dict() != canary_inventory:
        problems.append("version truth moved despite the aborted rollback")
    if manager4.stage != UpgradeStage.CANARY:
        problems.append("stage changed despite the aborted rollback")

    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "live migration application is transactionally isolated: raising, "
        "invalid-returning, and partially-applying chains leave live state "
        "byte-identical; the rollback proof-walk is isolated too",
    )


# --------------------------------------------------------------------------
# The battery registry
# --------------------------------------------------------------------------

CASES = (
    case_01_version_kinds_structurally_separated,
    case_02_software_version_canonical_grammar,
    case_03_protocol_profile_real_work003_artifact,
    case_04_common_profile_additive_floor,
    case_05_incompatible_majors_fail_closed,
    case_06_forged_selection_not_constructible,
    case_07_mixed_version_capability_interop_delegated,
    case_08_negotiation_is_delegation_not_reimplementation,
    case_09_inventory_complete_content_tamper_matrix,
    case_10_migration_step_discipline,
    case_11_migration_reversible_round_trip,
    case_12_migration_chain_multi_step,
    case_13_unknown_path_fails_closed,
    case_14_non_reversible_reverse_fails_closed,
    case_15_migration_determinism,
    case_16_plan_invariants,
    case_17_submit_validation_matrix,
    case_18_staged_ladder_happy_path,
    case_19_gate_requires_real_self_telemetry,
    case_20_stale_evidence_fails_closed,
    case_21_gate_threshold_and_latest_evidence,
    case_22_commit_requires_final_gate,
    case_23_rollback_restores_state,
    case_24_post_commit_window_closed,
    case_25_floor_ratchet_blocks_below_floor_plans,
    case_26_rolling_upgrade_population,
    case_27_mixed_version_coexistence_mid_rollout,
    case_28_mixed_version_envelope_interop,
    case_29_canary_failure_halts_rollout,
    case_30_per_node_failure_rolls_back_all,
    case_31_commit_failure_leaves_committed_windows_closed,
    case_32_population_downgrade_protection,
    case_33_authority_boundaries_imports,
    case_34_no_vendor_symbols,
    case_35_determinism_across_hash_seeds,
    case_36_frozen_spec_intact,
    case_37_py_compile_clean,
    case_38_ci_wiring,
    case_39_serialization_round_trips,
    case_40_schema_state_isolation,
    case_41_live_migration_transactional_isolation,
)


def main() -> int:
    print("ADCOS upgrade / rollback / compatibility self-test (WORK-029)")
    print("=" * 72)
    failures = 0
    for case in CASES:
        try:
            case_name, passed, detail = case()
        except Exception as exc:  # noqa: BLE001
            case_name, passed, detail = (
                case.__name__, False,
                "case raised %s: %s" % (type(exc).__name__, exc),
            )
        if not passed:
            failures += 1
        print("[%s] %-56s %s" % ("ok  " if passed else "FAIL", case_name, detail))
    print("-" * 72)
    if failures:
        print("Result: FAIL (%d/%d cases)" % (len(CASES) - failures, len(CASES)))
        return 1
    print("Result: PASS (%d/%d cases)" % (len(CASES), len(CASES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
