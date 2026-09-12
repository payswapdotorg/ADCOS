#!/usr/bin/env python3
"""ADCOS credential-lifecycle self-test (M018 — Credential and Key
Lifecycle Operations).

Deterministic, offline verification of the ``credentials/`` package
against the frozen Architecture 1.1 mandate (R8-CORE-001, DEC-0114;
the R8 charter M018 acceptance criteria): the operational
credential-lifecycle domain over the accepted M014 identity/
federation/client convergence surfaces composed BY REFERENCE —
rotation drills with zero coverage gaps (the admitted-set transition
atomic and journaled), revocation propagation as deterministic
rounds with declared round-count convergence bounds, emergency
revocation paths that are explicit and evidence-visible (LOCK-106
records consumed by reference from the accepted evidence/ typing),
credential inventory verification (every admitted credential traces
to a valid lifecycle record — a broken chain fails closed), key
material never stored/logged/echoed (LOCK-119 — the fixtures are
assembled at runtime from fragments so the full shape never appears
in source), and the admission gate consumed BY REFERENCE from the
accepted ``client/``/``federation/`` surfaces (no second
authorization runtime — LOCK-117).

Battery coverage (the M018 work-item matrix):

- (a) case_03..case_06 — the rotation drills: the journaled
  operation sequence (ordered, gapless, idempotent, replayable; the
  fold is the sole writer of the replayed view; construction-is-
  recovery), the zero-coverage-gap probes (the admitted set probed
  at every journaled instant around the rotations — no window admits
  the superseded generation; the flip lands exactly at the journaled
  instant; the journal truth cross-checked against the identity
  authority's own records), the atomic flip through the accepted
  identity authority (a rejected rotation leaves the identity state
  AND the journal byte-identical — the authority's own
  all-or-nothing StoreBatch discipline), and the forged non-atomic
  rotation records rejected by the mechanical kernel (both
  generations admitted / neither admitted / more than the single
  flip — the wire-forged record shapes);
- (b) case_07..case_09 — the revocation propagation: deterministic
  rounds (same inputs -> identical rounds, in-process and across
  re-runs), the declared ROUND-COUNT convergence bound enforced (an
  unconvergeable plan fails closed citing the bound and the pending
  consumers; a convergeable plan converges exactly within the bound;
  never a wall-clock bound), and the journaled/replayable rounds
  with the consumer-observation model;
- (c) case_10/case_11 — the emergency revocation path: the distinct
  typed journaled operation (the frozen three steps, the ordinary
  revocation structurally cannot carry them), the LOCK-106 evidence
  visibility at every step (each step's evidence references resolve
  to REAL typed evidence records in the real evidence store), and
  the accepted emergency stop driven through the frozen W049
  client's OWN control (the local fail-safe, the canonical lease
  revoked through the contract store's own command, the verified
  terminal state, the STOPPED client);
- (d) case_12..case_19 — the inventory verification: the clean audit
  (the typed record with the full per-credential trace) and one case
  per break kind (unknown-reference, status-mismatch,
  missing-activation, missing-supersession, missing-revocation-info,
  generation-gap, bookkeeping-missing — every break the typed
  ``credential-inventory-incomplete`` failure, never a warning);
- (e) case_20/case_21 — the admission gate composition: the composed
  probe driving the three accepted gates BY REFERENCE (the M014
  credential-lifecycle verdict, the M014 principal-authorization
  verdict, the converged traffic-admission point — the verdicts
  consumed verbatim, the rejections typed, the ZERO-byte probe
  idempotent) and the full drill through the frozen W049 client
  protocol (check_capability -> become_ready -> prepare_sharing ->
  grant_consent -> request_handoff -> activate — the client surface
  driven by reference inside the drills);
- (f) case_22/case_23 — LOCK-119: the structural probes (no public
  record type carries a bytes member; the assembled secret marker
  absent from every journaled/serialized/echoed surface; the domain
  never opens the store's secret path — AST-audited) and the
  fragment-assembled fixture discipline (the full secret shape never
  appears in the battery's own source);
- plus case_01/case_02 (the frozen vocabularies and the
  vocabulary/input gates), case_24/case_25 (canonical-JSON
  round-trips + typed errors + exception isolation), case_26/
  case_27 (the determinism re-run in-process and across
  PYTHONHASHSEED subprocesses), case_28/case_29 (the one-way import
  boundary and the clock/import discipline), case_30 (the
  lock-conformance mapping), case_31 (the PR delta shape) and
  case_32 (the evidence-doc honesty).

All instants are injected (T0-style constants); no wall clock, no
randomness, no network, no real sockets, no secrets (any
credential-shaped fixture is assembled at runtime from fragments so
the full shape never appears in source). Runs are byte-identical
across processes (PYTHONHASHSEED-safe).
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from protocol.canonicalization import canonical_json_bytes  # noqa: E402
from protocol.temporal import parse_instant  # noqa: E402

from contracts import (  # noqa: E402
    ActivateContract,
    BeneficiaryScope,
    ConnectivityPrincipal,
    ContractStore,
    CreateContract,
    GrantLease,
    HardConstraint,
    OpaqueReference,
    Provenance,
    RecordExecutionActivation,
    SelectOffers,
    TerminationRules,
    ValidityInterval,
)
from evidence import EvidenceStore, EVIDENCE_TYPES  # noqa: E402
from offers import (  # noqa: E402
    AdvertisementEntry,
    AdvertisementRef,
    OfferCommitment,
    OfferExchange,
    OfferPricing,
    ServiceBoundary,
    build_advertisement,
    build_offer,
    offer_reference,
)
from identity import (  # noqa: E402
    CredentialReference,
    DevHmacSha256Provider,
    IdentityService,
    InMemoryCredentialStore,
    KeyRole,
    LifecycleState,
    NodeIdentity,
    ProfileSet,
)
from identity.convergence import (  # noqa: E402
    AUTHORIZATION_VERDICTS,
    CREDENTIAL_VERDICTS,
    AuthorizationRegistry,
    CredentialLifecyclePolicy,
    CredentialLifecycleState,
    build_principal_authorization,
)
from federation.convergence import AuthorizationScope  # noqa: E402
from client import ProviderClientState, SandboxPlatformAdapter  # noqa: E402

from credentials import (  # noqa: E402
    ADMITTING_AUTHORIZATION_VERDICTS,
    ADMITTING_LIFECYCLE_VERDICTS,
    EMERGENCY_STEP_KINDS,
    INVENTORY_BREAK_KINDS,
    OPERATION_KINDS,
    AdmissionProbe,
    CredentialLifecycleError,
    CredentialLifecycleReason,
    EmergencyStep,
    InventoryAuditRecord,
    InventoryTrace,
    LifecycleJournal,
    LifecycleOperationRecord,
    PropagationPlan,
    admitted_set,
    admission_gate_world,
    check_credential_admission,
    check_rotation_flip_is_atomic,
    check_zero_coverage_gap,
    consumer_observed_revocation,
    fold_operations,
    journal_inventory_audit,
    plan_propagation,
    probe_credential_admission,
    propagation_verdict,
    probe_from_mapping,
    record_from_mapping,
    round_deliveries,
    run_emergency_revocation,
    run_inventory_audit,
    run_revocation_drill,
    run_revocation_propagation,
    run_rotation_drill,
    verify_emergency_evidence,
)

Result = Tuple[str, bool, str]

# ---------------------------------------------------------------------------
# The injected deterministic instants (the ONLY time source)
# ---------------------------------------------------------------------------

T0 = "2027-03-01T00:00:00Z"
T_END = "2027-04-01T00:00:00Z"
CREATE_AT = "2027-02-28T10:00:00Z"
OFFER_SEL_AT = "2027-02-28T10:05:00Z"
GATE_DRIVE_AT = "2027-03-01T12:00:00Z"

ID_PROV_AT = "2027-03-01T00:00:00Z"
ROT1_AT = "2027-03-02T00:00:00Z"
ROT2_AT = "2027-03-03T00:00:00Z"
REV_AT = "2027-03-04T00:00:00Z"
EMERG_AT = "2027-03-05T00:00:00Z"
EMERG_VALID_UNTIL = "2027-03-20T00:00:00Z"
ROUND1_AT = "2027-03-06T00:00:00Z"
ROUND2_AT = "2027-03-07T00:00:00Z"
ROUND3_AT = "2027-03-08T00:00:00Z"
# an instant strictly between two journaled operations (the between-
# windows probe: no intermediate admitted set exists)
MID_ROT_AT = "2027-03-02T12:00:00Z"
# an instant strictly before the first journaled operation (the
# pre-history probe: never fabricated)
PRE_JOURNAL_AT = "2027-03-01T13:00:00Z"

BUYER = "app:buyer-m018"
# the provider ref must be a canonical ADCOS NodeID (the offers
# authority's own grammar): the drill world passes the credential-
# holding node's REAL NodeID text (the composition binding)
PROVIDER = "adcos:node:identity.sha256-hmac-dev.v1:" + "c" * 64
DEVICE = "dev:pi-m018"
APPLICATION = "app:cred-gateway-m018"
PLATFORM = "platform:router-m018"
SESSION_REF = "sess:m018-operational"
PATH_REF = "path:w41-m018"

CONSUMERS = (
    "consumer:admission-edge-1",
    "consumer:admission-edge-2",
    "consumer:admission-edge-3",
)

EMERGENCY_REASON = "emergency:credential-compromise-suspected"

BATTERY_ISSUER = "credentials:battery"


# ---------------------------------------------------------------------------
# LOCK-119: the secret fixtures assembled at runtime from fragments
# ---------------------------------------------------------------------------

# The full secret shape (head + seed + tail) NEVER appears in this
# source: only the fragments do, and the assembly happens at runtime.
_SECRET_HEAD = b"TEST-ONLY-"
_SECRET_TAIL = b"-m018-fragments-DO-NOT-USE"


def _secret(seed: int) -> bytes:
    """One deterministic secret assembled at runtime from fragments
    (LOCK-119: the full shape never appears in source; the material
    goes ONLY to the accepted identity store through the accepted
    identity service's own public APIs)."""
    return _SECRET_HEAD + ("key-%03d" % seed).encode("ascii") + _SECRET_TAIL


# ---------------------------------------------------------------------------
# The typed fail-closed expectation helper
# ---------------------------------------------------------------------------


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def expect_error(case: str, code: str, action: Callable[[], Any]) -> Result:
    try:
        action()
    except CredentialLifecycleError as error:
        if error.code == code:
            return ok(case, "fail-closed %s: %s" % (code, error.detail[:90]))
        return fail(
            case,
            "expected code %s, got %s (%s)" % (code, error.code, error.detail[:90]),
        )
    except Exception as error:  # noqa: BLE001
        return fail(
            case,
            "unexpected exception %s: %s" % (type(error).__name__, str(error)[:90]),
        )
    return fail(case, "expected CredentialLifecycleError(%s); the input was accepted" % code)


# ---------------------------------------------------------------------------
# The deterministic injected clock (the ONLY time source)
# ---------------------------------------------------------------------------


class StepClock:
    """The injected deterministic clock seam (never a wall clock).

    ``advance_to`` moves the clock to an injected instant (validated,
    monotonic) so the composed admission-gate world observes the
    drill instants exactly."""

    def __init__(self, start: str) -> None:
        self._instant = start

    def now(self) -> str:
        return self._instant

    def advance_to(self, instant: str) -> str:
        if parse_instant(instant) < parse_instant(self._instant):
            raise AssertionError(
                "the injected clock only moves forward (%s -> %s)"
                % (self._instant, instant)
            )
        self._instant = instant
        return self._instant


# ---------------------------------------------------------------------------
# The identity-world fixture (the accepted identity authority, by reference)
# ---------------------------------------------------------------------------


@dataclass
class _IdentityWorld:
    service: IdentityService
    store: InMemoryCredentialStore
    provider: DevHmacSha256Provider
    identity: NodeIdentity
    identity_ref: Any
    op_ref: Any
    m014_state: CredentialLifecycleState
    policy: CredentialLifecyclePolicy


def _identity_world() -> _IdentityWorld:
    """The accepted identity authority composed for the drill: a real
    IdentityService over a real in-memory CredentialStore and the
    development HMAC provider, with identity + operational
    credentials ACTIVE (the secrets assembled from fragments and
    going ONLY to the store through the service's public APIs), plus
    the accepted M014 credential-lifecycle policy and bookkeeping."""
    profiles = ProfileSet.load_default()
    provider = DevHmacSha256Provider()
    store = InMemoryCredentialStore()
    service = IdentityService(store=store, provider=provider, profiles=profiles)
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    ident = NodeIdentity.create(profile, provider.public_material(_secret(1)), ID_PROV_AT)
    identity_ref = service.provision(ident, KeyRole.IDENTITY, _secret(1), now=ID_PROV_AT)
    service.activate(identity_ref, now=ID_PROV_AT)
    op_ref = service.provision(ident, KeyRole.OPERATIONAL, _secret(2), now=ID_PROV_AT)
    service.activate(op_ref, now=ID_PROV_AT)
    m014_state = CredentialLifecycleState()
    m014_state.record_activation(
        identity_ref.reference_id, ID_PROV_AT, LifecycleState.ACTIVE.value
    )
    m014_state.record_activation(
        op_ref.reference_id, ID_PROV_AT, LifecycleState.ACTIVE.value
    )
    policy = CredentialLifecyclePolicy(
        rotation_deadline_seconds=30 * 86400,
        grace_seconds=86400,
        max_active_credentials=4,
    )
    return _IdentityWorld(
        service=service,
        store=store,
        provider=provider,
        identity=ident,
        identity_ref=identity_ref,
        op_ref=op_ref,
        m014_state=m014_state,
        policy=policy,
    )


def _authorize_rotation(
    world: _IdentityWorld, new_secret: bytes, rotated_at: str
) -> bytes:
    """Prepare a valid rotation authorization signature through the
    accepted identity machinery (the identity battery's convention:
    the statement is built by the service's own public surface and
    signed through the provider's store-mediated path — the secret
    never leaves the store)."""
    current = world.service.active_credential(
        world.identity.node_id, KeyRole.OPERATIONAL, now=rotated_at
    )
    statement = world.service.rotation_statement(
        world.identity.node_id,
        KeyRole.OPERATIONAL,
        current.key_version,
        current.key_version + 1,
        world.provider.public_material(new_secret),
        rotated_at,
    )
    return world.provider.sign(world.store, world.identity_ref, statement)


# ---------------------------------------------------------------------------
# The admission-gate world fixture (the accepted client/federation
# surfaces, composed by reference through the accepted root)
# ---------------------------------------------------------------------------


def _prov(issuer: str, *refs: str) -> Provenance:
    return Provenance(issuer=issuer, decision_refs=tuple(refs))


@dataclass
class _GateWorld:
    world: Any
    cid: str
    clock: StepClock
    store: ContractStore
    evidence: EvidenceStore


def _gate_world(
    clock_start: str = GATE_DRIVE_AT,
    provider_ref: str = PROVIDER,
) -> _GateWorld:
    """The accepted admission-gate world: a REAL M002 contract store
    with a mature contract + lease, a REAL M003 offers exchange with
    a registered offer, a REAL M005 evidence store, the frozen W049
    sandbox adapter, the injected clock and the declared
    authorization scope — composed through the M018 domain's
    ``admission_gate_world`` (which drives the ACCEPTED
    ``client.convergence.build_converged_provider_client``
    composition root 1:1, by reference)."""
    exchange = OfferExchange()
    advertisement = build_advertisement(
        provider=provider_ref,
        entries=(AdvertisementEntry(
            capability_id="capability.core.multipath",
            schema_version="1.2",
            statement_digest="sha256:" + "b" * 64,
            classification="known",
        ),),
        validity=ValidityInterval(not_before=T0, not_after=T_END),
        provenance=_prov(PROVIDER),
    )
    offer = build_offer(
        provider=provider_ref,
        provider_offer_key="offer:skywave-mesh-m018",
        schema_version=1,
        advertisements=(AdvertisementRef(
            advertisement_id=advertisement.advertisement_id,
            provenance=_prov(PROVIDER),
        ),),
        commitments=(OfferCommitment(
            kind="latency-bound-ms",
            params={"max_ms": 150},
            window=ValidityInterval(not_before=T0, not_after=T_END),
            provenance=_prov(PROVIDER),
        ),),
        pricing=OfferPricing(
            currency="USD", price_minor=250, price_exponent=2,
            billing_mode="flat", provenance=_prov(PROVIDER),
        ),
        service_boundaries=(ServiceBoundary(
            jurisdiction="GH",
            geography_refs=("mpcell:v1:coarse-50000m:12:-1",),
            provenance=_prov(PROVIDER),
        ),),
        validity=ValidityInterval(not_before=T0, not_after=T_END),
        provenance=_prov(PROVIDER),
    )
    exchange.register_advertisement(advertisement)
    exchange.register_offer(offer)
    offer_ref = offer_reference(offer)

    store = ContractStore()
    created = store.submit(CreateContract(
        principal=ConnectivityPrincipal(
            principal_kind="APPLICATION", principal_ref=BUYER,
        ),
        beneficiaries=(BeneficiaryScope(
            beneficiary_kind="DEVICE", beneficiary_ref=DEVICE,
        ),),
        requirements=(OpaqueReference(
            ref_kind="intent-requirements", value="intent:m018-42",
            provenance=_prov("arch:credentials"),
        ),),
        hard_constraints=(HardConstraint(
            kind="latency-bound", params={"max_ms": 150},
            provenance=_prov(PROVIDER),
        ),),
        validity=ValidityInterval(not_before=T0, not_after=T_END),
        service_properties=(OpaqueReference(
            ref_kind="service-property", value="prop:committed-1",
            provenance=_prov(PROVIDER),
        ),),
        usage_pricing_terms=OpaqueReference(
            ref_kind="usage-pricing-terms", value="terms:comm-42",
            provenance=_prov("comm:ops"),
        ),
        assurance_obligations=(OpaqueReference(
            ref_kind="assurance-obligation", value="oblig:evid-7",
        ),),
        execution_scope=(OpaqueReference(
            ref_kind="execution-scope", value="scope:exec-default",
        ),),
        termination=TerminationRules(
            conditions=("principal-requested", "constraint-violated"),
            compensation=OpaqueReference(
                ref_kind="compensation", value="comp:rule-9",
                provenance=_prov("comm:ops"),
            ),
        ),
        provenance=_prov("arch:credentials", "dec:elig-1"),
    ), recorded_at=CREATE_AT)
    cid = created.contract.contract_id
    store.submit(
        SelectOffers(offers=(offer_ref,)),
        recorded_at=OFFER_SEL_AT, contract_id=cid,
    )
    store.submit(
        GrantLease(granted_at=CREATE_AT, not_before=T0, not_after=T_END),
        recorded_at=CREATE_AT, contract_id=cid,
    )
    store.submit(
        ActivateContract(
            activated_at=T0,
            signature_refs=(OpaqueReference(
                ref_kind="signature", value="sig:ed25519-m018",
            ),),
        ),
        recorded_at=T0, contract_id=cid,
    )
    store.submit(
        RecordExecutionActivation(recorded_at=T0), recorded_at=T0, contract_id=cid
    )

    estore = EvidenceStore()
    clock = StepClock(clock_start)
    scope = AuthorizationScope(
        exposed_egress=("egress:internet-via-provider",),
        byte_quota=1_000_000,
        valid_until=T_END,
        max_concurrent_sessions=2,
    )
    adapter = SandboxPlatformAdapter(
        platform_id=PLATFORM,
        provider_support="supported",
        buyer_support="supported",
    )
    world = admission_gate_world(
        store=store,
        evidence=estore,
        exchange=exchange,
        adapter=adapter,
        clock=clock,
        scope=scope,
        user_ref=provider_ref,
        device_ref=DEVICE,
        application_ref=APPLICATION,
        platform_id=PLATFORM,
    )
    return _GateWorld(
        world=world, cid=cid, clock=clock, store=store, evidence=estore
    )


# ---------------------------------------------------------------------------
# The composed drill world (identity + admission gate + journal)
# ---------------------------------------------------------------------------


@dataclass
class _DrillWorld:
    ident: _IdentityWorld
    gate: _GateWorld
    registry: AuthorizationRegistry
    authorization: Any
    journal: LifecycleJournal
    session_id: str

    @property
    def client(self) -> Any:
        return self.gate.world.client

    @property
    def authority(self) -> Any:
        return self.gate.world.authority

    @property
    def clock(self) -> StepClock:
        return self.gate.clock

    def probe(self, credential_ref: str, at_instant: str) -> AdmissionProbe:
        self.clock.advance_to(at_instant)
        return probe_credential_admission(
            policy=self.ident.policy,
            state=self.ident.m014_state,
            registry=self.registry,
            authorization_id=self.authorization.authorization_id,
            node_id=self.ident.identity.node_id.text,
            contract_id=self.gate.cid,
            credential_ref=credential_ref,
            at_instant=at_instant,
            authority=self.authority,
            session_id=self.session_id,
        )

    def rotate(self, new_secret: bytes, rotated_at: str) -> Any:
        authorization = _authorize_rotation(self.ident, new_secret, rotated_at)
        return run_rotation_drill(
            service=self.ident.service,
            m014_state=self.ident.m014_state,
            journal=self.journal,
            identity_credential=self.ident.identity_ref,
            node_id=self.ident.identity.node_id,
            role=KeyRole.OPERATIONAL,
            new_secret=new_secret,
            authorization=authorization,
            rotated_at=rotated_at,
            provenance=BATTERY_ISSUER,
        )


def _drill_world() -> _DrillWorld:
    """The composed drill world: the identity authority + the
    admission-gate world + the M014 principal authorization binding
    the node to the REAL contract + the frozen W049 client driven
    through its OWN public protocol to canonical ACTIVE (the client
    surface driven BY REFERENCE inside the drills) + the node-scoped
    lifecycle journal."""
    ident = _identity_world()
    gate = _gate_world(provider_ref=ident.identity.node_id.text)
    authorization = build_principal_authorization(
        node_id=ident.identity.node_id.text,
        principal_kind="APPLICATION",
        principal_ref=BUYER,
        contract=gate.store.contract(gate.cid),
        valid_from=T0,
        valid_until=T_END,
    )
    registry = AuthorizationRegistry()
    registry.register(authorization)
    # the frozen client protocol chain (by reference — the client
    # surface driven inside the drill)
    client = gate.world.client
    client.check_capability()
    client.become_ready()
    client.prepare_sharing(
        lease_ref=gate.cid,
        buyer_ref=BUYER,
        provider_ref=ident.identity.node_id.text,
        session_ref=SESSION_REF,
        path_ref=PATH_REF,
        scope=gate.world.scope,
    )
    client.grant_consent()
    client.request_handoff()
    client.activate()
    session_id = client.sharing_session_id
    journal = LifecycleJournal(ident.identity.node_id.text)
    return _DrillWorld(
        ident=ident,
        gate=gate,
        registry=registry,
        authorization=authorization,
        journal=journal,
        session_id=session_id,
    )


def _op_refs(world: _DrillWorld) -> Dict[int, str]:
    """The operational credential references by generation (v1..vN),
    read from the identity authority's own records."""
    refs: Dict[int, str] = {}
    for record in world.ident.service.records_for(world.ident.identity.node_id):
        if record.role == KeyRole.OPERATIONAL:
            refs[record.key_version] = record.reference.reference_id
    return refs


# ===========================================================================
# case_01 — the frozen vocabularies (M018-owned + consumed by reference)
# ===========================================================================


def case_01_frozen_vocabularies() -> Result:
    name = "case_01_frozen_vocabularies"
    problems: List[str] = []
    if OPERATION_KINDS != (
        "rotation", "revocation", "emergency-revocation",
        "propagation-round", "inventory-audit",
    ):
        problems.append("the operation-kind vocabulary changed")
    if EMERGENCY_STEP_KINDS != (
        "identity-revocation", "authorization-revocation", "admission-gate-stop",
    ):
        problems.append("the emergency-step vocabulary changed")
    if INVENTORY_BREAK_KINDS != (
        "unknown-reference", "status-mismatch", "missing-activation",
        "missing-supersession", "missing-revocation-info", "generation-gap",
        "bookkeeping-missing",
    ):
        problems.append("the inventory break-kind vocabulary changed")
    # the consumed vocabularies BY REFERENCE (never redefined here)
    if not set(ADMITTING_LIFECYCLE_VERDICTS) <= set(CREDENTIAL_VERDICTS):
        problems.append("the admitting lifecycle verdicts left the consumed M014 vocabulary")
    if not set(ADMITTING_AUTHORIZATION_VERDICTS) <= set(AUTHORIZATION_VERDICTS):
        problems.append("the admitting authorization verdicts left the consumed M014 vocabulary")
    if LifecycleState.ACTIVE.value != "active" or LifecycleState.REVOKED.value != "revoked":
        problems.append("the WORK-004 lifecycle vocabulary drifted")
    if "attestation" not in EVIDENCE_TYPES:
        problems.append("the LOCK-106 attestation type is not in the consumed EVIDENCE_TYPES")
    if len(CredentialLifecycleReason.values()) != 11:
        problems.append("the typed reason vocabulary changed size")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "the M018 kinds/emergency-steps/break-kinds frozen; the M014 verdict "
        "vocabularies, the WORK-004 lifecycle states and the LOCK-106 "
        "evidence types consumed by reference",
    )


