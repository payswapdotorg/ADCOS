#!/usr/bin/env python3
"""ADCOS provider/buyer client convergence battery (M014 — the
DEC-0099 re-baseline; R7-CORE-001, DEC-0101).

THE RE-BASELINE (visible, never silent — the DEC-0099 disclosure):
the previous era of this battery verified the W049 client runtime
against the W048 containment/sharing machinery
(``containment.CapabilityMatrix``, the sharing runtime), whose
subject material is WORK-048 — ACCEPTED-NOT-RESTORED under the
Architecture 1.1 migration policy.  It crashed on import at the
M009-era baseline (the CI workflow still carries the disclosed
DEC-0099 containment-guard on its step) and was carried as the
sole documented skip.  THIS battery is the honest convergence
baseline promised by that disclosure: the frozen WORK-049 client
code — ``ProviderClient`` / ``ClientRuntime`` / the gateway read
window / the privacy-bounded presentation — imported BY REFERENCE,
UNCHANGED (byte-identical to origin/main, verified in case_20),
and driven over the CONVERGED Architecture 1.1 authorities through
``client/convergence.py`` (the M014 composition):

- **contracts/** (M002) — the canonical commercial record: the
  lease read IS the CONTRACT read; the authorization lease gate is
  the contract's own lease lifecycle; the emergency stop drives
  the store's OWN ``RevokeLease`` command (LOCK-101);
- **offers/** (M003) — the canonical economic terms resolved
  through the REAL ``OfferExchange`` at read time (P1-2: no
  caller-supplied economics, ever; unknown economics refuse the
  consent presentation fail-closed);
- **evidence/** (M005) — the consent record as REAL typed
  ``AttestationEvidence`` (pending -> granted -> withdrawn, one
  immutable controller-verified record per transition —
  LOCK-106/118);
- **federation/** (M014) — the converged authorization authority
  (``ConvergedAuthorizationRuntime``): the lease gate, the consent
  attestation stream, the LOCK-117 rate gate and the declared
  authorization-scope quota;
- the frozen W049 duck-typed protocol (prepare/grant/authorize/
  activate/pause/resume/withdraw/emergency-stop/close/notify-path-
  lost/account-traffic/session/consent) delegated 1:1 — never
  reimplemented, never weakened.

WORK-048 STAYS ACCEPTED-NOT-RESTORED (the charter's migration
policy; verified structurally in case_17): no containment
primitive, no traffic-isolation authority, no buyer-traffic
enforcement exists anywhere in this composition — the converged
admission gate is the canonical lease + the consent attestation +
the declared quota, and the buyer-side purchase chain stays with
its own frozen seams.

Also exercised: the converged citation surface (the by-reference
``ChildCitation`` set over the REAL child records — contracts,
offers, evidence, adapter capability views, execution plans, the
commercial/vertical-proof seams — each digesting the cited
record's OWN canonical bytes), the per-domain citation ledger with
the pending -> propagated -> confirmed revocation discipline, the
deterministic fixed-window rate-limit surface, canonical
round-trips, tamper evidence, LOCK-119 discipline, PYTHONHASHSEED
cross-process determinism, the frozen-core byte-identity audit,
and the PR-delta authorization coverage.

Deterministic, offline, seeded: injected instants only (no wall
clock, no randomness, no UUIDs, no network, no secrets —
LOCK-119); content-derived ids over canonical JSON; sorted
iteration; typed fail-closed errors with stable codes;
exit-code-based verification.  All evidence produced here is
SOFTWARE class only — no PHYSICAL PASS is claimed or implied
(EVID-002..EVID-008 stay open; W040's physical obligations stay
W040-owned).

Usage:
    python3 tools/client_selftest.py
    python3 tools/client_selftest.py --determinism-stream
"""

from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
_TOOLS = os.path.join(REPO_ROOT, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from protocol.canonicalization import canonical_json_bytes  # noqa: E402

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
from evidence import AttestationEvidence, EvidenceStore  # noqa: E402
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
    resolve_offer_reference,
)
from adapters import CapabilityView  # noqa: E402
from executionplans import SegmentInput, translate_contract  # noqa: E402

from federation.convergence import (  # noqa: E402
    CITATION_KINDS,
    CONSENT_STATES,
    CONVERGENCE_AUTHORITIES,
    RATE_LIMIT_OPERATIONS,
    SESSION_STATES,
    SESSION_TERMINAL_STATES,
    SESSION_TRANSITIONS,
    VERTICAL_PROOF_KINDS,
    AuthorizationScope,
    ChildCitation,
    CitationRevocation,
    ConvergenceError,
    ConvergenceReasonCode,
    DomainCitationLedger,
    RateLimitPolicy,
    RateLimitState,
    check_rate_limit,
    citation_revocation,
    cite_adapter_capability,
    cite_contract,
    cite_evidence_record,
    cite_execution_plan,
    cite_offer,
    cite_replan_decision,
    cite_settlement_reference,
    cite_vertical_proof,
    derive_citation_id,
    peer_evidence_from_citation,
)
from client import (  # noqa: E402
    ClientError,
    ClientReasonCode,
    FailClosedResolution,
    Freshness,
    ProviderClientState,
    SandboxPlatformAdapter,
)
from client.convergence import (  # noqa: E402
    CLIENT_CONVERGENCE_PREFIX,
    CONSENT_SCOPE_DIMENSIONS,
    CONVERGED_READ_AUTHORITIES,
    UNWIRED_READ_AUTHORITIES,
    ClientConvergenceError,
    ClientConvergenceReasonCode,
    ConvergedConsentScope,
    ConvergedSessionView,
    ConvergedSharingRuntime,
    build_converged_provider_client,
    consent_scope_from_declared,
    converged_client_citations,
)

Result = Tuple[str, bool, str]

T0 = "2027-01-15T00:00:00Z"
T1H = "2027-01-15T01:00:00Z"
T2H = "2027-01-15T02:00:00Z"
T25H = "2027-01-16T01:00:00Z"
T_END = "2027-02-15T00:00:00Z"
CREATE_AT = "2027-01-14T10:00:00Z"
PROVIDER = "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 64
PLATFORM = "platform:router-01"
BUYER = "app:sharenet-gw-01"
DEVICE = "dev:router-01"
APPLICATION = "app:gw-01"


def ok(name: str, detail: str) -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def expect_typed(
    case: str,
    error_type: type,
    code: str,
    action: Callable[[], Any],
) -> Result:
    """One typed fail-closed expectation (stable code)."""
    try:
        action()
    except error_type as error:
        actual = getattr(error, "code", None) or getattr(error, "reason", "")
        if str(actual) == code:
            return ok(case, "fail-closed %s" % code)
        return fail(
            case, "expected %s, got %r (%s)"
            % (code, actual, str(error)[:80])
        )
    except Exception as error:  # noqa: BLE001
        return fail(
            case, "unexpected %s: %s" % (type(error).__name__, str(error)[:80])
        )
    return fail(case, "expected %s(%s); the input was accepted" % (
        error_type.__name__, code,
    ))


def expect_client_error(
    case: str, reason: str, resolution: str, action: Callable[[], Any]
) -> Result:
    """One frozen-client typed denial expectation (reason + resolution)."""
    try:
        action()
    except ClientError as error:
        actual_reason = str(getattr(error, "reason", "") or "")
        actual_resolution = str(getattr(error, "resolution", "") or "")
        if actual_reason == reason and actual_resolution == resolution:
            return ok(case, "fail-closed %s/%s" % (reason, resolution))
        return fail(
            case, "expected %s/%s, got %s/%s (%s)"
            % (reason, resolution, actual_reason, actual_resolution,
               str(error)[:70])
        )
    except Exception as error:  # noqa: BLE001
        return fail(
            case, "unexpected %s: %s" % (type(error).__name__, str(error)[:80])
        )
    return fail(case, "expected ClientError(%s/%s); accepted" % (
        reason, resolution,
    ))


# ---------------------------------------------------------------------------
# The deterministic injected clock (the ONLY time source)
# ---------------------------------------------------------------------------