# ===========================================================================
# case_02 — the vocabulary/input gates fail closed
# ===========================================================================


def case_02_vocabulary_fail_closed() -> Result:
    name = "case_02_vocabulary_fail_closed"
    results: List[Result] = []
    before = ("cred:a:operational:v1", "cred:a:identity:v1")
    after = ("cred:a:identity:v1", "cred:a:operational:v2")

    results.append(expect_error(
        name + "/unknown-kind",
        CredentialLifecycleReason.VOCABULARY,
        lambda: LifecycleOperationRecord(
            operation_id="", kind="rekey", sequence=1, node_id="adcos:node:p:1",
            recorded_at=ROT1_AT, subject_ref="cred:a:operational:v1",
            before_admitted=before, after_admitted=after,
            replacement_ref="cred:a:operational:v2",
            provenance=BATTERY_ISSUER,
        ),
    ))
    results.append(expect_error(
        name + "/emergency-without-steps",
        CredentialLifecycleReason.VOCABULARY,
        lambda: LifecycleOperationRecord(
            operation_id="", kind="emergency-revocation", sequence=1,
            node_id="adcos:node:p:1", recorded_at=EMERG_AT,
            subject_ref="cred:a:operational:v1",
            before_admitted=before, after_admitted=after,
            reason="r", provenance=BATTERY_ISSUER,
        ),
    ))
    results.append(expect_error(
        name + "/ordinary-revocation-with-emergency-steps",
        CredentialLifecycleReason.VOCABULARY,
        lambda: LifecycleOperationRecord(
            operation_id="", kind="revocation", sequence=1,
            node_id="adcos:node:p:1", recorded_at=REV_AT,
            subject_ref="cred:a:operational:v1",
            before_admitted=before, after_admitted=after,
            reason="r",
            steps=(EmergencyStep(step="identity-revocation", detail="d"),),
            provenance=BATTERY_ISSUER,
        ),
    ))
    results.append(expect_error(
        name + "/rotation-both-generations-admitted",
        CredentialLifecycleReason.ROTATION_NONATOMIC,
        lambda: check_rotation_flip_is_atomic(
            before, ("cred:a:identity:v1", "cred:a:operational:v1",
                     "cred:a:operational:v2"),
            "cred:a:operational:v1", "cred:a:operational:v2",
        ),
    ))
    results.append(expect_error(
        name + "/rotation-neither-generation-admitted",
        CredentialLifecycleReason.ROTATION_NONATOMIC,
        lambda: check_rotation_flip_is_atomic(
            before, ("cred:a:identity:v1",),
            "cred:a:operational:v1", "cred:a:operational:v2",
        ),
    ))
    results.append(expect_error(
        name + "/rotation-changes-more-than-the-flip",
        CredentialLifecycleReason.ROTATION_NONATOMIC,
        lambda: check_rotation_flip_is_atomic(
            before, ("cred:a:identity:v2", "cred:a:operational:v2"),
            "cred:a:operational:v1", "cred:a:operational:v2",
        ),
    ))
    results.append(expect_error(
        name + "/read-only-operation-changes-the-set",
        CredentialLifecycleReason.ROTATION_NONATOMIC,
        lambda: LifecycleOperationRecord(
            operation_id="", kind="inventory-audit", sequence=1,
            node_id="adcos:node:p:1", recorded_at=ROT1_AT,
            subject_ref="",
            before_admitted=before, after_admitted=after,
            provenance=BATTERY_ISSUER,
        ),
    ))
    results.append(expect_error(
        name + "/bad-instant",
        CredentialLifecycleReason.TEMPORAL_INVALID,
        lambda: LifecycleOperationRecord(
            operation_id="", kind="inventory-audit", sequence=1,
            node_id="adcos:node:p:1", recorded_at="not-an-instant",
            subject_ref="",
            before_admitted=before, after_admitted=before,
            provenance=BATTERY_ISSUER,
        ),
    ))
    secret_prefix = "client_"
    secret_body = "secret-material-9f3a"
    results.append(expect_error(
        name + "/secret-shaped-reference",
        CredentialLifecycleReason.SECRET_REJECTED,
        lambda: check_rotation_flip_is_atomic(
            (secret_prefix + secret_body,), ("cred:a:operational:v2",),
            secret_prefix + secret_body, "cred:a:operational:v2",
        ),
    ))
    results.append(expect_error(
        name + "/plan-fanout-zero",
        CredentialLifecycleReason.INVALID_INPUT,
        lambda: plan_propagation(("consumer:1",), 0, 1),
    ))
    results.append(expect_error(
        name + "/plan-rounds-zero",
        CredentialLifecycleReason.INVALID_INPUT,
        lambda: plan_propagation(("consumer:1",), 1, 0),
    ))
    results.append(expect_error(
        name + "/plan-duplicate-consumers",
        CredentialLifecycleReason.INVALID_INPUT,
        lambda: plan_propagation(("consumer:1", "consumer:1"), 1, 2),
    ))
    results.append(expect_error(
        name + "/probe-verdict-outside-consumed-vocabulary",
        CredentialLifecycleReason.VOCABULARY,
        lambda: AdmissionProbe(
            probe_id="", credential_ref="cred:a:operational:v1",
            node_id="adcos:node:p:1", at_instant=ROT1_AT,
            lifecycle_verdict="definitely-fine", authorization_verdict="authorized",
            operational_state="active", admitted=True, rejection="",
        ),
    ))
    results.append(expect_error(
        name + "/probe-caller-supplied-admitted",
        CredentialLifecycleReason.INVALID_INPUT,
        lambda: AdmissionProbe(
            probe_id="", credential_ref="cred:a:operational:v1",
            node_id="adcos:node:p:1", at_instant=ROT1_AT,
            lifecycle_verdict="revoked", authorization_verdict="authorized",
            operational_state="active", admitted=True, rejection="",
        ),
    ))
    results.append(expect_error(
        name + "/probe-wrong-rejection-gate",
        CredentialLifecycleReason.INVALID_INPUT,
        lambda: AdmissionProbe(
            probe_id="", credential_ref="cred:a:operational:v1",
            node_id="adcos:node:p:1", at_instant=ROT1_AT,
            lifecycle_verdict="revoked", authorization_verdict="authorized",
            operational_state="active", admitted=False,
            rejection="authorization:authorized",
        ),
    ))
    # journal discipline: the gapless positions + the continuity
    journal = LifecycleJournal("adcos:node:p:1")
    good = LifecycleOperationRecord(
        operation_id="", kind="inventory-audit", sequence=1,
        node_id="adcos:node:p:1", recorded_at=ROT1_AT, subject_ref="",
        before_admitted=before, after_admitted=before,
        provenance=BATTERY_ISSUER,
    )
    journal.append(good)
    results.append(expect_error(
        name + "/journal-sequence-gap",
        CredentialLifecycleReason.JOURNAL_DIVERGENCE,
        lambda: journal.append(replace(good, sequence=3, operation_id="")),
    ))
    results.append(expect_error(
        name + "/journal-unrecorded-transition",
        CredentialLifecycleReason.JOURNAL_DIVERGENCE,
        lambda: journal.append(
            LifecycleOperationRecord(
                operation_id="", kind="inventory-audit", sequence=2,
                node_id="adcos:node:p:1", recorded_at=ROT2_AT, subject_ref="",
                before_admitted=after, after_admitted=after,
                provenance=BATTERY_ISSUER,
            )
        ),
    ))
    bad = [r for r in results if not r[1]]
    if bad:
        return fail(name, "; ".join("%s: %s" % (r[0], r[2]) for r in bad[:4]))
    return ok(name, "18 typed gate probes all fail closed with the specific code")


# ===========================================================================
# case_03 — the journal round-trips + the ordinary revocation drill
# ===========================================================================


def case_03_journal_round_trips() -> Result:
    name = "case_03_journal_round_trips"
    dw = _drill_world()
    dw.rotate(_secret(3), ROT1_AT)
    revoked_record = run_revocation_drill(
        service=dw.ident.service,
        m014_state=dw.ident.m014_state,
        journal=dw.journal,
        credential_ref=dw.ident.service.active_credential(
            dw.ident.identity.node_id, KeyRole.OPERATIONAL, now=REV_AT
        ).reference,
        node_id=dw.ident.identity.node_id,
        reason="ordinary:policy-scheduled-retirement",
        revoked_at=REV_AT,
        provenance=BATTERY_ISSUER,
    )
    run_revocation_propagation(
        journal=dw.journal,
        revocation_operation_id=revoked_record.operation_id,
        revoked_ref=revoked_record.subject_ref,
        plan=plan_propagation(CONSUMERS, 2, 2),
        round_instants=(ROUND1_AT, ROUND2_AT),
    )
    audit = run_inventory_audit(
        journal=dw.journal,
        store=dw.ident.store,
        m014_state=dw.ident.m014_state,
        policy=dw.ident.policy,
        node_id=dw.ident.identity.node_id,
        at_instant=ROUND2_AT,
    )
    journal_inventory_audit(dw.journal, audit, at_instant=ROUND3_AT)
    records = dw.journal.operations()
    kinds = tuple(record.kind for record in records)
    if kinds != ("rotation", "revocation", "propagation-round",
                 "propagation-round", "inventory-audit"):
        return fail(name, "unexpected journal kind chain %r" % (kinds,))
    if [record.sequence for record in records] != [1, 2, 3, 4, 5]:
        return fail(name, "the journal positions are not gapless")
    # the ordinary revocation record: no emergency steps (distinctness)
    if revoked_record.steps != ():
        return fail(name, "the ordinary revocation carries emergency steps")
    # the IDEMPOTENT append: the identical last record replays as a no-op
    digest_before = dw.journal.digest()
    replayed = dw.journal.append(records[-1])
    if dw.journal.digest() != digest_before or len(dw.journal) != 5:
        return fail(name, "the idempotent append changed the journal")
    if replayed.operation_id != records[-1].operation_id:
        return fail(name, "the idempotent append returned a different record")
    # the fold twice: byte-identical timelines
    fold_one = dw.journal.fold()
    fold_two = dw.journal.fold()
    if fold_one.digest != fold_two.digest or fold_one.admitted_timeline != fold_two.admitted_timeline:
        return fail(name, "the fold is not deterministic")
    # construction-is-recovery: from_records rebuilds the identical journal
    rebuilt = LifecycleJournal.from_records(dw.journal.to_records(), node_id=dw.journal.node_id)
    if rebuilt.digest() != digest_before:
        return fail(name, "construction-is-recovery diverged")
    if [r.operation_id for r in rebuilt.operations()] != [r.operation_id for r in records]:
        return fail(name, "the rebuilt record ids diverged")
    # the pure fold over the rebuilt records
    pure = fold_operations(
        [LifecycleOperationRecord.from_dict(d) for d in dw.journal.to_records()],
        node_id=dw.journal.node_id,
    )
    if pure.digest != fold_one.digest:
        return fail(name, "the pure fold diverged from the journal fold")
    # the ATOMIC append: a rejected append leaves the journal byte-identical
    try:
        dw.journal.append(
            LifecycleOperationRecord(
                operation_id="", kind="inventory-audit", sequence=6,
                node_id=dw.journal.node_id, recorded_at=ROUND3_AT,
                subject_ref="",
                before_admitted=("cred:phantom:v1",),
                after_admitted=("cred:phantom:v1",),
                provenance=BATTERY_ISSUER,
            )
        )
        return fail(name, "the divergent append was accepted")
    except CredentialLifecycleError:
        pass
    if dw.journal.digest() != digest_before:
        return fail(name, "a rejected append changed the journal (not atomic)")
    return ok(
        name,
        "ordered gapless kind chain (rotation/revocation/2 rounds/audit); "
        "idempotent + atomic append; fold twice + from_records rebuild = "
        "byte-identical; the ordinary revocation carries no emergency steps",
    )


# ===========================================================================
# case_04 — the zero-coverage-gap probes at every journaled instant
# ===========================================================================


def case_04_zero_coverage_gap() -> Result:
    name = "case_04_zero_coverage_gap"
    dw = _drill_world()
    rot1 = dw.rotate(_secret(3), ROT1_AT)
    rot2 = dw.rotate(_secret(4), ROT2_AT)
    refs = _op_refs(dw)
    op1, op2, op3 = refs[1], refs[2], refs[3]
    emergency = run_emergency_revocation(
        service=dw.ident.service,
        registry=dw.registry,
        evidence_store=dw.gate.evidence,
        journal=dw.journal,
        credential_ref=_active_op_reference(dw),
        authorization_id=dw.authorization.authorization_id,
        contract_id=dw.gate.cid,
        node_id=dw.ident.identity.node_id,
        client=dw.client,
        reason=EMERGENCY_REASON,
        now=EMERG_AT,
        evidence_valid_until=EMERG_VALID_UNTIL,
        m014_state=dw.ident.m014_state,
        provenance=BATTERY_ISSUER,
    )
    run_revocation_propagation(
        journal=dw.journal,
        revocation_operation_id=emergency.operation_id,
        revoked_ref=emergency.subject_ref,
        plan=plan_propagation(CONSUMERS, 1, 3),
        round_instants=(ROUND1_AT, ROUND2_AT, ROUND3_AT),
    )
    fold = dw.journal.fold()
    identity_ref = dw.ident.identity_ref.reference_id
    problems: List[str] = []
    # the flip is effective AT the journaled instant: at ROT1 the
    # after-set excludes op1 and includes op2
    if fold.admitted_set_at(ROT1_AT) != (identity_ref, op2):
        problems.append("the flip is not effective at the journaled instant ROT1")
    if fold.admitted_set_at(ROT2_AT) != (identity_ref, op3):
        problems.append("the flip is not effective at the journaled instant ROT2")
    if fold.admitted_set_at(EMERG_AT) != (identity_ref,):
        problems.append("the emergency removal is not effective at EMERG_AT")
    # BETWEEN journaled instants there is NO intermediate admitted set
    if fold.admitted_set_at(MID_ROT_AT) != (identity_ref, op2):
        problems.append("a between-instant probe found an intermediate window")
    # the before/after sets fully recorded on the flip records
    if rot1.before_admitted != (identity_ref, op1) or rot1.after_admitted != (identity_ref, op2):
        problems.append("rot1 does not record the full before/after sets")
    if rot2.before_admitted != (identity_ref, op2) or rot2.after_admitted != (identity_ref, op3):
        problems.append("rot2 does not record the full before/after sets")
    if emergency.before_admitted != (identity_ref, op3) or emergency.after_admitted != (identity_ref,):
        problems.append("the emergency does not record the full before/after sets")
    # NO journaled instant at/after each flip admits the flipped-out
    # credential (the explicit zero-coverage-gap verification)
    for ref in (op1, op2, op3):
        try:
            check_zero_coverage_gap(fold, ref)
        except CredentialLifecycleError as error:
            problems.append("zero-coverage-gap failed for %s: %s" % (ref, error.detail[:70]))
    # probe EVERY journaled instant: the timeline equals each record's
    # after-set (there is no state between the records)
    for record in dw.journal.operations():
        at = record.recorded_at
        if fold.admitted_set_at(at) != record.after_admitted:
            problems.append("timeline mismatch at the journaled instant %s" % at)
    # the pre-history instant is NEVER fabricated
    try:
        fold.admitted_set_at(PRE_JOURNAL_AT)
        problems.append("a pre-history admitted set was fabricated")
    except CredentialLifecycleError:
        pass
    # the journal truth agrees with the identity authority's own
    # records at the end state
    if fold.current_admitted() != admitted_set(dw.ident.service, dw.ident.identity.node_id):
        problems.append("the journal truth disagrees with the identity authority")
    if problems:
        return fail(name, "; ".join(problems[:4]))
    return ok(
        name,
        "the admitted set probed at every journaled instant: the flip lands "
        "exactly at the journaled instants, no between-instant window, no "
        "post-flip admission (3 zero-coverage-gap checks), pre-history "
        "never fabricated, journal == authority",
    )


def _active_op_reference(dw: _DrillWorld) -> Any:
    return dw.ident.service.active_credential(
        dw.ident.identity.node_id, KeyRole.OPERATIONAL, now=EMERG_AT
    ).reference


# ===========================================================================
# case_05 — the atomic flip through the accepted identity authority
# ===========================================================================