class StepClock:
    """The injected deterministic clock seam (never a wall clock)."""

    def __init__(self, start: str, step_seconds: int = 3600) -> None:
        self._instant = start
        self._step = step_seconds

    def now(self) -> str:
        return self._instant

    def advance(self, steps: int = 1) -> str:
        from datetime import timedelta

        from protocol.temporal import parse_instant

        base = parse_instant(self._instant)
        self._instant = (
            base + timedelta(seconds=self._step * steps)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self._instant


def _prov(issuer: str, *refs: str) -> Provenance:
    return Provenance(issuer=issuer, decision_refs=tuple(refs))


# ---------------------------------------------------------------------------
# The converged world builder (REAL authorities only)
# ---------------------------------------------------------------------------


@dataclass
class _World:
    world: Any
    cid: str
    offer_ref: Any
    offer: Any


def _build(
    *,
    offer_not_after: str = T_END,
    lease_not_after: str = T_END,
    select_offers: bool = True,
    grant_lease: bool = True,
    activate_contract: bool = True,
    scope_until: str = T_END,
    byte_quota: int = 1_000_000,
    rate_policy: Any = None,
    clock_start: str = T0,
) -> _World:
    """Build one fresh converged provider world over REAL authorities
    (a REAL M002 contract store with a lease, a REAL M003 exchange
    with a registered offer, a REAL M005 evidence store, the frozen
    W049 sandbox adapter, the injected clock, and the composition
    root)."""
    exchange = OfferExchange()
    advertisement = build_advertisement(
        provider=PROVIDER,
        entries=(AdvertisementEntry(
            capability_id="capability.core.multipath",
            schema_version="1.2",
            statement_digest="sha256:" + "a" * 64,
            classification="known",
        ),),
        validity=ValidityInterval(not_before=T0, not_after=offer_not_after),
        provenance=_prov(PROVIDER),
    )
    offer = build_offer(
        provider=PROVIDER,
        provider_offer_key="offer:netpro-basic-1",
        schema_version=1,
        advertisements=(AdvertisementRef(
            advertisement_id=advertisement.advertisement_id,
            provenance=_prov(PROVIDER),
        ),),
        commitments=(OfferCommitment(
            kind="latency-bound-ms",
            params={"max_ms": 150},
            window=ValidityInterval(not_before=T0, not_after=offer_not_after),
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
        validity=ValidityInterval(not_before=T0, not_after=offer_not_after),
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
            beneficiary_kind="DEVICE", beneficiary_ref="dev:pi-7f2a",
        ),),
        requirements=(OpaqueReference(
            ref_kind="intent-requirements", value="intent:abc123",
            provenance=_prov("arch:sharenet"),
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
        provenance=_prov("arch:sharenet", "dec:elig-1"),
    ), recorded_at=CREATE_AT)
    cid = created.contract.contract_id
    if select_offers:
        store.submit(
            SelectOffers(offers=(offer_ref,)),
            recorded_at="2027-01-14T10:05:00Z", contract_id=cid,
        )
    if grant_lease:
        store.submit(
            GrantLease(granted_at=CREATE_AT, not_before=T0,
                       not_after=lease_not_after),
            recorded_at=CREATE_AT, contract_id=cid,
        )
    if activate_contract:
        store.submit(
            ActivateContract(
                activated_at=T0,
                signature_refs=(OpaqueReference(
                    ref_kind="signature", value="sig:ed25519-1",
                ),),
            ),
            recorded_at=T0, contract_id=cid,
        )
        store.submit(
            RecordExecutionActivation(recorded_at=T0),
            recorded_at=T0, contract_id=cid,
        )

    estore = EvidenceStore()
    clock = StepClock(clock_start)
    scope = AuthorizationScope(
        exposed_egress=("egress:internet-via-provider",),
        byte_quota=byte_quota,
        valid_until=scope_until,
        max_concurrent_sessions=2,
    )
    adapter = SandboxPlatformAdapter(
        platform_id=PLATFORM,
        provider_support="supported",
        buyer_support="supported",
    )
    world = build_converged_provider_client(
        store=store,
        evidence=estore,
        exchange=exchange,
        adapter=adapter,
        clock=clock,
        scope=scope,
        user_ref=PROVIDER,
        device_ref=DEVICE,
        application_ref=APPLICATION,
        platform_id=PLATFORM,
        rate_policy=rate_policy,
    )
    return _World(world=world, cid=cid, offer_ref=offer_ref, offer=offer)


def _ready(world: Any) -> None:
    """Take the frozen client through the capability gate to READY."""
    world.client.check_capability()
    world.client.become_ready()


def _prepare(world: Any, cid: str, session_ref: str = "sess:logical-1") -> Any:
    """Drive the canonical prepare through the frozen client."""
    return world.client.prepare_sharing(
        lease_ref=cid, buyer_ref=BUYER, provider_ref=PROVIDER,
        session_ref=session_ref, path_ref="path:w41-1",
        scope=world.scope,
    )


def _active(world: Any, cid: str, session_ref: str = "sess:logical-1") -> str:
    """Drive the frozen client to local ACTIVE (canonical active)."""
    _ready(world)
    _prepare(world, cid, session_ref=session_ref)
    world.client.grant_consent()
    world.client.request_handoff()
    world.client.activate()
    return world.client.sharing_session_id


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# 01: the frozen vocabularies
# ---------------------------------------------------------------------------


def case_01_frozen_vocabularies() -> Result:
    name = "case_01_frozen_vocabularies"
    checks: Dict[str, bool] = {
        "authorities": CONVERGENCE_AUTHORITIES == (
            "contracts", "offers", "executionplans", "adapters", "replan",
            "commercial", "evidence", "assurance", "vertical-proof",
        ),
        "citation kinds": CITATION_KINDS == {
            "contracts": ("connectivity-contract",),
            "offers": ("provider-offer",),
            "executionplans": ("execution-plan",),
            "adapters": ("adapter-capability",),
            "replan": ("replan-decision",),
            "commercial": ("settlement-reference",),
            "evidence": ("evidence-record",),
            "assurance": ("assurance-evaluation",),
            "vertical-proof": ("vertical-proof",),
        },
        "vertical proofs": VERTICAL_PROOF_KINDS == (
            "sharenet", "roamlink", "comos",
        ),
        "session states": SESSION_STATES == (
            "prepared", "authorized", "active", "paused", "degraded",
            "revoked", "expired", "closed",
        ),
        "session terminals": SESSION_TERMINAL_STATES == (
            "revoked", "expired", "closed",
        ),
        "closed terminal": SESSION_TRANSITIONS["closed"] == frozenset(),
        "consent states": CONSENT_STATES == (
            "pending", "granted", "withdrawn",
        ),
        "rate operations": RATE_LIMIT_OPERATIONS == (
            "prepare", "authorize", "activate", "account",
        ),
        "read authorities": CONVERGED_READ_AUTHORITIES == (
            "sharing", "commercial",
        ),
        "unwired authorities": UNWIRED_READ_AUTHORITIES == (
            "networkpath", "usage",
        ),
        "scope dimensions": CONSENT_SCOPE_DIMENSIONS == (
            "exposed_egress", "time_quota_expiry", "byte_quota",
            "max_concurrent_buyers",
        ),
        "client prefix": CLIENT_CONVERGENCE_PREFIX == "m014-client",
        "conv reasons": sorted((
            ConvergenceReasonCode.INVALID_INPUT,
            ConvergenceReasonCode.VOCABULARY,
            ConvergenceReasonCode.TEMPORAL_INVALID,
            ConvergenceReasonCode.SECRET_REJECTED,
            ConvergenceReasonCode.NOT_FOUND,
            ConvergenceReasonCode.LIFECYCLE_ILLEGAL,
            ConvergenceReasonCode.LEASE_NOT_ACTIVE,
            ConvergenceReasonCode.LEASE_EXPIRED,
            ConvergenceReasonCode.CONSENT_REQUIRED,
            ConvergenceReasonCode.QUOTA_EXCEEDED,
            ConvergenceReasonCode.RATE_LIMITED,
            ConvergenceReasonCode.ID_MISMATCH,
            ConvergenceReasonCode.REVOCATION_INVALID,
            ConvergenceReasonCode.EVIDENCE_REJECTED,
        )) == sorted((
            "invalid-input", "vocabulary", "temporal-invalid",
            "secret-rejected", "not-found", "lifecycle-illegal",
            "lease-not-active", "lease-expired", "consent-required",
            "quota-exceeded", "rate-limited", "id-mismatch",
            "revocation-invalid", "evidence-rejected",
        )),
        "client conv reasons": sorted((
            ClientConvergenceReasonCode.INVALID_INPUT,
            ClientConvergenceReasonCode.VOCABULARY,
            ClientConvergenceReasonCode.SECRET_REJECTED,
            ClientConvergenceReasonCode.TEMPORAL_INVALID,
            ClientConvergenceReasonCode.NOT_FOUND,
            ClientConvergenceReasonCode.AUTHORITY_REJECTED,
            ClientConvergenceReasonCode.COMPOSITION_INVALID,
        )) == sorted((
            "invalid-input", "vocabulary", "secret-rejected",
            "temporal-invalid", "not-found", "authority-rejected",
            "composition-invalid",
        )),
    }
    missing = [label for label, held in checks.items() if not held]
    if missing:
        return fail(name, "vocabulary drift: %s" % missing)
    return ok(name, "the converged + frozen-W049 vocabularies byte-frozen (%d checks)"
              % len(checks))


# ---------------------------------------------------------------------------
# 02: the full frozen provider lifecycle over the converged authority
# ---------------------------------------------------------------------------


def case_02_full_lifecycle_over_converged_authority() -> Result:
    name = "case_02_full_lifecycle"
    built = _build()
    world, cid = built.world, built.cid
    if str(world.store.contract(cid).state) != "EXECUTION_ACTIVE":
        return fail(name, "the REAL contract is not EXECUTION_ACTIVE")
    snapshot = world.client.check_capability()
    if world.client.capability_decision != "ALLOWED":
        return fail(name, "capability decision %r (sandbox adapter is supported)"
                    % world.client.capability_decision)
    if snapshot.platform_id != PLATFORM:
        return fail(name, "capability snapshot platform mismatch")
    world.client.become_ready()
    if str(world.client.state) != ProviderClientState.READY:
        return fail(name, "not READY after become_ready")
    facts = _prepare(world, cid)
    checks = {
        "what_is_shared": facts.what_is_shared == (
            "egress:internet-via-provider",),
        "duration": facts.duration_until == T_END,
        "buyer scope": facts.buyer_scope == (BUYER,),
        "quota": facts.quota_bytes == 1_000_000,
        "max buyers": facts.max_concurrent_buyers == 2,
        "stop control": facts.immediate_stop_control is True,
        "actual state": facts.current_actual_state == "prepared",
        "source refs": facts.canonical_source_refs == (
            "sharing:%s" % world.client.sharing_session_id,
            "commercial:%s" % cid,
        ),
        "client state": str(world.client.state)
        == ProviderClientState.CONSENT_REQUIRED,
    }
    missing = [label for label, held in checks.items() if not held]
    if missing:
        return fail(name, "consent facts drifted: %s" % missing)
    world.client.grant_consent()
    if str(world.client.state) != ProviderClientState.CONSENTED:
        return fail(name, "not CONSENTED after the canonical grant")
    world.client.request_handoff()
    if str(world.client.state) != ProviderClientState.HANDOFF_REQUESTED:
        return fail(name, "not HANDOFF_REQUESTED after the canonical authorize")
    world.client.activate()
    if str(world.client.state) != ProviderClientState.ACTIVE:
        return fail(name, "not ACTIVE after the canonical activation")
    status = world.client.refresh_status()
    if (status.state != "active"
            or str(status.freshness) != Freshness.CANONICAL_STATE):
        return fail(name, "refresh gave %r/%r (canonical active expected)"
                    % (status.state, status.freshness))
    view = world.authority.account_traffic(
        world.client.sharing_session_id, 1_000,
    )
    if view.bytes_admitted != 1_000 or view.state != "active":
        return fail(name, "traffic admission not accounted canonically")
    world.client.pause()
    if str(world.client.state) != ProviderClientState.PAUSED:
        return fail(name, "not PAUSED after the canonical pause")
    world.client.resume()
    if str(world.client.state) != ProviderClientState.ACTIVE:
        return fail(name, "not ACTIVE after the canonical resume")
    world.client.notify_path_lost()
    canonical = world.authority.session(world.client.sharing_session_id)
    if canonical.state != "degraded":
        return fail(name, "canonical session not degraded after path loss")
    if str(world.client.state) != ProviderClientState.ACTIVE:
        return fail(name, "local projection drifted on the path-loss report")
    recovered = world.authority.resume_sharing_session(
        world.client.sharing_session_id,
    )
    if recovered.state != "active":
        return fail(name, "authority-side recovery did not restore active")
    observed = world.client.refresh_status()
    if observed.state != "active":
        return fail(name, "the client did not observe the recovered truth")
    return ok(name, "the frozen provider lifecycle (UNAVAILABLE -> READY "
              "-> CONSENT_REQUIRED -> CONSENTED -> HANDOFF_REQUESTED -> "
              "ACTIVE <-> PAUSED, degraded observed) green over the "
              "converged 1.1 authorities")


# ---------------------------------------------------------------------------
# 03: the consent presentation is canonically sourced (P1-2)
# ---------------------------------------------------------------------------


def case_03_consent_economics_canonical() -> Result:
    name = "case_03_consent_economics_canonical"
    built = _build()
    world, cid = built.world, built.cid
    _ready(world)
    facts = _prepare(world, cid)
    lease_read = world.gateway.read_lease(cid)
    resolved = resolve_offer_reference(
        built.world.exchange, built.offer_ref,
        at_instant=built.world.clock.now(),
    )
    expected_terms = canonical_json_bytes(
        {"offers": [resolved.to_dict()]}
    ).decode("utf-8")
    if lease_read.binding("offer_terms") != expected_terms:
        return fail(name, "the gateway offer terms are not the canonical "
                          "serialization of the REAL resolved offer")
    if expected_terms not in facts.expected_economic_result:
        return fail(name, "the presentation economics do not embed the "
                          "canonical offer terms (P1-2)")
    if not facts.expected_economic_result.startswith("canonical W051 offer terms"):
        return fail(name, "the presentation economics are not labelled "
                          "canonical-sourced")
    # the honest empty binding: an early (INTENT) contract carries no
    # offer terms — the window never fabricates economics
    early = _build(select_offers=False, grant_lease=False,
                   activate_contract=False)
    early_read = early.world.gateway.read_lease(early.cid)
    if (early_read.state != "INTENT"
            or early_read.binding("offer_terms") != ""):
        return fail(name, "the INTENT contract read is not honest "
                          "(state %r, terms %r)"
                          % (early_read.state,
                             early_read.binding("offer_terms")[:40]))
    # unknown economics REFUSE the presentation fail-closed: the offer
    # validity expires while the lease stays valid
    expired = _build(offer_not_after=T1H, lease_not_after=T_END)
    expired.world.clock.advance(2)
    _ready(expired.world)
    outcome = expect_client_error(
        name, str(ClientReasonCode.CANONICAL_DENIED),
        str(FailClosedResolution.UNKNOWN),
        lambda: _prepare(expired.world, expired.cid),
    )
    if not outcome[1]:
        return outcome
    return ok(name, "economics projected from the REAL M003 records; "
              "unknown economics refuse the presentation (UNKNOWN)")


# ---------------------------------------------------------------------------
# 04: the consent-attestation closed loop (REAL M005 evidence)
# ---------------------------------------------------------------------------


def case_04_consent_attestation_closed_loop() -> Result:
    name = "case_04_consent_attestation_closed_loop"
    built = _build()
    world, cid = built.world, built.cid
    _ready(world)
    _prepare(world, cid)
    sid = world.client.sharing_session_id
    consent_ref = world.authority.session(sid).consent_ref
    records = world.evidence.records()
    if len(records) != 1:
        return fail(name, "expected the opening pending attestation, got %d"
                  % len(records))
    record = records[0]
    if (record.attestation_kind != "controller-verified"
            or record.attested_value != 0
            or record.contract_ref != cid
            or record.subject_ref != consent_ref
            or record.source_refs != (sid,)):
        return fail(name, "the pending attestation is not the typed "
                          "controller-verified record")
    # the typed consent state machine while the consent is PENDING
    pending_probes = [
        expect_typed(name + "/authorize-unconsented", ConvergenceError,
                     ConvergenceReasonCode.CONSENT_REQUIRED,
                     lambda: world.authority.authorize_sharing_session(sid)),
        expect_typed(name + "/withdraw-pending", ConvergenceError,
                     ConvergenceReasonCode.LIFECYCLE_ILLEGAL,
                     lambda: world.authority.withdraw_consent(sid)),
    ]
    for outcome_part in pending_probes:
        if not outcome_part[1]:
            return outcome_part
    world.client.grant_consent()
    records = world.evidence.records()
    if len(records) != 2 or sorted(
            item.attested_value for item in records) != [0, 1]:
        return fail(name, "the granted transition did not append")
    # the typed consent state machine (the consent is granted now)
    outcomes = [
        expect_typed(name + "/grant-again", ConvergenceError,
                     ConvergenceReasonCode.LIFECYCLE_ILLEGAL,
                     lambda: world.authority.grant_consent(sid)),
        expect_typed(name + "/grant-unknown", ConvergenceError,
                     ConvergenceReasonCode.NOT_FOUND,
                     lambda: world.authority.grant_consent(
                         "m014:authz:sha256:none")),
        expect_typed(name + "/consent-unknown", ConvergenceError,
                     ConvergenceReasonCode.NOT_FOUND,
                     lambda: world.authority.consent(
                         "m014:consent:sha256:none")),
    ]
    for outcome_part in outcomes:
        if not outcome_part[1]:
            return outcome_part
    if world.authority.consent(consent_ref).state != "granted":
        return fail(name, "the consent read is not granted")
    world.client.request_handoff()
    world.client.activate()
    world.client.withdraw_consent()
    records = world.evidence.records()
    if len(records) != 3 or sorted(
            item.attested_value for item in records) != [0, 1, 2]:
        return fail(name, "the withdrawal did not append the withdrawn "
                          "attestation")
    if world.authority.consent(consent_ref).state != "withdrawn":
        return fail(name, "the consent read is not withdrawn")
    if world.authority.session(sid).state != "revoked":
        return fail(name, "the withdrawn consent did not revoke the session")
    return ok(name, "pending->granted->withdrawn as REAL immutable M005 "
              "attestations; the consent machine is typed fail-closed")


# ---------------------------------------------------------------------------
# 05: the canonical lease gate (the M002 contract stays the authority)
# ---------------------------------------------------------------------------


def case_05_canonical_lease_gate() -> Result:
    name = "case_05_canonical_lease_gate"
    no_lease = _build(grant_lease=False, activate_contract=False)
    future = _build(grant_lease=False)
    future.world.store.submit(
        GrantLease(granted_at=CREATE_AT, not_before=T2H, not_after=T_END),
        recorded_at=CREATE_AT, contract_id=future.cid,
    )
    not_capable = _build(activate_contract=False)
    expired_lease = _build(lease_not_after=T1H)
    expired_lease.world.clock.advance(2)
    expired_scope = _build(scope_until=T1H)
    expired_scope.world.clock.advance(2)
    for built in (no_lease, future, not_capable, expired_lease,
                  expired_scope):
        _ready(built.world)
    checks = [
        (expect_typed(name + "/no-lease", ConvergenceError,
                      ConvergenceReasonCode.LEASE_NOT_ACTIVE,
                      lambda: no_lease.world.authority.prepare_sharing_session(
                          lease_ref=no_lease.cid, buyer_ref=BUYER,
                          provider_ref=PROVIDER, session_ref="sess:1",
                          path_ref="path:1", scope=no_lease.world.scope,
                          platform_id=PLATFORM))),
        (expect_typed(name + "/future-window", ConvergenceError,
                      ConvergenceReasonCode.LEASE_NOT_ACTIVE,
                      lambda: future.world.authority.prepare_sharing_session(
                          lease_ref=future.cid, buyer_ref=BUYER,
                          provider_ref=PROVIDER, session_ref="sess:1",
                          path_ref="path:1", scope=future.world.scope,
                          platform_id=PLATFORM))),
        (expect_typed(name + "/not-capable-state", ConvergenceError,
                      ConvergenceReasonCode.LEASE_NOT_ACTIVE,
                      lambda: not_capable.world.authority
                      .prepare_sharing_session(
                          lease_ref=not_capable.cid, buyer_ref=BUYER,
                          provider_ref=PROVIDER, session_ref="sess:1",
                          path_ref="path:1",
                          scope=not_capable.world.scope,
                          platform_id=PLATFORM))),
        (expect_typed(name + "/expired-lease", ConvergenceError,
                      ConvergenceReasonCode.LEASE_NOT_ACTIVE,
                      lambda: expired_lease.world.authority
                      .prepare_sharing_session(
                          lease_ref=expired_lease.cid, buyer_ref=BUYER,
                          provider_ref=PROVIDER, session_ref="sess:1",
                          path_ref="path:1",
                          scope=expired_lease.world.scope,
                          platform_id=PLATFORM))),
        (expect_typed(name + "/expired-scope", ConvergenceError,
                      ConvergenceReasonCode.QUOTA_EXCEEDED,
                      lambda: expired_scope.world.authority
                      .prepare_sharing_session(
                          lease_ref=expired_scope.cid, buyer_ref=BUYER,
                          provider_ref=PROVIDER, session_ref="sess:1",
                          path_ref="path:1",
                          scope=expired_scope.world.scope,
                          platform_id=PLATFORM))),
    ]
    for outcome in checks:
        if not outcome[1]:
            return outcome
    # the frozen client surfaces the canonical denial with the reason
    # preserved verbatim
    try:
        no_lease.world.client.prepare_sharing(
            lease_ref=no_lease.cid, buyer_ref=BUYER, provider_ref=PROVIDER,
            session_ref="sess:1", path_ref="path:1",
            scope=no_lease.world.scope,
        )
        return fail(name, "the frozen client accepted an unleased contract")
    except ClientError as error:
        if (str(error.canonical_reason.code)
                != ConvergenceReasonCode.LEASE_NOT_ACTIVE):
            return fail(name, "the canonical reason was not preserved "
                              "verbatim (%r)" % error.canonical_reason.code)
        if str(getattr(error, "resolution", "")) != str(
                FailClosedResolution.DENY):
            return fail(name, "the denial resolution drifted")
    return ok(name, "the lease gate is the contract's own lifecycle "
              "(5 typed denials; LOCK-101)")


# ---------------------------------------------------------------------------
# 06: traffic admission + the declared authorization quota
# ---------------------------------------------------------------------------


def case_06_traffic_admission_quota() -> Result:
    name = "case_06_traffic_admission_quota"
    built = _build(byte_quota=1_000)
    world, cid = built.world, built.cid
    sid = _active(world, cid)
    view = world.authority.account_traffic(sid, 400)
    if view.bytes_admitted != 400:
        return fail(name, "admission not accumulated")
    negative = expect_typed(
        name + "/negative", ConvergenceError,
        ConvergenceReasonCode.INVALID_INPUT,
        lambda: world.authority.account_traffic(sid, -1),
    )
    if not negative[1]:
        return negative
    over = expect_typed(
        name + "/over-quota", ConvergenceError,
        ConvergenceReasonCode.QUOTA_EXCEEDED,
        lambda: world.authority.account_traffic(sid, 601),
    )
    if not over[1]:
        return over
    view = world.authority.account_traffic(sid, 600)
    if view.bytes_admitted != 1_000:
        return fail(name, "the exact quota boundary did not admit")
    world.client.pause()
    paused = expect_typed(
        name + "/paused", ConvergenceError,
        ConvergenceReasonCode.LIFECYCLE_ILLEGAL,
        lambda: world.authority.account_traffic(sid, 1),
    )
    if not paused[1]:
        return paused
    unknown = expect_typed(
        name + "/unknown", ConvergenceError,
        ConvergenceReasonCode.NOT_FOUND,
        lambda: world.authority.account_traffic(
            "m014:authz:sha256:none", 1),
    )
    if not unknown[1]:
        return unknown
    return ok(name, "the declared quota gates every admission "
              "(exceed/terminal/unknown fail closed)")


# ---------------------------------------------------------------------------
# 07: the LOCK-117 rate gate
# ---------------------------------------------------------------------------


def case_07_rate_limit_gate() -> Result:
    name = "case_07_rate_limit_gate"
    policy = RateLimitPolicy(limit=3, window_seconds=3600)
    built = _build(rate_policy=policy)
    world, cid = built.world, built.cid
    for index in range(3):
        view = world.authority.prepare_sharing_session(
            lease_ref=cid, buyer_ref=BUYER, provider_ref=PROVIDER,
            session_ref="sess:%d" % index, path_ref="path:%d" % index,
            scope=world.scope, platform_id=PLATFORM,
        )
        if view.state != "prepared":
            return fail(name, "admission %d did not prepare" % index)
    limited = expect_typed(
        name + "/burst", ConvergenceError,
        ConvergenceReasonCode.RATE_LIMITED,
        lambda: world.authority.prepare_sharing_session(
            lease_ref=cid, buyer_ref=BUYER, provider_ref=PROVIDER,
            session_ref="sess:3", path_ref="path:3", scope=world.scope,
            platform_id=PLATFORM,
        ),
    )
    if not limited[1]:
        return limited
    world.clock.advance(1)
    view = world.authority.prepare_sharing_session(
        lease_ref=cid, buyer_ref=BUYER, provider_ref=PROVIDER,
        session_ref="sess:4", path_ref="path:4", scope=world.scope,
        platform_id=PLATFORM,
    )
    if view.state != "prepared":
        return fail(name, "the fixed window did not reset on the injected tick")
    state = world.authority.rate_state()
    subjects = state.subjects()
    if not any(subject.startswith("prepare:") for subject in subjects):
        return fail(name, "the prepare admissions were not rate-tracked")
    # the pure surface: verdicts, validation, round-trip
    probe_policy = RateLimitPolicy(limit=2, window_seconds=60)
    probe_state = RateLimitState()
    first = check_rate_limit(probe_policy, probe_state, "s", T0)
    second = check_rate_limit(probe_policy, probe_state, "s", T0)
    third = check_rate_limit(probe_policy, probe_state, "s", T0)
    if (first.allowed or second.allowed) is not True or third.allowed:
        return fail(name, "the pure counter verdicts drifted")
    if third.reason != ConvergenceReasonCode.RATE_LIMITED:
        return fail(name, "the denial verdict reason drifted")
    later = check_rate_limit(
        probe_policy, probe_state, "s", "2027-01-15T00:01:30Z",
    )
    if not later.allowed:
        return fail(name, "the next window did not admit")
    restored = RateLimitState.from_dict(
        probe_state.to_dict(),
    )
    if restored.to_dict() != probe_state.to_dict():
        return fail(name, "the rate state round-trip is not byte-stable")
    bad_policy = expect_typed(
        name + "/zero-limit", ConvergenceError,
        ConvergenceReasonCode.INVALID_INPUT,
        lambda: RateLimitPolicy(limit=0, window_seconds=60),
    )
    if not bad_policy[1]:
        return bad_policy
    return ok(name, "fixed-window admissions deny typed at the policy; "
              "windows reset on injected ticks; state round-trips")


# ---------------------------------------------------------------------------
# 08: the emergency stop drives the store's OWN RevokeLease
# ---------------------------------------------------------------------------


def case_08_emergency_stop_canonical_revocation() -> Result:
    name = "case_08_emergency_stop"
    built = _build()
    world, cid = built.world, built.cid
    sid = _active(world, cid)
    lease_id = world.authority.session(sid).lease_id
    consent_ref = world.authority.session(sid).consent_ref
    world.client.emergency_stop()
    if str(world.client.state) != ProviderClientState.STOPPED:
        return fail(name, "the client is not STOPPED")
    if str(world.store.lease(lease_id).state) != "revoked":
        return fail(name, "the canonical lease was not revoked through the "
                          "contract store's own command (LOCK-101)")
    session = world.authority.session(sid)
    if (session.state != "revoked"
            or session.termination_reason != "emergency-stop"):
        return fail(name, "the canonical session did not terminate "
                          "emergency-stop")
    if world.authority.consent(consent_ref).state != "withdrawn":
        return fail(name, "the granted consent was not withdrawn")
    detach_log = world.runtime.adapter.detach_log()
    if "path:w41-1" not in detach_log:
        return fail(name, "the local fail-safe detach did not run first "
                          "(the frozen stop sequence)")
    notifications = world.runtime.adapter.notifications()
    if "provider.share_stopped" not in notifications:
        return fail(name, "the stop notification did not reach the adapter")
    world.client.close()
    if str(world.client.state) != ProviderClientState.CLOSED:
        return fail(name, "the stopped client did not close")
    if world.authority.session(sid).state != "closed":
        return fail(name, "the canonical session is not closed")
    return ok(name, "local fail-safe -> canonical RevokeLease -> verified "
              "terminal read -> STOPPED -> CLOSED")


# ---------------------------------------------------------------------------
# 09: the authority-side revocation is OBSERVED (never locally minted)
# ---------------------------------------------------------------------------


def case_09_authority_side_revocation_observed() -> Result:
    name = "case_09_authority_revocation_observed"
    built = _build()
    world, cid = built.world, built.cid
    sid = _active(world, cid)
    lease_id = world.authority.session(sid).lease_id
    world.authority.revoke_authorization(sid, "operator-policy-7")
    if (world.authority.session(sid).state != "revoked"
            or str(world.store.lease(lease_id).state) != "revoked"):
        return fail(name, "the authority-side revocation did not terminate")
    snapshot = world.client.refresh_status()
    if snapshot.state != "revoked":
        return fail(name, "the client did not observe the terminal truth")
    if str(world.client.state) != ProviderClientState.REVOKED:
        return fail(name, "the terminal projection did not land")
    resurrect = expect_client_error(
        name + "/no-resurrection", str(ClientReasonCode.LIFECYCLE_ILLEGAL),
        str(FailClosedResolution.DENY),
        lambda: world.client.grant_consent(),
    )
    if not resurrect[1]:
        return resurrect
    return ok(name, "the terminal truth is observed through the read "
              "window; terminal clients never resurrect")


# ---------------------------------------------------------------------------
# 10: consent withdrawal terminates canonically
# ---------------------------------------------------------------------------


def case_10_consent_withdrawal_terminates() -> Result:
    name = "case_10_consent_withdrawal"
    built = _build()
    world, cid = built.world, built.cid
    sid = _active(world, cid)
    consent_ref = world.authority.session(sid).consent_ref
    world.client.withdraw_consent()
    if str(world.client.state) != ProviderClientState.REVOKED:
        return fail(name, "the withdrawing client is not REVOKED")
    session = world.authority.session(sid)
    if (session.state != "revoked"
            or session.termination_reason != "consent-withdrawn"):
        return fail(name, "the canonical termination reason drifted")
    if world.authority.consent(consent_ref).state != "withdrawn":
        return fail(name, "the consent is not withdrawn")
    values = sorted(record.attested_value
                    for record in world.evidence.records())
    if values != [0, 1, 2]:
        return fail(name, "the attestation stream is %r (expected "
                          "pending/granted/withdrawn)" % values)
    return ok(name, "withdrawal: canonical revoked + withdrawn attestation "
              "(no soft revoke)")


# ---------------------------------------------------------------------------
# 11: lease expiry is observed through the store's own surface
# ---------------------------------------------------------------------------


def case_11_lease_expiry_observed() -> Result:
    name = "case_11_lease_expiry_observed"
    built = _build(lease_not_after=T1H)
    world, cid = built.world, built.cid
    sid = _active(world, cid)
    world.clock.advance(2)
    snapshot = world.client.refresh_status()
    if snapshot.state != "expired":
        return fail(name, "the canonical session did not expire (got %r)"
                    % snapshot.state)
    if str(world.client.state) != ProviderClientState.EXPIRED:
        return fail(name, "the expiry projection did not land")
    session = world.authority.session(sid)
    if (session.state != "expired"
            or session.termination_reason != "lease-expired"):
        return fail(name, "the canonical expiry reason drifted")
    return ok(name, "expiry observed through the contract store's own "
              "expire_leases_if_due surface (never a local timer)")


# ---------------------------------------------------------------------------
# 12: the W049 duck-typed views + the scope projection
# ---------------------------------------------------------------------------


def case_12_duck_typed_views_and_scope_projection() -> Result:
    name = "case_12_duck_typed_views"
    built = _build()
    world, cid = built.world, built.cid
    _ready(world)
    _prepare(world, cid)
    view = world.sharing.session(world.client.sharing_session_id)
    if not isinstance(view, ConvergedSessionView):
        return fail(name, "the facade did not project the W049 view")
    if view.sharing_session_id != view.session_id or not view.session_id:
        return fail(name, "the W049 session identity attribute drifted")
    if view.lease_ref != cid:
        return fail(name, "lease_ref must be the CONTRACT id (the canonical "
                          "commercial record)")
    scope = view.scope
    if not isinstance(scope, ConvergedConsentScope):
        return fail(name, "the view does not carry the consent scope")
    checks = {
        "egress": scope.exposed_egress == (
            "egress:internet-via-provider",),
        "expiry": scope.time_quota_expiry == T_END,
        "quota": scope.byte_quota == 1_000_000,
        "buyers": scope.max_concurrent_buyers == 2,
        "round trip": ConvergedConsentScope.from_dict(
            scope.to_dict(),
        ).to_dict() == scope.to_dict(),
    }
    missing = [label for label, held in checks.items() if not held]
    if missing:
        return fail(name, "scope projection drifted: %s" % missing)
    projection = expect_typed(
        name + "/non-scope", ClientConvergenceError,
        ClientConvergenceReasonCode.INVALID_INPUT,
        lambda: consent_scope_from_declared("not-a-scope"),
    )
    if not projection[1]:
        return projection
    bad_scope = expect_typed(
        name + "/bad-dimension", ClientConvergenceError,
        ClientConvergenceReasonCode.INVALID_INPUT,
        lambda: ConvergedConsentScope(
            exposed_egress=("ok",), time_quota_expiry=T_END,
            byte_quota=-1, max_concurrent_buyers=0,
        ),
    )
    if not bad_scope[1]:
        return bad_scope
    # a second session: sorted deterministic iteration
    second = world.authority.prepare_sharing_session(
        lease_ref=cid, buyer_ref=BUYER, provider_ref=PROVIDER,
        session_ref="sess:logical-2", path_ref="path:w41-2",
        scope=world.scope, platform_id=PLATFORM,
    )
    sessions = world.authority.sessions()
    ids = [item.session_id for item in sessions]
    if ids != sorted(ids) or len(ids) != 2:
        return fail(name, "sessions() is not sorted/deterministic")
    if second.session_id not in ids:
        return fail(name, "the second session is not readable")
    consent = world.sharing.consent(view.consent_ref)
    if (consent.state != "pending" or consent.provider_ref != PROVIDER
            or consent.buyer_ref != BUYER):
        return fail(name, "the consent view attributes drifted")
    return ok(name, "the frozen W049 attributes project 1:1 (lease_ref = "
              "the contract id; sorted sessions)")


# ---------------------------------------------------------------------------
# 13: the converged gateway read window
# ---------------------------------------------------------------------------


def case_13_gateway_read_window() -> Result:
    name = "case_13_gateway_read_window"
    built = _build()
    world, cid = built.world, built.cid
    sid = _active(world, cid)
    consent_ref = world.authority.session(sid).consent_ref
    session_read = world.gateway.read_sharing_session(sid)
    if (session_read.authority != "sharing"
            or session_read.state != "active"
            or session_read.observed_at != world.clock.now()
            or session_read.binding("buyer_ref") != BUYER
            or session_read.binding("provider_ref") != PROVIDER
            or session_read.binding("consent_ref") != consent_ref
            or session_read.binding("path_ref") != "path:w41-1"):
        return fail(name, "the sharing read bindings drifted")
    consent_read = world.gateway.read_consent(consent_ref)
    if (consent_read.state != "granted"
            or consent_read.binding("provider_ref") != PROVIDER):
        return fail(name, "the consent read drifted")
    lease_read = world.gateway.read_lease(cid)
    if (lease_read.authority != "commercial"
            or lease_read.state != "EXECUTION_ACTIVE"
            or lease_read.binding("buyer_ref") != BUYER
            or not lease_read.binding("offer_terms")):
        return fail(name, "the commercial read drifted")
    unwired = [
        expect_client_error(
            name + "/path-unwired", str(ClientReasonCode.STALE_STATE),
            str(FailClosedResolution.DENY),
            lambda: world.gateway.read_path("path:w41-1"),
        ),
        expect_client_error(
            name + "/usage-unwired", str(ClientReasonCode.STALE_STATE),
            str(FailClosedResolution.DENY),
            lambda: world.gateway.read_usage_account(cid),
        ),
        expect_client_error(
            name + "/unknown-session", str(ClientReasonCode.CANONICAL_DENIED),
            str(FailClosedResolution.UNKNOWN),
            lambda: world.gateway.read_sharing_session(
                "m014:authz:sha256:none"),
        ),
    ]
    for outcome in unwired:
        if not outcome[1]:
            return outcome
    # the offline seam: reads fail closed, mutations are refused,
    # nothing is fabricated; reconnect reconciles
    world.gateway.set_reachable(False)
    offline_read = expect_client_error(
        name + "/offline-read", str(ClientReasonCode.OFFLINE),
        str(FailClosedResolution.UNKNOWN),
        lambda: world.gateway.read_sharing_session(sid),
    )
    if not offline_read[1]:
        return offline_read
    offline_mutation = expect_client_error(
        name + "/offline-mutation", str(ClientReasonCode.OFFLINE),
        str(FailClosedResolution.UNKNOWN),
        lambda: world.client.pause(),
    )
    if not offline_mutation[1]:
        return offline_mutation
    if str(world.client.state) != ProviderClientState.ACTIVE:
        return fail(name, "the offline refusal mutated the lifecycle")
    world.gateway.set_reachable(True)
    reconciled = world.client.reconcile()
    if reconciled.state != "active":
        return fail(name, "the reconnect reconciliation did not observe "
                          "canonical truth")
    return ok(name, "sharing/commercial reads bound + clocked; the unwired "
              "seams refuse typed; offline fails closed")


# ---------------------------------------------------------------------------
# 14: the by-reference citation set of one converged world
# ---------------------------------------------------------------------------


def case_14_converged_client_citations() -> Result:
    name = "case_14_converged_client_citations"
    built = _build()
    world, cid = built.world, built.cid
    sid = _active(world, cid)
    world.client.withdraw_consent()
    citations = converged_client_citations(
        world, issuer="m014-battery", cited_at=T0,
    )
    contract_citations = [c for c in citations if c.authority == "contracts"]
    offer_citations = [c for c in citations if c.authority == "offers"]
    evidence_citations = [c for c in citations if c.authority == "evidence"]
    if len(contract_citations) != 1 or len(offer_citations) != 1:
        return fail(name, "citation counts drifted (%d contracts, %d offers)"
                  % (len(contract_citations), len(offer_citations)))
    if len(evidence_citations) != 3:
        return fail(name, "expected the 3 consent attestations, got %d"
                  % len(evidence_citations))
    contract = world.store.contract(cid)
    expected_digest = _sha256_hex(contract.canonical_bytes())
    citation = contract_citations[0]
    if (citation.subject_ref != cid
            or citation.payload_digest != expected_digest
            or citation.citation_id != derive_citation_id(
                "contracts", cid, "connectivity-contract", expected_digest)):
        return fail(name, "the contract citation does not digest the real "
                          "record's OWN canonical bytes")
    resolved = resolve_offer_reference(
        built.world.exchange, built.offer_ref, at_instant=T0,
    )
    offer_citation = offer_citations[0]
    if (offer_citation.subject_ref != "%s/%s" % (
            PROVIDER, "offer:netpro-basic-1")
            or offer_citation.payload_digest != _sha256_hex(
                resolved.canonical_bytes())):
        return fail(name, "the offer citation does not digest the real "
                          "record's OWN canonical bytes")
    record_ids = {record.record_id for record in world.evidence.records()}
    cited_ids = {c.subject_ref for c in evidence_citations}
    if record_ids != cited_ids:
        return fail(name, "the evidence citations do not cover the record "
                          "identities")
    # canonical round-trips + tamper evidence
    for item in citations:
        if ChildCitation.from_dict(item.to_dict()).to_dict() != item.to_dict():
            return fail(name, "citation round-trip not byte-stable")
    tampered = dict(citations[0].to_dict())
    tampered["payload_digest"] = "0" * 64
    tamper = expect_typed(
        name + "/tamper", ConvergenceError,
        ConvergenceReasonCode.ID_MISMATCH,
        lambda: ChildCitation.from_dict(tampered),
    )
    if not tamper[1]:
        return tamper
    return ok(name, "contract + offer + 3 evidence citations, each digesting "
              "the cited record's OWN canonical bytes (LOCK-101/106/118)")


# ---------------------------------------------------------------------------
# 15: the wider converged citation surface (the other child authorities)
# ---------------------------------------------------------------------------


def case_15_child_authority_citation_surface() -> Result:
    name = "case_15_child_authority_citations"
    built = _build()
    world, cid = built.world, built.cid
    contract = world.store.contract(cid)
    # a REAL M006 execution plan translated from the SAME contract
    plan = translate_contract(
        contract,
        (SegmentInput(
            offer_reference=built.offer_ref,
            role="primary",
            operations=("reserve", "activate", "measure", "release"),
            provenance=_prov("optimizer:m014-battery", "dec:opt-m014"),
        ),),
        provenance=_prov("optimizer:m014-battery", "dec:opt-m014"),
    )
    plan_citation = cite_execution_plan(
        plan, issuer="m014-battery", cited_at=T0,
    )
    if (plan_citation.authority != "executionplans"
            or plan_citation.subject_ref != plan.plan_id
            or plan_citation.payload_digest != _sha256_hex(
                plan.canonical_bytes())):
        return fail(name, "the plan citation does not digest the REAL M006 "
                          "record")
    # a REAL M007 adapter capability view
    view = CapabilityView(
        adapter_id="adapter:tech-experimental-1",
        access_technology_id="access:experimental",
        capability_references=("capability.core.multipath",),
        standard_mechanisms=("mech:standard-1",),
        computed_instant=T0,
        lifecycle="active",
    )
    adapter_citation = cite_adapter_capability(
        view, issuer="m014-battery", cited_at=T0,
    )
    if (adapter_citation.authority != "adapters"
            or adapter_citation.subject_ref != view.adapter_id
            or adapter_citation.payload_digest != _sha256_hex(
                view.to_canonical_bytes())):
        return fail(name, "the adapter citation does not digest the REAL "
                          "M007 record")
    # the commercial/vertical-proof seams (opaque typed references)
    settlement = cite_settlement_reference(
        subject_ref="usage-ledger/settlement-42",
        canonical_payload=canonical_json_bytes({"settlement": "s-42"}),
        issuer="m014-battery", cited_at=T0,
    )
    if (settlement.authority != "commercial"
            or settlement.ref_kind != "settlement-reference"):
        return fail(name, "the settlement citation drifted")
    proof = cite_vertical_proof(
        proof_kind="sharenet", subject_ref="pattern/hgw-1",
        issuer="m014-battery", cited_at=T0,
        canonical_payload=canonical_json_bytes({"pattern": "hgw-1"}),
    )
    if (proof.authority != "vertical-proof"
            or proof.subject_ref != "sharenet/pattern/hgw-1"):
        return fail(name, "the vertical-proof citation drifted")
    bad_proof = expect_typed(
        name + "/bad-proof-kind", ConvergenceError,
        ConvergenceReasonCode.VOCABULARY,
        lambda: cite_vertical_proof(
            proof_kind="unknown", subject_ref="x",
            issuer="m014-battery", cited_at=T0,
            canonical_payload=canonical_json_bytes({"x": 1}),
        ),
    )
    if not bad_proof[1]:
        return bad_proof
    # the duck-typed record constructors fail closed on non-records
    not_a_plan = expect_typed(
        name + "/not-a-plan", ConvergenceError,
        ConvergenceReasonCode.INVALID_INPUT,
        lambda: cite_execution_plan(
            "not-a-plan", issuer="m014-battery", cited_at=T0),
    )
    if not not_a_plan[1]:
        return not_a_plan
    not_a_view = expect_typed(
        name + "/not-a-view", ConvergenceError,
        ConvergenceReasonCode.INVALID_INPUT,
        lambda: cite_adapter_capability(
            {"adapter_id": "x"}, issuer="m014-battery", cited_at=T0),
    )
    if not not_a_view[1]:
        return not_a_view
    not_a_decision = expect_typed(
        name + "/not-a-decision", ConvergenceError,
        ConvergenceReasonCode.INVALID_INPUT,
        lambda: cite_replan_decision(
            "not-a-decision", issuer="m014-battery", cited_at=T0),
    )
    if not not_a_decision[1]:
        return not_a_decision
    # every authority label is inside the frozen set
    for citation in (plan_citation, adapter_citation, settlement, proof):
        if citation.authority not in CONVERGENCE_AUTHORITIES:
            return fail(name, "authority %r outside the frozen set"
                      % citation.authority)
    # the ONE sanctioned lift into the REAL M005 evidence space
    attestation = peer_evidence_from_citation(
        plan_citation, producer="peer:domain-b", valid_until=T_END,
    )
    if (not isinstance(attestation, AttestationEvidence)
            or attestation.attestation_kind != "remotely-attested"
            or attestation.subject_ref != plan_citation.subject_ref
            or attestation.source_refs != (plan_citation.citation_id,)
            or attestation.contract_ref != "m014-convergence:executionplans"):
        return fail(name, "the peer lift is not the frozen remotely-attested "
                          "record")
    peer_store = EvidenceStore()
    peer_store.ingest(attestation)
    if len(peer_store.records()) != 1:
        return fail(name, "the peer evidence did not enter the REAL store")
    bad_window = expect_typed(
        name + "/bad-window", ConvergenceError,
        ConvergenceReasonCode.EVIDENCE_REJECTED,
        lambda: peer_evidence_from_citation(
            plan_citation, producer="peer:domain-b", valid_until=T0),
    )
    if not bad_window[1]:
        return bad_window
    return ok(name, "executionplans/adapters/commercial/vertical-proof "
              "cited by reference; the peer lift enters the REAL evidence "
              "space")


# ---------------------------------------------------------------------------
# 16: the per-domain citation ledger + the revocation discipline
# ---------------------------------------------------------------------------


def case_16_citation_ledger_revocation() -> Result:
    name = "case_16_citation_ledger_revocation"
    built = _build()
    world, cid = built.world, built.cid
    contract = world.store.contract(cid)
    citation = cite_contract(
        contract, issuer="m014-battery", cited_at=T0,
    )
    ledger = DomainCitationLedger()
    ledger.append(citation)
    if ledger.append(citation) is not citation or len(
            ledger.citations()) != 1:
        return fail(name, "the identical append is not an idempotent no-op")
    # a forged same-id/different-content record is rejected (tamper)
    forged = object.__new__(ChildCitation)
    forged.__dict__.update({
        "citation_id": citation.citation_id,
        "authority": citation.authority,
        "subject_ref": citation.subject_ref,
        "ref_kind": citation.ref_kind,
        "issuer": "m014-forged",
        "cited_at": citation.cited_at,
        "payload_digest": citation.payload_digest,
    })
    collision = expect_typed(
        name + "/collision", ConvergenceError,
        ConvergenceReasonCode.ID_MISMATCH,
        lambda: ledger.append(forged),
    )
    if not collision[1]:
        return collision
    # the pending -> propagated -> confirmed propagation discipline
    pending = citation_revocation(
        citation_id=citation.citation_id, reason="battery-revocation",
        revoked_at=T0,
    )
    propagated = citation_revocation(
        citation_id=citation.citation_id, reason="battery-revocation",
        revoked_at=T1H, propagated_to=("domain-b", "domain-c"),
        state="propagated",
    )
    confirmed = citation_revocation(
        citation_id=citation.citation_id, reason="battery-revocation",
        revoked_at=T2H, propagated_to=("domain-b", "domain-c"),
        confirmed_by=("domain-b", "domain-c"), state="confirmed",
    )
    ledger.revoke(pending)
    if not ledger.is_revoked(citation.citation_id):
        return fail(name, "the pending revocation is not visible")
    if len(ledger.citations()) != 1:
        return fail(name, "the revocation deleted history (append-only "
                          "violated)")
    ledger.revoke(propagated)
    ledger.revoke(confirmed)
    if ledger.revocation(citation.citation_id).state != "confirmed":
        return fail(name, "the propagation did not reach confirmed")
    exact_replay = ledger.revoke(confirmed)
    if exact_replay.state != "confirmed":
        return fail(name, "the exact idempotent replay failed")
    backward = expect_typed(
        name + "/backward", ConvergenceError,
        ConvergenceReasonCode.REVOCATION_INVALID,
        lambda: ledger.revoke(propagated),
    )
    if not backward[1]:
        return backward
    re_append = ledger.append(citation)
    if (re_append is not citation or len(ledger.citations()) != 1
            or not ledger.is_revoked(citation.citation_id)):
        return fail(name, "the identical re-append after revocation is not "
                          "the idempotent history-preserving no-op")
    unknown = expect_typed(
        name + "/unknown-revocation", ConvergenceError,
        ConvergenceReasonCode.NOT_FOUND,
        lambda: ledger.revoke(citation_revocation(
            citation_id="m014:cite:sha256:none", reason="x",
            revoked_at=T0,
        )),
    )
    if not unknown[1]:
        return unknown
    bad_state = expect_typed(
        name + "/bad-state", ConvergenceError,
        ConvergenceReasonCode.VOCABULARY,
        lambda: citation_revocation(
            citation_id=citation.citation_id, reason="x", revoked_at=T0,
            state="final",
        ),
    )
    if not bad_state[1]:
        return bad_state
    # deterministic digests + round-trips
    first_digest = ledger.digest()
    restored = DomainCitationLedger.from_dict(ledger.to_dict())
    if (restored.digest() != first_digest
            or restored.to_dict() != ledger.to_dict()):
        return fail(name, "the ledger round-trip is not byte-stable")
    if DomainCitationLedger.from_dict(
            ledger.to_dict()).digest() != first_digest:
        return fail(name, "the ledger digest is not replay-stable")
    # content-derived revocation ids
    same_again = citation_revocation(
        citation_id=citation.citation_id, reason="battery-revocation",
        revoked_at=T0,
    )
    if same_again.revocation_id != pending.revocation_id:
        return fail(name, "the revocation id is not content-derived")
    other_reason = citation_revocation(
        citation_id=citation.citation_id, reason="other-reason",
        revoked_at=T0,
    )
    if other_reason.revocation_id == pending.revocation_id:
        return fail(name, "distinct content produced the same id")
    return ok(name, "append-only idempotent ledger; pending->propagated->"
              "confirmed forward-only; byte-stable digests")


# ---------------------------------------------------------------------------
# 17: W048 stays accepted-not-restored (the DEC-0099 invariant)
# ---------------------------------------------------------------------------


def _client_module_paths() -> List[str]:
    client_dir = os.path.join(REPO_ROOT, "client")
    return [
        os.path.join(client_dir, entry)
        for entry in sorted(os.listdir(client_dir))
        if entry.endswith(".py")
    ]


def _module_imports(path: str) -> List[str]:
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    imported: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module)
            else:
                imported.extend(
                    alias.name for alias in node.names
                )
    return imported


def case_17_w048_stays_accepted_not_restored() -> Result:
    name = "case_17_w048_accepted_not_restored"
    modules = _client_module_paths()
    offenders = []
    for path in modules:
        module_name = os.path.basename(path)
        for imported in _module_imports(path):
            root = imported.split(".")[0]
            if root == "sharing":
                offenders.append(
                    "%s imports %s" % (module_name, imported),
                )
            elif root == "containment" and imported not in (
                # the ONE frozen sanctioned seam: the ACR-012 capability
                # vocabulary reused as DATA by the frozen W049 contract
                # (client/capability.py, byte-identical to origin/main —
                # verified in case_20; everything else in containment is
                # W048 subject material and stays forbidden)
                "containment.state",
            ):
                offenders.append(
                    "%s imports %s" % (module_name, imported),
                )
    if offenders:
        return fail(name, "W048 surfaces leaked into the client family: %s"
                  % offenders)
    # the NEW M014 composition imports no containment/sharing surface
    # AT ALL (not even the frozen vocabulary seam — the converged
    # admission gate is lease + consent + quota)
    convergence_imports = _module_imports(
        os.path.join(REPO_ROOT, "client", "convergence.py"),
    )
    for imported in convergence_imports:
        if imported.split(".")[0] in ("containment", "sharing"):
            return fail(name, "the new composition imports %r" % imported)
    # the containment package still lacks CapabilityMatrix: the DEC-0099
    # guard's own probe cannot silently re-enable
    probe = subprocess.run(
        [sys.executable, "-c", "from containment import CapabilityMatrix"],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    if probe.returncode == 0:
        return fail(name, "containment.CapabilityMatrix reappeared — the "
                          "W048 restoration guard would silently re-enable")
    # no containment/isolation primitive is defined anywhere in the
    # five convergence modules (def/class name scan)
    convergence_modules = [
        os.path.join(REPO_ROOT, package, "convergence.py")
        for package in (
            "federation", "identity", "upgrade", "scale", "client",
        )
    ]
    primitive_names = []
    for path in convergence_modules:
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                lowered = node.name.lower()
                if "containment" in lowered or "isolat" in lowered:
                    primitive_names.append("%s:%s" % (
                        os.path.basename(os.path.dirname(path)), node.name,
                    ))
    if primitive_names:
        return fail(name, "isolation primitives defined: %s"
                  % primitive_names)
    # the converged sharing facade exposes EXACTLY the frozen W049
    # protocol members (no enforcement surface beyond them)
    protocol_members = {
        "prepare_sharing_session", "grant_consent",
        "authorize_sharing_session", "activate_sharing_session",
        "pause_sharing_session", "resume_sharing_session",
        "withdraw_consent", "emergency_stop", "close_sharing_session",
        "notify_path_lost", "account_traffic", "session", "consent",
    }
    public_members = {
        member for member in dir(ConvergedSharingRuntime)
        if not member.startswith("_")
    }
    extra = public_members - protocol_members - {
        "authority", "declared_scope", "consent_scope",
    }
    if extra:
        return fail(name, "the facade grew non-protocol members: %s"
                  % sorted(extra))
    missing = protocol_members - public_members
    if missing:
        return fail(name, "the facade lost protocol members: %s"
                  % sorted(missing))
    # this battery itself consumes no W048 surface (AST-audited: the
    # probe string above is an intentional NEGATIVE probe, not an
    # import; the battery's own imports must be free of both roots)
    battery_imports = _module_imports(os.path.abspath(__file__))
    for imported in battery_imports:
        if imported.split(".")[0] in ("containment", "sharing"):
            return fail(name, "the battery itself imports %r" % imported)
    return ok(name, "no containment/sharing import (beyond the frozen "
              "vocabulary seam), no isolation primitive, no facade "
              "growth — WORK-048 accepted-not-restored")


# ---------------------------------------------------------------------------
# 18: LOCK-119 discipline (determinism + secret rejection)
# ---------------------------------------------------------------------------


_FORBIDDEN_ROOTS = (
    "random", "uuid", "socket", "urllib", "http", "ftplib", "smtplib",
    "telnetlib", "secrets", "ssl", "asyncio",
)
_FORBIDDEN_CALLS = (
    "time.time", "time.monotonic", "datetime.now", "datetime.utcnow",
    "datetime.today", "os.urandom", "random.random", "uuid.uuid",
)


def case_18_lock119_discipline() -> Result:
    name = "case_18_lock119_discipline"
    convergence_modules = [
        os.path.join(REPO_ROOT, package, "convergence.py")
        for package in (
            "federation", "identity", "upgrade", "scale", "client",
        )
    ]
    offenders: List[str] = []
    for path in convergence_modules:
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in _FORBIDDEN_ROOTS:
                        offenders.append("%s imports %s" % (
                            os.path.basename(path), alias.name,
                        ))
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in _FORBIDDEN_ROOTS:
                    offenders.append("%s imports from %s" % (
                        os.path.basename(path), node.module,
                    ))
            elif isinstance(node, ast.Call):
                function = node.func
                trace: List[str] = []
                while isinstance(function, ast.Attribute):
                    trace.append(function.attr)
                    function = function.value
                if isinstance(function, ast.Name):
                    trace.append(function.id)
                    dotted = ".".join(reversed(trace))
                    for pattern in _FORBIDDEN_CALLS:
                        if dotted == pattern or dotted.startswith(
                                pattern + "("):
                            offenders.append("%s calls %s" % (
                                os.path.basename(path), dotted,
                            ))
    if offenders:
        return fail(name, "LOCK-119 offenders: %s" % offenders)
    # secret-shaped material is rejected at the construction boundaries
    built = _build()
    secret = expect_typed(
        name + "/secret-prepare", ConvergenceError,
        ConvergenceReasonCode.SECRET_REJECTED,
        lambda: built.world.authority.prepare_sharing_session(
            lease_ref=built.cid, buyer_ref=BUYER,
            provider_ref="x:api_key-provider", session_ref="sess:1",
            path_ref="path:1", scope=built.world.scope, platform_id=PLATFORM,
        ),
    )
    if not secret[1]:
        return secret
    contract = built.world.store.contract(built.cid)
    secret_citation = expect_typed(
        name + "/secret-issuer", ConvergenceError,
        ConvergenceReasonCode.SECRET_REJECTED,
        lambda: cite_contract(
            contract, issuer="issuer-with-password", cited_at=T0),
    )
    if not secret_citation[1]:
        return secret_citation
    return ok(name, "no wall clock/randomness/UUID/network in the five "
              "convergence modules; secret-shaped material rejected typed")


# ---------------------------------------------------------------------------
# 19: determinism (in-process + cross-PYTHONHASHSEED)
# ---------------------------------------------------------------------------


def _determinism_stream() -> Dict[str, str]:
    built = _build()
    world, cid = built.world, built.cid
    _ready(world)
    _prepare(world, cid)
    world.client.grant_consent()
    world.client.request_handoff()
    world.client.activate()
    sid = world.client.sharing_session_id
    consent_ref = world.authority.session(sid).consent_ref
    world.client.withdraw_consent()
    citations = converged_client_citations(
        world, issuer="m014-battery", cited_at=T0,
    )
    ledger = DomainCitationLedger()
    for citation in citations:
        ledger.append(citation)
    return {
        "session_id": sid,
        "consent_ref": consent_ref,
        "events_digest": world.runtime.events_digest(),
        "citation_count": str(len(citations)),
        "citation_digest": _sha256_hex(canonical_json_bytes(
            [item.to_dict() for item in citations],
        )),
        "ledger_digest": ledger.digest(),
        "evidence_digest": _sha256_hex(canonical_json_bytes(
            [record.to_dict() for record in world.evidence.records()],
        )),
        "rate_state": canonical_json_bytes(
            world.authority.rate_state().to_dict(),
        ).decode("utf-8"),
    }


def case_19_determinism() -> Result:
    name = "case_19_determinism"
    first = _determinism_stream()
    second = _determinism_stream()
    if first != second:
        return fail(name, "two fresh worlds diverged")
    # cross-process determinism under PYTHONHASHSEED 0/1/42 and unset
    outputs: List[str] = []
    environments = [{"PYTHONHASHSEED": "0"}, {"PYTHONHASHSEED": "1"},
                    {"PYTHONHASHSEED": "42"}]
    base_env = dict(os.environ)
    for override in environments:
        env = dict(base_env)
        env["PYTHONHASHSEED"] = override["PYTHONHASHSEED"]
        run = subprocess.run(
            [sys.executable, os.path.abspath(__file__),
             "--determinism-stream"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
        )
        if run.returncode != 0:
            return fail(name, "subprocess failed under %s: %s"
                        % (override, run.stderr[-200:]))
        outputs.append(run.stdout)
    unset_env = dict(base_env)
    unset_env.pop("PYTHONHASHSEED", None)
    run = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--determinism-stream"],
        capture_output=True, text=True, env=unset_env, cwd=str(REPO_ROOT),
    )
    if run.returncode != 0:
        return fail(name, "subprocess failed with PYTHONHASHSEED unset")
    outputs.append(run.stdout)
    if len(set(outputs)) != 1:
        return fail(name, "PYTHONHASHSEED variance: %d distinct outputs"
                    % len(set(outputs)))
    expected = "".join(
        "%s=%s\n" % (key, first[key]) for key in sorted(first)
    )
    if outputs[0] != expected:
        return fail(name, "the subprocess stream diverged from the "
                          "in-process stream")
    return ok(name, "byte-identical across fresh worlds and PYTHONHASHSEED "
              "0/1/42/unset subprocesses")


# ---------------------------------------------------------------------------
# 20: the frozen W049 core is unchanged (the re-baseline discipline)
# ---------------------------------------------------------------------------


_FROZEN_CLIENT_MODULES = (
    "__init__.py", "adapters.py", "buyer.py", "capability.py", "errors.py",
    "events.py", "gateway.py", "model.py", "privacy.py", "projection.py",
    "provider.py", "runtime.py", "sandbox.py", "state.py",
)

_SANCTIONED_CONVERGENCE_IMPORTS = {
    "__future__",
    "dataclasses",
    "typing",
    "protocol.canonicalization",
    "contracts",
    "evidence",
    "offers",
    "federation.convergence",
    "client.adapters",
    "client.errors",
    "client.gateway",
    "client.model",
    "client.provider",
    "client.runtime",
}


def case_20_frozen_core_unchanged() -> Result:
    name = "case_20_frozen_core_unchanged"
    # import discipline of the composition module first (always available)
    path = os.path.join(REPO_ROOT, "client", "convergence.py")
    absolute: set = set()
    relative: set = set()
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                absolute.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if node.module:
                    relative.add("client.%s" % node.module)
                else:
                    for alias in node.names:
                        relative.add("client.%s" % alias.name)
            elif node.module:
                absolute.add(node.module)
    actual = absolute | relative
    unexpected = actual - _SANCTIONED_CONVERGENCE_IMPORTS
    missing = _SANCTIONED_CONVERGENCE_IMPORTS - actual
    if unexpected or missing:
        return fail(name, "import drift (unexpected %s, missing %s)"
                    % (sorted(unexpected), sorted(missing)))
    ref_check = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if ref_check.returncode != 0:
        # origin/main unavailable (isolated checkout): the weaker
        # disclosed check — the frozen modules are unmodified in the
        # working tree and committed
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", "client/"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        if status.stdout.strip():
            return fail(name, "uncommitted client/ changes")
        return ok(name, "import discipline green; origin/main unavailable — "
                  "tree-clean fallback (disclosed)")
    delta = subprocess.run(
        ["git", "diff", "--name-only", "origin/main", "HEAD", "--", "client/"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    changed = [line for line in delta.stdout.splitlines() if line.strip()]
    if set(changed) != {"client/convergence.py"}:
        return fail(name, "the client delta is not exactly the convergence "
                          "module: %s" % changed)
    for module in _FROZEN_CLIENT_MODULES:
        local = subprocess.run(
            ["git", "hash-object", os.path.join(REPO_ROOT, "client", module)],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        remote = subprocess.run(
            ["git", "rev-parse", "origin/main:client/%s" % module],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        if (remote.returncode != 0
                or local.stdout.strip() != remote.stdout.strip()):
            return fail(name, "frozen module %s drifted from origin/main"
                      % module)
    return ok(name, "the frozen W049 core is byte-identical to origin/main "
              "(%d modules); the composition imports exactly the "
              "sanctioned set" % len(_FROZEN_CLIENT_MODULES))


# ---------------------------------------------------------------------------
# 21: PR delta shape + authorization coverage + tree cleanliness
# ---------------------------------------------------------------------------


def case_21_pr_delta_authorization() -> Result:
    name = "case_21_pr_delta_authorization"
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    untracked = [
        line[3:] for line in status.stdout.splitlines()
        if line.startswith("??")
    ]
    if untracked:
        return fail(name, "untracked files read as unauthorized deltas to "
                          "tree-auditing batteries: %s" % untracked)
    ref_check = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if ref_check.returncode != 0:
        return ok(name, "tree clean; origin/main unavailable (isolated "
                  "checkout; the delta audit is disclosed-skipped)")
    delta = subprocess.run(
        ["git", "diff", "--name-only", "origin/main", "HEAD"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    changed = [line for line in delta.stdout.splitlines() if line.strip()]
    if not changed:
        return ok(name, "tree clean; no delta vs origin/main "
                  "(post-acceptance state)")
    try:
        from authorization_provenance import covers
    except Exception as error:  # noqa: BLE001
        return fail(name, "authorization consultation unavailable: %s"
                    % error)
    uncovered = [path for path in changed if not covers(path)]
    if uncovered:
        return fail(name, "delta outside the ACTIVE R7-CORE-001 scope: %s"
                    % uncovered)
    forbidden = [path for path in changed
                 if path.startswith(("spec/", ".github/"))]
    if forbidden:
        return fail(name, "control-plane surfaces in an implementation "
                          "delta: %s" % forbidden)
    return ok(name, "every delta path (%d) covered by the ACTIVE "
              "R7-CORE-001 authorization; no spec/ or .github/ touch"
              % len(changed))


# ---------------------------------------------------------------------------
# 22: the evidence-class honesty contract
# ---------------------------------------------------------------------------


def case_22_evidence_honesty() -> Result:
    name = "case_22_evidence_honesty"
    path = os.path.join(REPO_ROOT, "docs", "M014-evidence.md")
    if not os.path.isfile(path):
        return fail(name, "docs/M014-evidence.md is missing (lands with "
                          "this delivery; the honesty contract is part of "
                          "the battery)")
    with open(path, encoding="utf-8") as handle:
        doc = handle.read()
    markers = {
        "work item": "M014" in doc,
        "software class": "SOFTWARE" in doc,
        "physical honesty": "no PHYSICAL PASS" in doc,
        "open physical": "EVID-002" in doc,
        "w048 disclosure": "accepted-not-restored" in doc,
        "re-baseline disclosure": "DEC-0099" in doc,
        "authorization": "R7-CORE-001" in doc,
    }
    missing = [label for label, held in markers.items() if not held]
    if missing:
        return fail(name, "honesty markers missing from the evidence doc: %s"
                    % missing)
    if "PHYSICAL: PASS" in doc or "PHYSICAL PASS." in doc:
        return fail(name, "an affirmative PHYSICAL PASS claim exists")
    # this battery is SOFTWARE verification only (the frozen W040 seam)
    with open(os.path.abspath(__file__), encoding="utf-8") as handle:
        source = handle.read()
    if "no PHYSICAL PASS is claimed or implied" not in source:
        return fail(name, "the battery's own SOFTWARE-class disclosure "
                          "drifted")
    return ok(name, "SOFTWARE-class evidence only; EVID-002..008 open; the "
              "DEC-0099/W048 disclosures carried in the evidence doc")


# ---------------------------------------------------------------------------
# the runner
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Result] = []
    results.append(case_01_frozen_vocabularies())
    results.append(case_02_full_lifecycle_over_converged_authority())
    results.append(case_03_consent_economics_canonical())
    results.append(case_04_consent_attestation_closed_loop())
    results.append(case_05_canonical_lease_gate())
    results.append(case_06_traffic_admission_quota())
    results.append(case_07_rate_limit_gate())
    results.append(case_08_emergency_stop_canonical_revocation())
    results.append(case_09_authority_side_revocation_observed())
    results.append(case_10_consent_withdrawal_terminates())
    results.append(case_11_lease_expiry_observed())
    results.append(case_12_duck_typed_views_and_scope_projection())
    results.append(case_13_gateway_read_window())
    results.append(case_14_converged_client_citations())
    results.append(case_15_child_authority_citation_surface())
    results.append(case_16_citation_ledger_revocation())
    results.append(case_17_w048_stays_accepted_not_restored())
    results.append(case_18_lock119_discipline())
    results.append(case_19_determinism())
    results.append(case_20_frozen_core_unchanged())
    results.append(case_21_pr_delta_authorization())
    results.append(case_22_evidence_honesty())

    print("ADCOS provider/buyer client convergence battery "
          "(M014 — the DEC-0099 re-baseline)")
    print("=" * 78)
    for case_name, passed, detail in results:
        print("[%s] %-52s %s"
              % ("ok  " if passed else "FAIL", case_name, detail))
    print("-" * 78)
    passed_count = sum(1 for _, flag, _ in results if flag)
    if passed_count == len(results):
        print("Result: PASS (%d/%d cases)" % (passed_count, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed_count, len(results)))
    for case_name, flag, detail in results:
        if not flag:
            print("  FAILED %s: %s" % (case_name, detail))
    return 1


if __name__ == "__main__":
    if "--determinism-stream" in sys.argv:
        stream = _determinism_stream()
        for key in sorted(stream):
            print("%s=%s" % (key, stream[key]))
        sys.exit(0)
    sys.exit(main())