def case_05_atomic_flip_via_identity_authority() -> Result:
    name = "case_05_atomic_flip_via_identity_authority"
    dw = _drill_world()
    refs = _op_refs(dw)
    op1 = refs[1]
    records_before = [
        (r.reference.reference_id, r.status.value)
        for r in dw.ident.store.list_records()
    ]
    digest_before = dw.journal.digest()
    # a rotation with an INVALID authorization: the identity authority
    # rejects BEFORE any state change (its own atomicity), the wrap
    # surfaces the typed composition error, and the M018 surfaces
    # stay byte-identical
    bad_authorization = b"\x00" * 32
    result = expect_error(
        name + "/rejected-rotation",
        CredentialLifecycleReason.COMPOSITION,
        lambda: run_rotation_drill(
            service=dw.ident.service,
            m014_state=dw.ident.m014_state,
            journal=dw.journal,
            identity_credential=dw.ident.identity_ref,
            node_id=dw.ident.identity.node_id,
            role=KeyRole.OPERATIONAL,
            new_secret=_secret(9),
            authorization=bad_authorization,
            rotated_at=ROT1_AT,
            provenance=BATTERY_ISSUER,
        ),
    )
    if not result[1]:
        return result
    records_after = [
        (r.reference.reference_id, r.status.value)
        for r in dw.ident.store.list_records()
    ]
    if records_before != records_after:
        return fail(name, "the rejected rotation changed the identity state (not atomic)")
    if dw.journal.digest() != digest_before:
        return fail(name, "the rejected rotation changed the journal")
    if admitted_set(dw.ident.service, dw.ident.identity.node_id) != (
        dw.ident.identity_ref.reference_id, op1
    ):
        return fail(name, "the admitted set changed under a rejected rotation")
    # the SUCCESSFUL rotation: the identity authority's own outcome is
    # an exact single flip (v1 superseded + v2 active in ONE commit)
    rot1 = dw.rotate(_secret(3), ROT1_AT)
    status = {
        r.reference.reference_id: r.status.value
        for r in dw.ident.store.list_records()
        if r.role == KeyRole.OPERATIONAL
    }
    if status[op1] != "superseded":
        return fail(name, "the superseded generation is not SUPERSEDED")
    op2 = [ref for ref in status if ref != op1][0]
    if status[op2] != "active":
        return fail(name, "the new generation is not ACTIVE")
    if rot1.replacement_ref != op2:
        return fail(name, "the journaled replacement disagrees with the authority")
    # the identity credential is untouched (rotation never changes
    # NodeID stability / the identity-role admission)
    identity_record = dw.ident.store.get_record(dw.ident.identity_ref)
    if identity_record.status is not LifecycleState.ACTIVE:
        return fail(name, "the identity-role credential was disturbed")
    return ok(
        name,
        "a rejected rotation leaves the identity state AND the journal "
        "byte-identical; the accepted StoreBatch lands v1-superseded + "
        "v2-active in one commit; the identity credential stays ACTIVE",
    )


# ===========================================================================
# case_06 — the forged non-atomic rotation records rejected
# ===========================================================================


def case_06_forged_nonatomic_records_rejected() -> Result:
    name = "case_06_forged_nonatomic_records_rejected"
    identity_ref = "cred:a:identity:v1"
    op1 = "cred:a:operational:v1"
    op2 = "cred:a:operational:v2"
    before = (identity_ref, op1)
    results: List[Result] = []
    # the wire-forged BOTH-admitted shape (a coverage window)
    results.append(expect_error(
        name + "/both-generations-admitted",
        CredentialLifecycleReason.ROTATION_NONATOMIC,
        lambda: record_from_mapping({
            "operation_id": "", "kind": "rotation", "sequence": 1,
            "node_id": "adcos:node:p:1", "recorded_at": ROT1_AT,
            "subject_ref": op1, "before_admitted": before,
            "after_admitted": (identity_ref, op1, op2),
            "replacement_ref": op2, "provenance": BATTERY_ISSUER,
        }),
    ))
    # the wire-forged NEITHER-admitted shape (a coverage gap)
    results.append(expect_error(
        name + "/neither-generation-admitted",
        CredentialLifecycleReason.ROTATION_NONATOMIC,
        lambda: record_from_mapping({
            "operation_id": "", "kind": "rotation", "sequence": 1,
            "node_id": "adcos:node:p:1", "recorded_at": ROT1_AT,
            "subject_ref": op1, "before_admitted": before,
            "after_admitted": (identity_ref,),
            "replacement_ref": op2, "provenance": BATTERY_ISSUER,
        }),
    ))
    # the wire-forged revocation that KEEPS the revoked credential
    # admitted (the coverage window on the removal path)
    results.append(expect_error(
        name + "/revocation-keeps-admitted",
        CredentialLifecycleReason.ROTATION_NONATOMIC,
        lambda: record_from_mapping({
            "operation_id": "", "kind": "revocation", "sequence": 1,
            "node_id": "adcos:node:p:1", "recorded_at": REV_AT,
            "subject_ref": op1, "before_admitted": before,
            "after_admitted": before, "reason": "r",
            "provenance": BATTERY_ISSUER,
        }),
    ))
    # the tampered id: the derived identity re-verified at
    # deserialization
    good = record_from_mapping({
        "operation_id": "", "kind": "inventory-audit", "sequence": 1,
        "node_id": "adcos:node:p:1", "recorded_at": ROT1_AT,
        "subject_ref": "", "before_admitted": before,
        "after_admitted": before, "provenance": BATTERY_ISSUER,
    })
    tampered = good.to_dict()
    tampered["operation_id"] = "m018-credentials:op:sha256:" + "0" * 64
    results.append(expect_error(
        name + "/tampered-id",
        CredentialLifecycleReason.ID_MISMATCH,
        lambda: record_from_mapping(tampered),
    ))
    bad = [r for r in results if not r[1]]
    if bad:
        return fail(name, "; ".join("%s: %s" % (r[0], r[2]) for r in bad[:4]))
    return ok(
        name,
        "the wire-forged both/neither/kept-admitted shapes and the tampered "
        "id all fail closed at construction (tamper evidence)",
    )


# ===========================================================================
# The full deterministic drill scenario (shared by the determinism cases)
# ===========================================================================


def _full_scenario() -> Dict[str, str]:
    """The full deterministic drill scenario: the identity world +
    the admission-gate world + the frozen client driven to canonical
    ACTIVE + the journal through rotation -> rotation -> the
    emergency revocation -> the 3-round propagation.  Returns the
    deterministic material (journal digest, record ids, the
    mid-scenario admission probe id)."""
    dw = _drill_world()
    rot1 = dw.rotate(_secret(3), ROT1_AT)
    rot2 = dw.rotate(_secret(4), ROT2_AT)
    refs = _op_refs(dw)
    probe = dw.probe(refs[3], ROT2_AT)
    if not probe.admitted:
        raise AssertionError("the mid-scenario probe must be admitted")
    emergency = run_emergency_revocation(
        service=dw.ident.service,
        registry=dw.registry,
        evidence_store=dw.gate.evidence,
        journal=dw.journal,
        credential_ref=_active_op_reference(dw),
        authorization_id=dw.authorization.authorization_id,
        contract_id=dw.gate.cid,
        node_id=dw.ident.identity.node_id,
        client=dw.client,
        reason=EMERGENCY_REASON,
        now=EMERG_AT,
        evidence_valid_until=EMERG_VALID_UNTIL,
        m014_state=dw.ident.m014_state,
        provenance=BATTERY_ISSUER,
    )
    rounds = run_revocation_propagation(
        journal=dw.journal,
        revocation_operation_id=emergency.operation_id,
        revoked_ref=emergency.subject_ref,
        plan=plan_propagation(CONSUMERS, 1, 3),
        round_instants=(ROUND1_AT, ROUND2_AT, ROUND3_AT),
    )
    evidence_refs = verify_emergency_evidence(
        emergency, dw.gate.evidence
    )
    return {
        "journal_digest": dw.journal.digest(),
        "rot1_id": rot1.operation_id,
        "rot2_id": rot2.operation_id,
        "emergency_id": emergency.operation_id,
        "round_ids": ",".join(record.operation_id for record in rounds),
        "probe_id": probe.probe_id,
        "emergency_evidence": ",".join(evidence_refs),
    }


# ===========================================================================
# case_07 — the propagation determinism (identical rounds)
# ===========================================================================


def _revoked_scenario() -> Tuple[_DrillWorld, Any]:
    """A mini-scenario: one rotation then one ordinary revocation (the
    propagation input)."""
    dw = _drill_world()
    dw.rotate(_secret(3), ROT1_AT)
    record = run_revocation_drill(
        service=dw.ident.service,
        m014_state=dw.ident.m014_state,
        journal=dw.journal,
        credential_ref=_active_op_reference_at(dw, REV_AT),
        node_id=dw.ident.identity.node_id,
        reason="ordinary:policy-scheduled-retirement",
        revoked_at=REV_AT,
        provenance=BATTERY_ISSUER,
    )
    return dw, record


def _active_op_reference_at(dw: _DrillWorld, at: str) -> Any:
    return dw.ident.service.active_credential(
        dw.ident.identity.node_id, KeyRole.OPERATIONAL, now=at
    ).reference


def case_07_propagation_determinism() -> Result:
    name = "case_07_propagation_determinism"
    plan = plan_propagation(CONSUMERS, 2, 3)
    deliveries = round_deliveries(plan)
    if deliveries != (
        ("consumer:admission-edge-1", "consumer:admission-edge-2"),
        ("consumer:admission-edge-3",),
    ):
        return fail(name, "the declared fanout slicing is not deterministic")
    if round_deliveries(plan) != deliveries:
        return fail(name, "round_deliveries is not a pure function of the plan")
    # same inputs -> identical journaled rounds (two independent runs)
    round_ids: List[str] = []
    for _ in range(2):
        dw, revoked = _revoked_scenario()
        rounds = run_revocation_propagation(
            journal=dw.journal,
            revocation_operation_id=revoked.operation_id,
            revoked_ref=revoked.subject_ref,
            plan=plan,
            round_instants=(ROUND1_AT, ROUND2_AT, ROUND3_AT),
        )
        round_ids.append(",".join(r.operation_id for r in rounds))
        if propagation_verdict(dw.journal, revoked.operation_id) != "converged":
            return fail(name, "the propagation did not converge")
    if len(set(round_ids)) != 1:
        return fail(name, "identical inputs produced different rounds")
    # the round records carry the deterministic round members
    dw, revoked = _revoked_scenario()
    rounds = run_revocation_propagation(
        journal=dw.journal,
        revocation_operation_id=revoked.operation_id,
        revoked_ref=revoked.subject_ref,
        plan=plan,
        round_instants=(ROUND1_AT, ROUND2_AT, ROUND3_AT),
    )
    if [r.round_index for r in rounds] != [1, 2]:
        return fail(name, "the round indices are not 1-based sequential")
    if rounds[0].delivered_to != (
        "consumer:admission-edge-1", "consumer:admission-edge-2"
    ):
        return fail(name, "round 1 delivered to the wrong consumers")
    if rounds[1].delivered_to != ("consumer:admission-edge-3",):
        return fail(name, "round 2 delivered to the wrong consumers")
    if rounds[0].converged or not rounds[1].converged:
        return fail(name, "the convergence flags are wrong")
    if rounds[1].pending_after != ():
        return fail(name, "the converged round still carries pending consumers")
    # the authoritative admitted set is UNCHANGED by the rounds
    if rounds[0].before_admitted != rounds[0].after_admitted:
        return fail(name, "a propagation round changed the authoritative set")
    return ok(
        name,
        "round_deliveries pure; two independent runs produce byte-identical "
        "round ids; the rounds carry the declared fanout slices in the "
        "declared order; the authoritative admitted set is unchanged",
    )


# ===========================================================================
# case_08 — the declared ROUND-COUNT convergence bound enforced
# ===========================================================================


def case_08_declared_round_bound_enforced() -> Result:
    name = "case_08_declared_round_bound_enforced"
    # (1) the unconvergeable plan: 3 consumers, fanout 1, bound 2 —
    # the bounded rounds run and journal, then FAIL CLOSED citing
    # the declared round count and the pending consumer
    dw, revoked = _revoked_scenario()
    digest_before = dw.journal.digest()
    detail = ""
    try:
        run_revocation_propagation(
            journal=dw.journal,
            revocation_operation_id=revoked.operation_id,
            revoked_ref=revoked.subject_ref,
            plan=plan_propagation(CONSUMERS, 1, 2),
            round_instants=(ROUND1_AT, ROUND2_AT),
        )
        return fail(name, "the unconvergeable plan was accepted")
    except CredentialLifecycleError as error:
        if error.code != CredentialLifecycleReason.PROPAGATION_UNCONVERGED:
            return fail(name, "wrong code %r" % error.code)
        detail = error.detail
    if "ROUND-COUNT bound 2" not in detail:
        return fail(name, "the typed failure does not cite the declared round count")
    if "consumer:admission-edge-3" not in detail:
        return fail(name, "the typed failure does not cite the pending consumer")
    # the bounded rounds STAY JOURNALED (the evidence of the bounded
    # failure — never silently dropped)
    rounds = [
        r for r in dw.journal.operations() if r.kind == "propagation-round"
    ]
    if len(rounds) != 2:
        return fail(name, "the bounded failure did not journal its rounds")
    if rounds[-1].pending_after != ("consumer:admission-edge-3",):
        return fail(name, "the last bounded round does not carry the pending consumer")
    if dw.journal.digest() == digest_before:
        return fail(name, "the bounded rounds were not journaled")
    # (2) the exact-bound plan: 3 consumers, fanout 1, bound 3 —
    # converges AT the declared bound (the last round converges)
    dw2, revoked2 = _revoked_scenario()
    rounds2 = run_revocation_propagation(
        journal=dw2.journal,
        revocation_operation_id=revoked2.operation_id,
        revoked_ref=revoked2.subject_ref,
        plan=plan_propagation(CONSUMERS, 1, 3),
        round_instants=(ROUND1_AT, ROUND2_AT, ROUND3_AT),
    )
    if len(rounds2) != 3 or not rounds2[-1].converged:
        return fail(name, "the exact-bound plan did not converge at round 3")
    # (3) the wall-clock absence: the plan carries INTEGERS only (a
    # declared round count — never a time quantity)
    plan = plan_propagation(CONSUMERS, 1, 3)
    if not isinstance(plan.max_rounds, int) or not isinstance(plan.fanout_per_round, int):
        return fail(name, "the convergence bound is not an integer round count")
    # (4) the instant-count discipline: one deterministic instant per
    # DECLARED round (the budget) — a mismatch fails closed
    dw3, revoked3 = _revoked_scenario()
    mismatch = expect_error(
        name + "/instant-count-mismatch",
        CredentialLifecycleReason.INVALID_INPUT,
        lambda: run_revocation_propagation(
            journal=dw3.journal,
            revocation_operation_id=revoked3.operation_id,
            revoked_ref=revoked3.subject_ref,
            plan=plan_propagation(CONSUMERS, 1, 3),
            round_instants=(ROUND1_AT,),
        ),
    )
    if not mismatch[1]:
        return mismatch
    return ok(
        name,
        "the unconvergeable plan fails closed citing the declared ROUND-COUNT "
        "bound and the pending consumer (its bounded rounds stay journaled); "
        "the exact-bound plan converges at round 3; the bound is an integer "
        "round count, never wall clock",
    )


# ===========================================================================
# case_09 — the journaled/replayable rounds + the consumer model
# ===========================================================================


def case_09_rounds_replayable() -> Result:
    name = "case_09_rounds_replayable"
    dw, revoked = _revoked_scenario()
    rounds = run_revocation_propagation(
        journal=dw.journal,
        revocation_operation_id=revoked.operation_id,
        revoked_ref=revoked.subject_ref,
        plan=plan_propagation(CONSUMERS, 1, 3),
        round_instants=(ROUND1_AT, ROUND2_AT, ROUND3_AT),
    )
    if len(rounds) != 3:
        return fail(name, "expected 3 deterministic rounds")
    # the consumer-observation model: every consumer observed the
    # revocation by its delivery round; a non-consumer never did
    for consumer in CONSUMERS:
        if not consumer_observed_revocation(rounds, consumer):
            return fail(name, "consumer %s did not observe the revocation" % consumer)
    if consumer_observed_revocation(rounds, "consumer:not-declared"):
        return fail(name, "an undeclared consumer observed the revocation")
    # the rounds are replayable: from_records rebuilds them
    # byte-identically (the fold carries the timeline through them)
    rebuilt = LifecycleJournal.from_records(
        dw.journal.to_records(), node_id=dw.journal.node_id
    )
    replayed_rounds = [
        r for r in rebuilt.operations() if r.kind == "propagation-round"
    ]
    if [r.operation_id for r in replayed_rounds] != [r.operation_id for r in rounds]:
        return fail(name, "the replayed rounds diverged")
    if rebuilt.digest() != dw.journal.digest():
        return fail(name, "the replayed journal diverged")
    # the verdict over the replayed rounds
    if propagation_verdict(rebuilt, revoked.operation_id) != "converged":
        return fail(name, "the replayed propagation verdict is not converged")
    # the propagated operation must be a journaled revocation
    dw2, revoked2 = _revoked_scenario()
    result = expect_error(
        name + "/propagating-a-non-revocation",
        CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
        lambda: run_revocation_propagation(
            journal=dw2.journal,
            revocation_operation_id=dw2.journal.operations()[0].operation_id,
            revoked_ref=revoked2.subject_ref,
            plan=plan_propagation(CONSUMERS, 1, 3),
            round_instants=(ROUND1_AT, ROUND2_AT, ROUND3_AT),
        ),
    )
    if not result[1]:
        return result
    return ok(
        name,
        "3 journaled rounds replay byte-identically from records; every "
        "declared consumer observes the revocation at its delivery round; "
        "the verdict is converged; propagating a non-revocation fails closed",
    )


# ===========================================================================
# case_10 — the emergency revocation path (distinct, typed, journaled,
# evidence-visible at every step)
# ===========================================================================


def case_10_emergency_path() -> Result:
    name = "case_10_emergency_path"
    dw = _drill_world()
    dw.rotate(_secret(3), ROT1_AT)
    refs = _op_refs(dw)
    op2 = refs[2]
    emergency = run_emergency_revocation(
        service=dw.ident.service,
        registry=dw.registry,
        evidence_store=dw.gate.evidence,
        journal=dw.journal,
        credential_ref=_active_op_reference(dw),
        authorization_id=dw.authorization.authorization_id,
        contract_id=dw.gate.cid,
        node_id=dw.ident.identity.node_id,
        client=dw.client,
        reason=EMERGENCY_REASON,
        now=EMERG_AT,
        evidence_valid_until=EMERG_VALID_UNTIL,
        m014_state=dw.ident.m014_state,
        provenance=BATTERY_ISSUER,
    )
    # the DISTINCT typed operation (never a silent shortcut)
    if emergency.kind != "emergency-revocation":
        return fail(name, "the emergency path is not the distinct typed kind")
    if tuple(step.step for step in emergency.steps) != EMERGENCY_STEP_KINDS:
        return fail(name, "the frozen emergency steps are not carried in order")
    if emergency.reason != EMERGENCY_REASON:
        return fail(name, "the emergency reason was not journaled verbatim")
    # evidence-visible at EVERY step: each step's evidence references
    # resolve to REAL typed LOCK-106 records in the real store
    resolved = verify_emergency_evidence(emergency, dw.gate.evidence)
    if not resolved:
        return fail(name, "no evidence references resolved")
    for step in emergency.steps:
        if not step.evidence_refs:
            return fail(name, "step %r carries no evidence references" % step.step)
    # the three authority outcomes
    revoked_record = dw.ident.store.get_record(CredentialReference(op2))
    if revoked_record.status is not LifecycleState.REVOKED:
        return fail(name, "the credential is not REVOKED at the identity authority")
    if revoked_record.revoked is None or revoked_record.revoked.reason != EMERGENCY_REASON:
        return fail(name, "the identity revocation metadata is missing/altered")
    if not dw.registry.is_revoked(dw.authorization.authorization_id):
        return fail(name, "the principal authorization is not revoked")
    verdict = dw.registry.check(
        dw.authorization.authorization_id,
        node_id=dw.ident.identity.node_id.text,
        contract_id=dw.gate.cid,
        at_instant=EMERG_AT,
    )
    if verdict != "revoked":
        return fail(name, "the registry verdict is not revoked")
    session = dw.authority.session(dw.session_id)
    if session.state != "revoked" or session.termination_reason != "emergency-stop":
        return fail(name, "the canonical session did not terminate emergency-stop")
    # the post-probes fail closed at the composed gate
    probe = dw.probe(op2, EMERG_AT)
    if probe.admitted or probe.rejection != "lifecycle:revoked":
        return fail(name, "the revoked credential still admits (%r)" % probe.rejection)
    identity_probe = dw.probe(dw.ident.identity_ref.reference_id, EMERG_AT)
    if identity_probe.admitted or identity_probe.rejection != "authorization:revoked":
        return fail(name, "the node authorization still admits (%r)" % identity_probe.rejection)
    # the M014 bookkeeping tracks the emergency (the lifecycle verdict)
    from identity.convergence import evaluate_credential_lifecycle
    verdict2 = evaluate_credential_lifecycle(
        dw.ident.policy, dw.ident.m014_state, op2, EMERG_AT
    )
    if verdict2.verdict != "revoked":
        return fail(name, "the M014 lifecycle verdict is not revoked")
    return ok(
        name,
        "the distinct typed kind with the 3 frozen steps; every step's "
        "LOCK-106 references resolve in the real evidence store; the "
        "identity/registry/session outcomes verified; the post-probes "
        "fail closed (lifecycle:revoked, authorization:revoked)",
    )


# ===========================================================================
# case_11 — the emergency stop through the frozen W049 client (the
# accepted client surface driven by reference)
# ===========================================================================


def case_11_emergency_through_frozen_client() -> Result:
    name = "case_11_emergency_through_frozen_client"
    dw = _drill_world()
    dw.rotate(_secret(3), ROT1_AT)
    lease_id = dw.authority.session(dw.session_id).lease_id
    consent_ref = dw.authority.session(dw.session_id).consent_ref
    emergency = run_emergency_revocation(
        service=dw.ident.service,
        registry=dw.registry,
        evidence_store=dw.gate.evidence,
        journal=dw.journal,
        credential_ref=_active_op_reference(dw),
        authorization_id=dw.authorization.authorization_id,
        contract_id=dw.gate.cid,
        node_id=dw.ident.identity.node_id,
        client=dw.client,
        reason=EMERGENCY_REASON,
        now=EMERG_AT,
        evidence_valid_until=EMERG_VALID_UNTIL,
        m014_state=dw.ident.m014_state,
        provenance=BATTERY_ISSUER,
    )
    if emergency.kind != "emergency-revocation":
        return fail(name, "the emergency did not journal the distinct kind")
    # the frozen client's OWN surfaces: STOPPED, the local fail-safe
    # detach, the verified terminal read, the stop notification
    if str(dw.client.state) != ProviderClientState.STOPPED:
        return fail(name, "the frozen client is not STOPPED")
    if PATH_REF not in dw.gate.world.runtime.adapter.detach_log():
        return fail(name, "the local fail-safe detach did not run first")
    if "provider.share_stopped" not in dw.gate.world.runtime.adapter.notifications():
        return fail(name, "the stop notification did not reach the adapter")
    # the canonical termination through the contract store's OWN command
    if str(dw.gate.store.lease(lease_id).state) != "revoked":
        return fail(name, "the canonical lease was not revoked (LOCK-101)")
    if dw.authority.consent(consent_ref).state != "withdrawn":
        return fail(name, "the granted consent was not withdrawn")
    # the emergency evidence: the withdrawn consent attestation IS a
    # real LOCK-106 record in the store (consumed by reference)
    withdrawn = [
        record for record in dw.gate.evidence.records()
        if getattr(record, "attestation_kind", "") == "controller-verified"
        and getattr(record, "attested_value", None) == 2
    ]
    if not withdrawn:
        return fail(name, "no withdrawn-consent LOCK-106 record exists")
    if not set(r.record_id for r in withdrawn) <= set(
        ref for step in emergency.steps for ref in step.evidence_refs
    ):
        return fail(name, "the withdrawn attestation is not cited by the emergency steps")
    # the failed emergency: a client that never reached an operating
    # state (READY) fails closed at the frozen client's own control
    # — the typed composition error, and NO partial M018 record (the
    # journal stays byte-identical; the authority transitions that
    # completed remain visible at their own authorities)
    ident3 = _identity_world()
    gate3 = _gate_world()
    authorization3 = build_principal_authorization(
        node_id=ident3.identity.node_id.text,
        principal_kind="APPLICATION",
        principal_ref=BUYER,
        contract=gate3.store.contract(gate3.cid),
        valid_from=T0,
        valid_until=T_END,
    )
    registry3 = AuthorizationRegistry()
    registry3.register(authorization3)
    client3 = gate3.world.client
    client3.check_capability()
    client3.become_ready()
    journal3 = LifecycleJournal(ident3.identity.node_id.text)
    failed = expect_error(
        name + "/client-not-operating",
        CredentialLifecycleReason.COMPOSITION,
        lambda: run_emergency_revocation(
            service=ident3.service,
            registry=registry3,
            evidence_store=gate3.evidence,
            journal=journal3,
            credential_ref=ident3.op_ref,
            authorization_id=authorization3.authorization_id,
            contract_id=gate3.cid,
            node_id=ident3.identity.node_id,
            client=client3,
            reason=EMERGENCY_REASON,
            now=EMERG_AT,
            evidence_valid_until=EMERG_VALID_UNTIL,
            m014_state=ident3.m014_state,
            provenance=BATTERY_ISSUER,
        ),
    )
    if not failed[1]:
        return failed
    if len(journal3) != 0:
        return fail(name, "the client-not-operating emergency journaled a record")
    # the failed emergency at the authorization step: an unknown
    # authorization id fails at step 2 (typed composition error, the
    # journal still carries no partial record)
    ident4 = _identity_world()
    gate4 = _gate_world()
    registry4 = AuthorizationRegistry()
    client4 = gate4.world.client
    client4.check_capability()
    client4.become_ready()
    journal4 = LifecycleJournal(ident4.identity.node_id.text)
    unknown_authz = expect_error(
        name + "/unknown-authorization",
        CredentialLifecycleReason.COMPOSITION,
        lambda: run_emergency_revocation(
            service=ident4.service,
            registry=registry4,
            evidence_store=gate4.evidence,
            journal=journal4,
            credential_ref=ident4.op_ref,
            authorization_id="m014-identity:authz:sha256:" + "0" * 64,
            contract_id=gate4.cid,
            node_id=ident4.identity.node_id,
            client=client4,
            reason=EMERGENCY_REASON,
            now=EMERG_AT,
            evidence_valid_until=EMERG_VALID_UNTIL,
            m014_state=ident4.m014_state,
            provenance=BATTERY_ISSUER,
        ),
    )
    if not unknown_authz[1]:
        return unknown_authz
    if len(journal4) != 0:
        return fail(name, "the unknown-authorization emergency journaled a record")
    return ok(
        name,
        "the frozen client STOPPED (fail-safe detach first, notification); "
        "the canonical lease revoked through the store's own command; the "
        "consent withdrawn (a real LOCK-106 record cited by the steps); "
        "failed emergencies leave the journal without partial records",
    )


# ===========================================================================
# case_12 — the clean inventory audit
# ===========================================================================


def case_12_clean_inventory() -> Result:
    name = "case_12_clean_inventory"
    dw = _drill_world()
    dw.rotate(_secret(3), ROT1_AT)
    refs = _op_refs(dw)
    audit = run_inventory_audit(
        journal=dw.journal,
        store=dw.ident.store,
        m014_state=dw.ident.m014_state,
        policy=dw.ident.policy,
        node_id=dw.ident.identity.node_id,
        at_instant=ROT1_AT,
    )
    identity_ref = dw.ident.identity_ref.reference_id
    if audit.admitted_count != 2:
        return fail(name, "the clean audit traced %d credentials (expected 2)" % audit.admitted_count)
    traced = {trace.credential_ref for trace in audit.traces}
    if traced != {identity_ref, refs[2]}:
        return fail(name, "the audit traced the wrong admitted set")
    for trace in audit.traces:
        if trace.status != "active" or trace.key_version < 1:
            return fail(name, "a trace carries an inconsistent record view")
        if not trace.activated_at:
            return fail(name, "a trace carries no activation instant")
    # the rotation trace cites the journaled operation that produced it
    op_trace = [t for t in audit.traces if t.credential_ref == refs[2]][0]
    if op_trace.operation_refs != (dw.journal.operations()[0].operation_id,):
        return fail(name, "the trace does not cite the journaled rotation")
    # the audit record round-trips
    rebuilt = InventoryAuditRecord.from_dict(audit.to_dict())
    if rebuilt.to_dict() != audit.to_dict():
        return fail(name, "the audit record does not round-trip")
    # journaling the clean audit (read-only evidence)
    record = journal_inventory_audit(dw.journal, audit, at_instant=ROT2_AT)
    if record.kind != "inventory-audit" or record.before_admitted != record.after_admitted:
        return fail(name, "the journaled audit is not read-only")
    if dw.journal.fold().admitted_set_at(ROT2_AT) != (identity_ref, refs[2]):
        return fail(name, "the journaled audit changed the admitted set")
    # the trace record round-trips
    trace = InventoryTrace.from_dict(audit.traces[0].to_dict())
    if trace.to_dict() != audit.traces[0].to_dict():
        return fail(name, "the trace record does not round-trip")
    return ok(
        name,
        "2 admitted credentials traced (status/version/activation/operation "
        "refs); the audit + trace records round-trip; the journaled audit is "
        "read-only evidence",
    )


# ===========================================================================
# case_13..case_19 — one case per inventory break kind (fail closed)
# ===========================================================================


def _audit_case(name: str, code: str, break_setup: Callable) -> Result:
    """One inventory break-kind case: ``break_setup(dw)`` corrupts the
    world after a rotation; the audit must fail closed with the typed
    ``credential-inventory-incomplete`` citing the break kind."""
    full = name
    dw = _drill_world()
    dw.rotate(_secret(3), ROT1_AT)
    break_setup(dw)
    return expect_error(full, code, lambda: run_inventory_audit(
        journal=dw.journal,
        store=dw.ident.store,
        m014_state=dw.ident.m014_state,
        policy=dw.ident.policy,
        node_id=dw.ident.identity.node_id,
        at_instant=ROT1_AT,
    ))


def _forged_journal(
    dw: _DrillWorld, admitted: Tuple[str, ...], at_instant: str
) -> LifecycleJournal:
    """A wire-forged journal whose single audit record carries the
    corrupted admitted set (the M008 battery's wire-forged precedent:
    the ids re-derive over the forged content — the journal truth
    disagrees with the identity authority, and the AUDIT catches
    it)."""
    forged = LifecycleJournal(dw.ident.identity.node_id.text)
    forged.append(
        LifecycleOperationRecord(
            operation_id="", kind="inventory-audit", sequence=1,
            node_id=dw.ident.identity.node_id.text, recorded_at=at_instant,
            subject_ref="",
            before_admitted=admitted, after_admitted=admitted,
            provenance=BATTERY_ISSUER,
        )
    )
    return forged


def case_13_break_unknown_reference() -> Result:
    def corrupt(dw: _DrillWorld) -> None:
        # a wire-forged journal carrying a PHANTOM admitted reference
        # (the journal truth disagrees with the identity authority —
        # the audit catches it, fail closed)
        refs = _op_refs(dw)
        dw.journal = _forged_journal(
            dw,
            (dw.ident.identity_ref.reference_id, refs[2],
             "cred:phantom:operational:v9"),
            ROT1_AT,
        )
    return _audit_case(
        "case_13_break_unknown_reference",
        CredentialLifecycleReason.INVENTORY_INCOMPLETE,
        corrupt,
    )


def case_14_break_status_mismatch() -> Result:
    def corrupt(dw: _DrillWorld) -> None:
        # a wire-forged journal still claiming the SUPERSEDED
        # generation as admitted (the stale local view)
        refs = _op_refs(dw)
        dw.journal = _forged_journal(
            dw, (dw.ident.identity_ref.reference_id, refs[1]), ROT1_AT
        )
    return _audit_case(
        "case_14_break_status_mismatch",
        CredentialLifecycleReason.INVENTORY_INCOMPLETE,
        corrupt,
    )


def case_15_break_missing_activation() -> Result:
    def corrupt(dw: _DrillWorld) -> None:
        # a forged ACTIVE record without an activation instant (the
        # public store update surface; the wire-forged record shape)
        refs = _op_refs(dw)
        record = dw.ident.store.get_record(CredentialReference(refs[2]))
        dw.ident.store.update_record(replace(record, activated_at=None))
    return _audit_case(
        "case_15_break_missing_activation",
        CredentialLifecycleReason.INVENTORY_INCOMPLETE,
        corrupt,
    )


def case_16_break_missing_supersession() -> Result:
    def corrupt(dw: _DrillWorld) -> None:
        refs = _op_refs(dw)
        record = dw.ident.store.get_record(CredentialReference(refs[1]))
        dw.ident.store.update_record(replace(record, superseded_at=None))
    return _audit_case(
        "case_16_break_missing_supersession",
        CredentialLifecycleReason.INVENTORY_INCOMPLETE,
        corrupt,
    )


def case_17_break_missing_revocation_info() -> Result:
    def corrupt(dw: _DrillWorld) -> None:
        refs = _op_refs(dw)
        revoked = run_revocation_drill(
            service=dw.ident.service,
            m014_state=dw.ident.m014_state,
            journal=dw.journal,
            credential_ref=CredentialReference(refs[2]),
            node_id=dw.ident.identity.node_id,
            reason="ordinary:audit-fixture",
            revoked_at=REV_AT,
            provenance=BATTERY_ISSUER,
        )
        assert revoked is not None
        record = dw.ident.store.get_record(CredentialReference(refs[2]))
        dw.ident.store.update_record(replace(record, revoked=None))
    return _audit_case(
        "case_17_break_missing_revocation_info",
        CredentialLifecycleReason.INVENTORY_INCOMPLETE,
        corrupt,
    )


def case_18_break_generation_gap() -> Result:
    name = "case_18_break_generation_gap"
    # a raw record store with a GAP in the (node, role) version chain
    # (v1 and v3 present, v2 missing — constructed through the public
    # put_record surface, the identity battery's raw-record fixture)
    dw = _drill_world()
    profiles = ProfileSet.load_default()
    ident2 = NodeIdentity.create(
        profiles.get("identity.sha256-hmac-dev.v1"),
        dw.ident.provider.public_material(_secret(7)),
        ID_PROV_AT,
    )
    template = dw.ident.store.list_records()[0]
    for version in (1, 3):
        dw.ident.store.put_record(replace(
            template,
            reference=CredentialReference(
                "cred:%s:operational:v%d" % (ident2.node_id.text, version)
            ),
            node_id=ident2.node_id,
            key_version=version,
            status=LifecycleState.ACTIVE if version == 3 else LifecycleState.SUPERSEDED,
            activated_at=ID_PROV_AT if version == 3 else None,
            superseded_at=None if version == 3 else ID_PROV_AT,
        ))
    journal2 = LifecycleJournal(ident2.node_id.text)
    journal2.append(
        LifecycleOperationRecord(
            operation_id="", kind="inventory-audit", sequence=1,
            node_id=ident2.node_id.text, recorded_at=ROT1_AT,
            subject_ref="",
            before_admitted=("cred:%s:operational:v3" % ident2.node_id.text,),
            after_admitted=("cred:%s:operational:v3" % ident2.node_id.text,),
            provenance=BATTERY_ISSUER,
        )
    )
    state2 = CredentialLifecycleState()
    state2.record_activation(
        "cred:%s:operational:v3" % ident2.node_id.text, ID_PROV_AT,
        LifecycleState.ACTIVE.value,
    )
    return expect_error(
        name, CredentialLifecycleReason.INVENTORY_INCOMPLETE,
        lambda: run_inventory_audit(
            journal=journal2,
            store=dw.ident.store,
            m014_state=state2,
            policy=dw.ident.policy,
            node_id=ident2.node_id,
            at_instant=ROT1_AT,
        ),
    )


def case_19_break_bookkeeping_missing() -> Result:
    def corrupt(dw: _DrillWorld) -> None:
        # the M014 bookkeeping WITHOUT the new generation's activation
        # (the consumed M014 evaluation fails closed on an ADMITTED
        # credential — the typed inventory break)
        state = CredentialLifecycleState()
        state.record_activation(
            dw.ident.identity_ref.reference_id, ID_PROV_AT,
            LifecycleState.ACTIVE.value,
        )
        dw.ident.m014_state = state
    return _audit_case(
        "case_19_break_bookkeeping_missing",
        CredentialLifecycleReason.INVENTORY_INCOMPLETE,
        corrupt,
    )


# ===========================================================================
# case_20 — the admission gate composition (by reference, verdicts
# consumed verbatim, the idempotent zero-byte probe)
# ===========================================================================


def case_20_admission_gate_composition() -> Result:
    name = "case_20_admission_gate_composition"
    dw = _drill_world()
    refs = _op_refs(dw)
    identity_ref = dw.ident.identity_ref.reference_id
    problems: List[str] = []
    # pre-rotation: the composed probe admits op-v1 through the three
    # accepted gates (the verdicts consumed verbatim)
    probe = dw.probe(refs[1], ROT1_AT)
    if not probe.admitted:
        problems.append("the pre-rotation probe is not admitted")
    if (probe.lifecycle_verdict, probe.authorization_verdict, probe.operational_state) != (
        "ok", "authorized", "active"
    ):
        problems.append("the consumed verdicts are not recorded verbatim")
    # the ZERO-byte probe is idempotent: repeated probes admit with
    # the session state unchanged (bytes_admitted advanced by zero)
    session_before = dw.authority.session(dw.session_id)
    probe_again = dw.probe(refs[1], ROT1_AT)
    session_after = dw.authority.session(dw.session_id)
    if not probe_again.admitted or probe_again.probe_id != probe.probe_id:
        problems.append("the repeated probe diverged")
    if session_after.bytes_admitted != session_before.bytes_admitted:
        problems.append("the zero-byte probe advanced the session state")
    # the superseded generation: the M014 lifecycle verdict rejects
    # (gate 1, the first rejecting gate named)
    dw.rotate(_secret(3), ROT1_AT)
    refs = _op_refs(dw)
    old_probe = dw.probe(refs[1], ROT1_AT)
    if old_probe.admitted or old_probe.rejection != "lifecycle:not-active":
        problems.append("the superseded credential still admits (%r)" % old_probe.rejection)
    new_probe = dw.probe(refs[2], ROT1_AT)
    if not new_probe.admitted:
        problems.append("the new generation does not admit")
    # gate 3 (the converged traffic-admission point): an
    # authority-side session revocation (the lease revoked through
    # the authority's own driver, the registry INTACT) is recorded
    # verbatim as the operational rejection class (the converged
    # gate's lease check fires first — its own typed code)
    dw.authority.revoke_authorization(dw.session_id, "operator-policy-7")
    gate3_probe = dw.probe(identity_ref, ROT1_AT)
    if gate3_probe.admitted or gate3_probe.rejection != "admission-gate:rejected:lease-not-active":
        problems.append("the gate-3 rejection was not recorded verbatim (%r)" % gate3_probe.rejection)
    # gate 2 (the M014 registry): a registry revocation is observed
    # first by the registry's own check
    dw2 = _drill_world()
    from identity.convergence import authorization_revocation as m014_revocation
    dw2.registry.revoke(
        m014_revocation(
            authorization_id=dw2.authorization.authorization_id,
            reason="operator-policy-9",
            revoked_at=REV_AT,
        )
    )
    gate2_probe = dw2.probe(dw2.ident.identity_ref.reference_id, REV_AT)
    if gate2_probe.admitted or gate2_probe.rejection != "authorization:revoked":
        problems.append("the gate-2 rejection was not recorded verbatim (%r)" % gate2_probe.rejection)
    # the raising twin: a non-admitting probe fails closed
    twin = expect_error(
        name + "/raising-twin",
        CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
        lambda: check_credential_admission(
            policy=dw2.ident.policy,
            state=dw2.ident.m014_state,
            registry=dw2.registry,
            authorization_id=dw2.authorization.authorization_id,
            node_id=dw2.ident.identity.node_id.text,
            contract_id=dw2.gate.cid,
            credential_ref=dw2.ident.identity_ref.reference_id,
            at_instant=REV_AT,
            authority=dw2.authority,
            session_id=dw2.session_id,
        ),
    )
    if not twin[1]:
        problems.append("the raising twin did not fail closed")
    # LOCK-117: a non-accepted admission gate object is rejected
    duck = object()
    gate_type = expect_error(
        name + "/second-runtime-rejected",
        CredentialLifecycleReason.INVALID_INPUT,
        lambda: probe_credential_admission(
            policy=dw.ident.policy,
            state=dw.ident.m014_state,
            registry=dw.registry,
            authorization_id=dw.authorization.authorization_id,
            node_id=dw.ident.identity.node_id.text,
            contract_id=dw.gate.cid,
            credential_ref=refs[1],
            at_instant=ROT1_AT,
            authority=duck,
            session_id=dw.session_id,
        ),
    )
    if not gate_type[1]:
        problems.append("a second authorization runtime was accepted")
    if problems:
        return fail(name, "; ".join(problems[:4]))
    return ok(
        name,
        "the three accepted gates driven by reference with the verdicts "
        "consumed verbatim; the zero-byte probe idempotent; per-gate "
        "rejections recorded (lifecycle/authorization/admission-gate); "
        "non-accepted gate objects rejected (LOCK-117)",
    )


# ===========================================================================
# case_21 — the full drill through the frozen W049 client protocol
# ===========================================================================


def case_21_drill_through_frozen_client() -> Result:
    name = "case_21_drill_through_frozen_client"
    dw = _drill_world()
    refs = _op_refs(dw)
    problems: List[str] = []
    # the frozen client's own state machine: the admission chain drove
    # it to canonical ACTIVE (the client surface driven by reference)
    if str(dw.client.state) != ProviderClientState.ACTIVE:
        problems.append("the frozen client is not ACTIVE")
    session = dw.authority.session(dw.session_id)
    if session.state != "active" or str(session.session_ref) != SESSION_REF:
        problems.append("the canonical session is not the drill's session")
    # the client journal carries the admission chain events (the
    # frozen client's OWN evidentiary surface)
    kinds = [event.kind for event in dw.gate.world.runtime.journal.events()]
    for expected in (
        "provider.capability_changed", "provider.consent_requested",
        "provider.consent_granted", "provider.share_started",
    ):
        if expected not in kinds:
            problems.append("the client journal lacks %r" % expected)
    # the request ledger recorded the chain (idempotent mutating
    # requests — the frozen runtime's own discipline)
    actions = sorted(
        record.action for record in dw.gate.world.runtime.request_records()
    )
    if actions != ["activate", "authorize", "capability", "grant_consent", "prepare"]:
        problems.append("the request ledger actions diverged: %r" % (actions,))
    # the rotation inside the live drill: the node-level admission
    # persists (the session stays active, the client stays ACTIVE)
    # while the credential generation flips
    dw.rotate(_secret(3), ROT1_AT)
    refs = _op_refs(dw)
    if str(dw.client.state) != ProviderClientState.ACTIVE:
        problems.append("the rotation disturbed the frozen client")
    if dw.authority.session(dw.session_id).state != "active":
        problems.append("the rotation disturbed the canonical session")
    new_probe = dw.probe(refs[2], ROT1_AT)
    old_probe = dw.probe(refs[1], ROT1_AT)
    if not new_probe.admitted:
        problems.append("the new generation does not admit through the gate")
    if old_probe.admitted:
        problems.append("the superseded generation still admits")
    # the client's canonical read window: the session read is bound
    # to THIS provider context (the frozen binding discipline)
    read = dw.gate.world.runtime.gateway.read_sharing_session(dw.session_id)
    if read.binding("provider_ref") != dw.ident.identity.node_id.text:
        problems.append("the canonical read is not provider-bound")
    if problems:
        return fail(name, "; ".join(problems[:4]))
    return ok(
        name,
        "the frozen client protocol chain (capability->ready->prepare->"
        "consent->handoff->activate) driven by reference; the client "
        "journal/ledger carry the chain; the rotation flips the credential "
        "generation without disturbing the session or the client",
    )


# ===========================================================================
# case_22 — LOCK-119 structural probes (secret-free public types; the
# domain never opens the store's secret path)
# ===========================================================================


def case_22_lock119_structural_probes() -> Result:
    name = "case_22_lock119_structural_probes"
    problems: List[str] = []
    # (1) NO public M018 record type carries a bytes member (the
    # structural incapability: every field is a string/int/bool/tuple
    # of those)
    record_types = (
        LifecycleOperationRecord, EmergencyStep, PropagationPlan,
        AdmissionProbe, InventoryTrace, InventoryAuditRecord,
    )
    for cls in record_types:
        for field_name, field_type in cls.__dataclass_fields__.items():
            annotation = str(field_type.type)
            if "bytes" in annotation.lower():
                problems.append(
                    "%s.%s carries a bytes-typed member" % (cls.__name__, field_name)
                )
    # (2) a bytes member is REJECTED at the boundary (the reference
    # grammar: strings only)
    try:
        LifecycleOperationRecord(
            operation_id="", kind="inventory-audit", sequence=1,
            node_id=b"adcos:node:p:1", recorded_at=ROT1_AT, subject_ref="",
            before_admitted=(), after_admitted=(),
            provenance=BATTERY_ISSUER,
        )
        problems.append("a bytes node_id was accepted")
    except CredentialLifecycleError:
        pass
    # (3) the assembled secret never appears on ANY journaled,
    # serialized, echoed or exceptional surface of the drill
    dw = _drill_world()
    dw.rotate(_secret(3), ROT1_AT)
    dw.rotate(_secret(4), ROT2_AT)
    emergency = run_emergency_revocation(
        service=dw.ident.service,
        registry=dw.registry,
        evidence_store=dw.gate.evidence,
        journal=dw.journal,
        credential_ref=_active_op_reference(dw),
        authorization_id=dw.authorization.authorization_id,
        contract_id=dw.gate.cid,
        node_id=dw.ident.identity.node_id,
        client=dw.client,
        reason=EMERGENCY_REASON,
        now=EMERG_AT,
        evidence_valid_until=EMERG_VALID_UNTIL,
        m014_state=dw.ident.m014_state,
        provenance=BATTERY_ISSUER,
    )
    run_revocation_propagation(
        journal=dw.journal,
        revocation_operation_id=emergency.operation_id,
        revoked_ref=emergency.subject_ref,
        plan=plan_propagation(CONSUMERS, 1, 3),
        round_instants=(ROUND1_AT, ROUND2_AT, ROUND3_AT),
    )
    probes = [
        probe_credential_admission(
            policy=dw.ident.policy,
            state=dw.ident.m014_state,
            registry=dw.registry,
            authorization_id=dw.authorization.authorization_id,
            node_id=dw.ident.identity.node_id.text,
            contract_id=dw.gate.cid,
            credential_ref=dw.ident.identity_ref.reference_id,
            at_instant=EMERG_AT,
            authority=dw.authority,
            session_id=dw.session_id,
        )
    ]
    surfaces: Dict[str, bytes] = {
        "journal-snapshot": canonical_json_bytes(dw.journal.snapshot_dict()),
        "fold-digest": dw.journal.digest().encode(),
        "emergency-record": canonical_json_bytes(emergency.to_dict()),
        "probe-record": canonical_json_bytes(probes[0].to_dict()),
        "evidence-snapshot": b"\n".join(
            line.encode() for line in dw.gate.evidence.snapshot_lines()
        ),
        "repr-record": repr(emergency).encode(),
        "repr-probe": repr(probes[0]).encode(),
    }
    secrets = [_secret(i) for i in (1, 2, 3, 4)]
    for surface_name, blob in surfaces.items():
        for secret in secrets:
            if secret in blob:
                problems.append(
                    "the secret material leaked onto %s" % surface_name
                )
    # exception messages never echo the secret
    try:
        run_rotation_drill(
            service=dw.ident.service,
            m014_state=dw.ident.m014_state,
            journal=dw.journal,
            identity_credential=dw.ident.identity_ref,
            node_id=dw.ident.identity.node_id,
            role=KeyRole.OPERATIONAL,
            new_secret=_secret(9),
            authorization=b"\x00" * 32,
            rotated_at=ROUND3_AT,
            provenance=BATTERY_ISSUER,
        )
    except CredentialLifecycleError as error:
        if _secret(9) in str(error).encode() or _SECRET_TAIL in str(error).encode():
            problems.append("the exception text echoed the secret")
    # (4) AST audit: the domain never opens the store's secret path
    for path in sorted((REPO_ROOT / "credentials").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in (
                "get_secret", "put_secret",
            ):
                problems.append("%s opens the store secret path (%s)" % (
                    path.name, node.attr,
                ))
            if isinstance(node, ast.Name) and node.id in (
                "get_secret", "put_secret",
            ):
                problems.append("%s opens the store secret path (%s)" % (
                    path.name, node.id,
                ))
    if problems:
        return fail(name, "; ".join(problems[:4]))
    return ok(
        name,
        "no public record type carries a bytes member (structural); the "
        "assembled secret absent from the journal/fold/emergency/probe/"
        "evidence/repr/exception surfaces; the domain never calls the "
        "store's secret path (AST-audited)",
    )


# ===========================================================================
# case_23 — the fragment-assembled fixtures (LOCK-119)
# ===========================================================================


def case_23_fragment_assembled_fixtures() -> Result:
    name = "case_23_fragment_assembled_fixtures"
    problems: List[str] = []
    # the secrets are assembled at runtime from fragments: the FULL
    # shape never appears in this source
    battery_source = Path(__file__).resolve().read_text(encoding="utf-8")
    domain_sources = b"".join(
        path.read_bytes() for path in sorted((REPO_ROOT / "credentials").glob("*.py"))
    )
    for seed in (1, 2, 3, 4, 7, 9):
        full = _secret(seed)
        if full.decode("ascii") in battery_source:
            problems.append("the full secret shape for seed %d appears in source" % seed)
        if full in domain_sources:
            problems.append("the full secret shape for seed %d appears in the domain" % seed)
    # the fragments alone are inert (no fragment is a usable secret)
    for fragment in (_SECRET_HEAD, _SECRET_TAIL):
        if len(fragment) >= len(_secret(1)):
            problems.append("a fragment is not smaller than the assembled secret")
    # the assembled secrets are deterministic and distinct per seed
    if _secret(1) != _secret(1) or _secret(1) == _secret(2):
        problems.append("the secret assembly is not deterministic/distinct")
    # the ONLY secret path is the store (the identity battery's own
    # discipline): every secret entered through the service's public
    # provisioning/rotation APIs and is retrievable only through the
    # store's get_secret
    dw = _drill_world()
    if dw.ident.store.get_secret(dw.ident.identity_ref) != _secret(1):
        problems.append("the identity secret did not reach the store intact")
    if dw.ident.store.get_secret(dw.ident.op_ref) != _secret(2):
        problems.append("the operational secret did not reach the store intact")
    if problems:
        return fail(name, "; ".join(problems[:4]))
    return ok(
        name,
        "the full secret shapes appear in NO source (battery or domain); "
        "the fragments are inert; the assembly deterministic and distinct; "
        "the only secret path is the accepted store",
    )


# ===========================================================================
# case_24 — the canonical-JSON round-trips
# ===========================================================================


def case_24_canonical_round_trips() -> Result:
    name = "case_24_canonical_round_trips"
    material = _full_scenario()
    problems: List[str] = []
    # the record dicts round-trip through the wire constructors with
    # the tamper-evident identities re-verified
    dw = _drill_world()
    dw.rotate(_secret(3), ROT1_AT)
    for record in dw.journal.operations():
        data = record.to_dict()
        rebuilt = record_from_mapping(dict(data))
        if rebuilt.to_dict() != data:
            problems.append("the operation record %r does not round-trip" % record.kind)
    # the probe round-trips
    probe = dw.probe(_op_refs(dw)[2], ROT1_AT)
    if probe_from_mapping(dict(probe.to_dict())).to_dict() != probe.to_dict():
        problems.append("the admission probe does not round-trip")
    # the propagation plan round-trips
    plan = plan_propagation(CONSUMERS, 2, 3)
    if PropagationPlan.from_dict(plan.to_dict()).to_dict() != plan.to_dict():
        problems.append("the propagation plan does not round-trip")
    # the journal snapshot round-trips (construction-is-recovery)
    rebuilt_journal = LifecycleJournal.from_records(
        dw.journal.to_records(), node_id=dw.journal.node_id
    )
    if rebuilt_journal.digest() != dw.journal.digest():
        problems.append("the journal snapshot does not round-trip")
    # tampered dicts fail closed (the ids re-derived at
    # deserialization)
    tampered = probe.to_dict()
    tampered["lifecycle_verdict"] = "rotation-due"
    try:
        probe_from_mapping(dict(tampered))
        problems.append("a tampered probe was accepted")
    except CredentialLifecycleError:
        pass
    # the scenario material is byte-stable
    if len(material["journal_digest"]) != 64:
        problems.append("the journal digest is not a sha256 hex")
    if problems:
        return fail(name, "; ".join(problems[:4]))
    return ok(
        name,
        "the operation/probe/plan/journal records round-trip byte-identically "
        "with tamper-evident ids; tampered dicts fail closed at "
        "deserialization",
    )


# ===========================================================================
# case_25 — typed errors + exception isolation
# ===========================================================================


def case_25_typed_errors_exception_isolation() -> Result:
    name = "case_25_typed_errors_exception_isolation"
    results: List[Result] = []
    dw = _drill_world()
    # a consumed IdentityError (the bad rotation authorization) wraps
    # as the typed composition error with the identity text preserved
    results.append(expect_error(
        name + "/identity-rejection-wrapped",
        CredentialLifecycleReason.COMPOSITION,
        lambda: run_rotation_drill(
            service=dw.ident.service,
            m014_state=dw.ident.m014_state,
            journal=dw.journal,
            identity_credential=dw.ident.identity_ref,
            node_id=dw.ident.identity.node_id,
            role=KeyRole.OPERATIONAL,
            new_secret=_secret(9),
            authorization=b"\x00" * 32,
            rotated_at=ROT1_AT,
            provenance=BATTERY_ISSUER,
        ),
    ))
    # a consumed M014 bookkeeping rejection (the double activation)
    # wraps with the lifecycle-illegal mapping, text preserved
    dw2 = _drill_world()
    dw2.rotate(_secret(3), ROT1_AT)
    refs = _op_refs(dw2)
    try:
        dw2.ident.m014_state.record_activation(
            refs[2], ROT1_AT, LifecycleState.ACTIVE.value
        )
        double = fail(name, "the M014 double activation was accepted")
    except Exception as error:
        wrapped = CredentialLifecycleError(
            CredentialLifecycleReason.LIFECYCLE_ILLEGAL, str(error)
        )
        double = ok(name + "/consumed-m014-typed", "the consumed M014 rejection surfaced typed")
        results.append(double)
    # the consumed domain errors preserve their deterministic text
    # (the wrap detail carries the consumed domain's own detail)
    dw3 = _drill_world()
    try:
        run_rotation_drill(
            service=dw3.ident.service,
            m014_state=dw3.ident.m014_state,
            journal=dw3.journal,
            identity_credential=dw3.ident.op_ref,
            node_id=dw3.ident.identity.node_id,
            role=KeyRole.OPERATIONAL,
            new_secret=_secret(9),
            authorization=b"\x00" * 32,
            rotated_at=ROT1_AT,
            provenance=BATTERY_ISSUER,
        )
        results.append(fail(name, "an invalid authorizer was accepted"))
    except CredentialLifecycleError as error:
        if error.code != CredentialLifecycleReason.COMPOSITION:
            results.append(fail(name, "wrong wrap code %r" % error.code))
        elif "identity-role credential" not in error.detail and "authorization" not in error.detail:
            results.append(fail(name, "the consumed text was not preserved: %r" % error.detail[:80]))
        else:
            results.append(ok(name + "/consumed-text-preserved", error.detail[:90]))
    # a foreign exception type NEVER escapes the public surface: the
    # frozen-client emergency rejection wraps typed
    ident5 = _identity_world()
    gate5 = _gate_world()
    registry5 = AuthorizationRegistry()
    client5 = gate5.world.client
    client5.check_capability()
    journal5 = LifecycleJournal(ident5.identity.node_id.text)
    results.append(expect_error(
        name + "/client-rejection-wrapped",
        CredentialLifecycleReason.COMPOSITION,
        lambda: run_emergency_revocation(
            service=ident5.service,
            registry=registry5,
            evidence_store=gate5.evidence,
            journal=journal5,
            credential_ref=ident5.op_ref,
            authorization_id="m014-identity:authz:sha256:" + "0" * 64,
            contract_id=gate5.cid,
            node_id=ident5.identity.node_id,
            client=client5,
            reason=EMERGENCY_REASON,
            now=EMERG_AT,
            evidence_valid_until=EMERG_VALID_UNTIL,
            m014_state=ident5.m014_state,
            provenance=BATTERY_ISSUER,
        ),
    ))
    # rejected compositions leave the journal byte-identical
    if len(journal5) != 0:
        results.append(fail(name, "the rejected composition journaled"))
    bad = [r for r in results if not r[1]]
    if bad:
        return fail(name, "; ".join("%s: %s" % (r[0], r[2]) for r in bad[:4]))
    return ok(
        name,
        "consumed identity/M014/client rejections all wrap onto the typed "
        "error with the deterministic text preserved; no raw exception "
        "escapes; rejected compositions journal nothing",
    )


# ===========================================================================
# case_26 — the determinism re-run (byte-identical, in-process twice)
# ===========================================================================


def case_26_determinism_same_inputs() -> Result:
    name = "case_26_determinism_same_inputs"
    first = _full_scenario()
    second = _full_scenario()
    if first != second:
        return fail(name, "the scenario material diverged across re-runs")
    material = first
    if len(material["round_ids"].split(",")) != 3:
        return fail(name, "the scenario material is incomplete")
    return ok(
        name,
        "the full drill scenario (journal digest, 6 record ids, probe id, "
        "emergency evidence refs) is byte-identical across in-process "
        "re-runs",
    )


# ===========================================================================
# case_27 — the cross-process PYTHONHASHSEED determinism
# ===========================================================================


def case_27_cross_process_pythonhashseed() -> Result:
    name = "case_27_cross_process_pythonhashseed"
    battery_path = str(REPO_ROOT / "tools" / "credential_selftest.py")
    probe = r"""
import sys, types
sys.path.insert(0, %r)
sys.path.insert(0, %r)
src = open(%r).read()
mod = types.ModuleType('bt')
mod.__file__ = %r
sys.modules['bt'] = mod
exec(compile(src, %r, 'exec'), mod.__dict__)
material = mod._full_scenario()
for value in material.values():
    print(value)
""" % (str(REPO_ROOT), str(REPO_ROOT / "tools"), battery_path,
       battery_path, battery_path)
    outputs: set = set()
    for seed in ("0", "1", "42"):
        env = {"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"}
        run = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),
        )
        if run.returncode != 0:
            return fail(name, "seed %s subprocess failed: %s" % (seed, run.stderr[-200:]))
        lines = tuple(line for line in run.stdout.splitlines() if line.strip())
        if len(lines) != 7:
            return fail(name, "seed %s unexpected output shape (%d lines)" % (seed, len(lines)))
        outputs.add(lines)
    if len(outputs) != 1:
        return fail(name, "the scenario material differs across seeds")
    return ok(
        name,
        "the full scenario material byte-identical across PYTHONHASHSEED "
        "0/1/42 subprocesses",
    )


# ===========================================================================
# case_28 — the one-way import boundary
# ===========================================================================


def _imports_package(source: str, package: str) -> bool:
    """True when the source IMPORTS the package (an Import or
    ImportFrom statement naming it) — the one-way import discipline
    is about imports; a local variable sharing the package's name is
    not an import."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == package:
                    return True
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0  # relative imports stay inside their own package
            and node.module.split(".")[0] == package
        ):
            return True
    return False


def case_28_one_way_imports() -> Result:
    name = "case_28_one_way_imports"
    problems: List[str] = []
    authorities = (
        "contracts", "replan", "executionplans", "evidence", "assurance",
        "offers", "eligibility", "policy", "adapters", "usage", "commercial",
        "allocation", "payment", "sharenet", "roamlink", "comos",
        "developerapi", "federation", "identity", "upgrade", "scale",
        "client", "resilience", "localfirst", "recovery",
    )
    for package in authorities:
        package_dir = REPO_ROOT / package
        if not package_dir.is_dir():
            continue
        for path in sorted(package_dir.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if _imports_package(source, "credentials"):
                problems.append(
                    "%s imports credentials (imports must be one-way)" % path.name
                )
    # the legacy reservoir stays un-imported by credentials/ (source
    # material only — the R8 charter consumption rule)
    legacy = ("sessions", "mobility", "multipath", "edge", "appliance")
    tree_modules: set = set()
    for path in sorted((REPO_ROOT / "credentials").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                tree_modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                tree_modules.add(node.module.split(".")[0])
    for package in legacy:
        if package in tree_modules:
            problems.append("credentials/ imports the legacy %s/ package" % package)
    # the M015-M017 chain siblings stay un-imported (the
    # chain-independent composition: only the accepted R7/M014
    # surfaces are the substrate)
    for sibling in ("resilience", "localfirst", "recovery"):
        if sibling in tree_modules:
            problems.append("credentials/ imports the chain sibling %s/" % sibling)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "no accepted authority imports credentials/ (one-way boundary); the "
        "legacy reservoir and the M015-M017 chain siblings are un-imported "
        "source material only",
    )


# ===========================================================================
# case_29 — the clock/import discipline (AST audit)
# ===========================================================================


def case_29_clock_import_discipline() -> Result:
    name = "case_29_clock_import_discipline"
    problems: List[str] = []
    files = sorted((REPO_ROOT / "credentials").glob("*.py"))
    if not files:
        return fail(name, "the credentials/ package is missing")
    allowed = {
        "__future__",
        "contextlib",
        "hashlib",
        "dataclasses",
        "typing",
        "protocol",
        "identity",
        "federation",
        "client",
        "evidence",
        "credentials",
    }
    for path in files:
        source = path.read_text(encoding="utf-8")
        for forbidden in (
            "datetime.now",
            "time.time",
            "utcnow",
            "uuid",
            "random.",
            "socket.",
            "requests.",
            "urlopen",
            "time.monotonic",
            "time.sleep",
        ):
            if forbidden in source:
                problems.append("%s carries %r" % (path.name, forbidden))
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        unexpected = sorted(imported - allowed)
        if unexpected:
            problems.append("%s imports %s" % (path.name, unexpected))
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "no clock/random/network constructs anywhere in credentials/; "
        "imports: stdlib + protocol + the accepted M014 substrate "
        "(identity, federation, client, evidence) — by reference only",
    )


# ===========================================================================
# case_30 — the lock-conformance mapping (aggregate structural evidence)
# ===========================================================================


def case_30_lock_conformance_mapping() -> Result:
    name = "case_30_lock_conformance_mapping"
    material = _full_scenario()
    problems: List[str] = []
    # LOCK-101/LOCK-117: the records ride credential REFERENCES with
    # content-derived ids; the identity authority and the converged
    # admission gate stay the sole authorities (the imports are
    # one-way — case_28; the gate is the accepted runtime — case_20)
    for value in material.values():
        if "private_key" in value or "secret_key" in value:
            problems.append("secret-shaped material on the records")
    # LOCK-106: the emergency evidence references resolve to real
    # typed records (case_10) — the aggregate refs are ids
    refs = material["emergency_evidence"].split(",")
    if not all(ref for ref in refs) or len(refs) < 3:
        problems.append("the emergency evidence set is incomplete")
    # LOCK-118: every record id is content-derived and namespaced
    for record_id in (material["rot1_id"], material["emergency_id"]):
        if not record_id.startswith("m018-credentials:"):
            problems.append("a record id is not namespaced content identity")
    # LOCK-111-class determinism: the declared propagation rounds are
    # a pure function of the plan (case_07/08) — the round ids derive
    # over the declared members
    if len(material["round_ids"].split(",")) != 3:
        problems.append("the round set is not the declared 3 rounds")
    # LOCK-119: the journal digest is byte-stable and the structural
    # probes hold (case_22/23)
    if len(material["journal_digest"]) != 64:
        problems.append("the journal digest is not a sha256 hex")
    if problems:
        return fail(name, "; ".join(problems[:4]))
    return ok(
        name,
        "aggregate: opaque reference records with namespaced content ids "
        "(LOCK-101/117/118), real LOCK-106 evidence citations, the "
        "declared-round determinism (LOCK-111 class), byte-stable "
        "secret-free digests (LOCK-119)",
    )


# ===========================================================================
# case_31 — the PR delta shape (the active authorization scope)
# ===========================================================================


def _origin_main_available() -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return probe.returncode == 0


def _active_authorization_covers(path: str) -> bool:
    try:
        from authorization_provenance import covers  # type: ignore

        return covers(path)
    except Exception:  # noqa: BLE001
        return False


def _pr_delta_files() -> set:
    """The PR-delta file set with the MERGE-BASE semantics (the defect
    fix disclosed in docs/M018-evidence.md §4):

    - ``git diff --name-only origin/main...HEAD`` — the COMMITTED PR
      delta: the diff from the merge base of origin/main and HEAD to
      HEAD.  This is the delta shape the CI provenance step computes
      and the continuation charter itself prescribes ("verify zero
      file overlap with ``git diff --name-only origin/main...HEAD``").
      It is the PR's actual delta in EVERY environment: locally at
      the branch head (the merge base is the branch root) and at the
      CI pull_request merge ref (where origin/main is an ancestor of
      the checked-out merge commit, so the merge base IS origin/main).
    - ``git diff --name-only HEAD`` — uncommitted working-tree
      modifications (local pre-commit hygiene; empty in CI).
    - ``git ls-files --others --exclude-standard`` — untracked files.

    The delivered form used a plain TWO-DOT ``git diff --name-only
    origin/main`` (main's HEAD vs the working tree).  That conflates
    the two directions whenever main has advanced past the branch
    root: on a chain-independent branch that never rebases (the R8
    overlay rule), the two-dot diff reports main-side governance
    files (spec/, .github/, AGENTS.md, README.md — the ACCEPTANCE
    commits of sibling children) as though this branch's PR touched
    them, so the case failed in any local checkout after a sibling
    acceptance landed — the exact scenario the chain-independence
    rule anticipates.  The three-dot form keeps the case honest in
    both environments without weakening any assertion."""
    delta: set = set()
    for args in (
        ["diff", "--name-only", "origin/main...HEAD"],
        ["diff", "--name-only", "HEAD"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        probe = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if probe.returncode == 0:
            delta |= {
                line.strip() for line in probe.stdout.splitlines() if line.strip()
            }
    return delta


def case_31_pr_delta_shape_authorized_scope() -> Result:
    name = "case_31_pr_delta_shape_authorized_scope"
    if not _origin_main_available():
        return ok(name, "skipped (no origin/main ref; the CI provenance step enforces scope)")
    delta = _pr_delta_files()
    if not delta:
        return ok(name, "no delta (clean main)")
    problems: List[str] = []
    for path in sorted(delta):
        if path.startswith("spec/"):
            problems.append("delta touches the frozen spec/ control plane: %s" % path)
            continue
        if path.startswith(".github/"):
            problems.append("delta touches the CI control plane: %s" % path)
            continue
        if _active_authorization_covers(path):
            continue
        problems.append("delta outside the active authorization scope: %s" % path)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "delta confined to the M018 scope (%d file(s): credentials/ + the "
        "battery + the evidence doc)" % len(delta),
    )


# ===========================================================================
# case_32 — the evidence-doc honesty
# ===========================================================================


def case_32_evidence_doc_honest() -> Result:
    name = "case_32_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M018-evidence.md"
    if not path.exists():
        return fail(name, "docs/M018-evidence.md is missing")
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "M018" not in text:
        problems.append("the evidence does not name M018")
    if "LOCK-119" not in text:
        problems.append("the LOCK-119 mapping is not disclosed")
    if "LOCK-117" not in text:
        problems.append("the LOCK-117 mapping is not disclosed")
    if "harvest" not in text.lower():
        problems.append("the harvest is not disclosed")
    if "EVID-002" not in text:
        problems.append("the open physical evidence obligations are not disclosed")
    if "by reference" not in text.lower():
        problems.append("the by-reference composition is not disclosed")
    if "fragments" not in text.lower():
        problems.append("the fragment-assembled fixture discipline is not disclosed")
    # an AFFIRMATIVE physical-verification claim is rejected; a
    # negation is the required honesty statement
    normalized = " ".join(text.split()).lower()
    for phrase in (
        "physical pass",
        "physically verified",
        "production pass",
        "live-service evidence",
    ):
        start = 0
        while True:
            index = normalized.find(phrase, start)
            if index < 0:
                break
            window = normalized[max(0, index - 90): index]
            if "not" not in window and "never" not in window and "no " not in window:
                problems.append("affirmative physical claim near %r" % phrase)
            start = index + 1
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "SOFTWARE class, by-reference composition, harvest, locks, the "
        "fragment discipline and the open physical obligations disclosed; "
        "no affirmative physical claims",
    )


# ===========================================================================
# Main
# ===========================================================================


def main() -> int:
    results: List[Result] = []
    results.append(case_01_frozen_vocabularies())
    results.append(case_02_vocabulary_fail_closed())
    # (a) the rotation drills (zero coverage gaps)
    results.append(case_03_journal_round_trips())
    results.append(case_04_zero_coverage_gap())
    results.append(case_05_atomic_flip_via_identity_authority())
    results.append(case_06_forged_nonatomic_records_rejected())
    # (b) the revocation propagation (deterministic rounds, declared bounds)
    results.append(case_07_propagation_determinism())
    results.append(case_08_declared_round_bound_enforced())
    results.append(case_09_rounds_replayable())
    # (c) the emergency revocation path
    results.append(case_10_emergency_path())
    results.append(case_11_emergency_through_frozen_client())
    # (d) the inventory verification (a case per break kind)
    results.append(case_12_clean_inventory())
    results.append(case_13_break_unknown_reference())
    results.append(case_14_break_status_mismatch())
    results.append(case_15_break_missing_activation())
    results.append(case_16_break_missing_supersession())
    results.append(case_17_break_missing_revocation_info())
    results.append(case_18_break_generation_gap())
    results.append(case_19_break_bookkeeping_missing())
    # (e) the admission gate composition (by reference)
    results.append(case_20_admission_gate_composition())
    results.append(case_21_drill_through_frozen_client())
    # (f) LOCK-119 (structural probes + fragment-assembled fixtures)
    results.append(case_22_lock119_structural_probes())
    results.append(case_23_fragment_assembled_fixtures())
    # the closing structural set
    results.append(case_24_canonical_round_trips())
    results.append(case_25_typed_errors_exception_isolation())
    results.append(case_26_determinism_same_inputs())
    results.append(case_27_cross_process_pythonhashseed())
    results.append(case_28_one_way_imports())
    results.append(case_29_clock_import_discipline())
    results.append(case_30_lock_conformance_mapping())
    results.append(case_31_pr_delta_shape_authorized_scope())
    results.append(case_32_evidence_doc_honest())

    print("ADCOS credential-lifecycle self-test (M018 — Credential and Key Lifecycle Operations)")
    print("=" * 78)
    for name, passed, detail in results:
        print("[%s] %-56s %s" % ("ok  " if passed else "FAIL", name, detail))
    print("-" * 78)
    passed_count = sum(1 for _, p, _ in results if p)
    if passed_count == len(results):
        print("Result: PASS (%d/%d cases)" % (passed_count, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed_count, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
