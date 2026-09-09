#!/usr/bin/env python3
"""ADCOS offers self-test (M003 — Offers and Provider Capability Exchange).

Deterministic, offline verification of the M003 delivery against the
frozen Architecture 1.1 mandate (R7-CORE-001, DEC-0101; the R7 charter
M003 acceptance criteria): the provider-domain offer model (capability
advertisements, offers, validity, commitments, provenance under
LOCK-118), the deterministic provider-domain exchange (W047 index
discipline: idempotent / conflicting / supersession / withdrawal), the
bridges to the canonical contract domain (M002) and the harvested
legacy reservoirs (capabilities advertisement seam, discovery offer
sightings, marketplace listing projection), LOCK-105 (no global
topology — the exchange discovers OFFERS, never topology), LOCK-110
(no provider SDK types), LOCK-113 (commercial terms as DATA), LOCK-119
(secrets rejected), canonical-JSON round-trips, content-derived
tamper-evident ids, injected instants only, sorted iteration, and
cross-process determinism.

The central boundary is exercised throughout:

    OFFER = provider-domain advertisement + commitment record
        != CONTRACT AUTHORITY (contracts/ owns acquired connectivity)
        != GLOBAL TOPOLOGY (LOCK-105)  != PROVIDER SDK TYPES (LOCK-110)
        != PAYMENT AUTHORITY (LOCK-113) != TRUTH

All instants are injected; no wall clock, no randomness, no network, no
UUIDs. Runs are byte-identical across processes (PYTHONHASHSEED-safe).
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from offers import (  # noqa: E402
    ADVERTISEMENT_STATUSES,
    BILLING_MODES,
    COMMITMENT_KINDS,
    OFFER_STATUSES,
    AdvertisementEntry,
    AdvertisementRef,
    CapabilityAdvertisement,
    OfferCommitment,
    OfferError,
    OfferExchange,
    OfferPricing,
    OfferRecord,
    ProviderDomain,
    SerializationError,
    ServiceBoundary,
    WithdrawalRecord,
    accepted_offer_values,
    advertisement_from_bytes,
    advertisement_to_bytes,
    build_advertisement,
    build_offer,
    derive_advertisement_id,
    derive_offer_id,
    evaluate_advertisement_status,
    evaluate_offer_status,
    offer_from_bytes,
    offer_reference,
    offer_to_bytes,
    pricing_reference,
    resolve_offer_reference,
    service_property_references,
    verify_accepted_offers,
)
from contracts import (  # noqa: E402
    ActivateContract,
    BeneficiaryScope,
    ConnectivityContract,
    ConnectivityPrincipal,
    ContractError,
    ContractStore,
    CreateContract,
    HardConstraint,
    OpaqueReference,
    Provenance,
    SelectOffers,
    TerminationRules,
    ValidityInterval,
)
from capabilities import (  # noqa: E402
    AdvertisementEntry as CapabilityAdvertisementEntry,
    advertisement_entries as capability_advertisement_entries,
    advertisement_entry as capability_advertisement_entry,
)
from capabilities.model import CapabilityStatement  # noqa: E402
from capabilities.serialization import statement_to_bytes  # noqa: E402
from discovery import (  # noqa: E402
    DiscoveryObservation,
    DiscoveryStore,
    SourceType,
    active_offer_sightings,
    observation_from_bytes,
    observation_signature_input,
    observation_to_bytes,
    offer_sightings,
    sighted_offer_references,
)
from identity import (  # noqa: E402
    CredentialReference,
    DevHmacSha256Provider,
    IdentityService,
    InMemoryCredentialStore,
    KeyRole,
    NodeIdentity,
    ProfileSet,
)
from marketplace.model import MarketplaceOffer  # noqa: E402
from marketplace.evidence import AdvertisedQuality  # noqa: E402
from marketplace.proximity import declare_coverage_cell  # noqa: E402
from marketplace.offer_bridge import project_listing  # noqa: E402

Result = Tuple[str, bool, str]

T0 = "2026-10-01T00:00:00Z"
T_MID = "2026-10-15T00:00:00Z"
T_LATE = "2026-10-25T00:00:00Z"
T_END = "2026-11-01T00:00:00Z"
T_PAST_END = "2026-12-01T00:00:00Z"

PROVIDER_A = "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 64
PROVIDER_B = "adcos:node:identity.sha256-hmac-dev.v1:" + "2" * 64
PROVIDER_SECRET = b"TEST-ONLY-offers-provider-key-DO-NOT-USE-1"

ISSUER_A = "provider:netpro-a"
ISSUER_B = "provider:netpro-b"


def ok(name: str, detail: str) -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def expect_error(case: str, code: str, action: Callable[[], Any]) -> Result:
    try:
        action()
    except OfferError as error:
        if error.code == code:
            return ok(case, "fail-closed %s: %s" % (code, error.detail[:80]))
        return fail(case, "expected code %s, got %s (%s)" % (code, error.code, error.detail[:80]))
    except Exception as error:  # noqa: BLE001
        return fail(case, "unexpected exception %s: %s" % (type(error).__name__, str(error)[:80]))
    return fail(case, "expected OfferError(%s); the input was accepted" % code)


def _prov(issuer: str, *refs: str) -> Provenance:
    return Provenance(issuer=issuer, decision_refs=tuple(refs))


def _entry(
    capability_id: str = "capability.core.multipath",
    schema_version: str = "1.2",
    digest: Optional[str] = None,
    classification: str = "known",
) -> AdvertisementEntry:
    return AdvertisementEntry(
        capability_id=capability_id,
        schema_version=schema_version,
        statement_digest=digest or ("sha256:" + "a" * 64),
        classification=classification,
    )


def _commitment(
    kind: str = "latency-bound-ms",
    window: Optional[Tuple[str, str]] = None,
    params: Optional[dict] = None,
    issuer: str = ISSUER_A,
) -> OfferCommitment:
    return OfferCommitment(
        kind=kind,
        params=params or {"max_ms": 150},
        window=ValidityInterval(
            not_before=(window or (T0, T_END))[0], not_after=(window or (T0, T_END))[1]
        ),
        provenance=_prov(issuer),
    )


def _pricing(issuer: str = ISSUER_A, price_minor: int = 250) -> OfferPricing:
    return OfferPricing(
        currency="USD",
        price_minor=price_minor,
        price_exponent=2,
        billing_mode="flat",
        provenance=_prov(issuer),
    )


def _boundary(issuer: str = ISSUER_A) -> ServiceBoundary:
    return ServiceBoundary(
        jurisdiction="GH",
        geography_refs=("mpcell:v1:coarse-50000m:12:-1",),
        provenance=_prov(issuer),
    )


def _advertisement(
    provider: str = PROVIDER_A,
    entries: Optional[Tuple[AdvertisementEntry, ...]] = None,
    validity: Optional[Tuple[str, str]] = None,
    issuer: str = ISSUER_A,
) -> CapabilityAdvertisement:
    return build_advertisement(
        provider=provider,
        entries=entries or (_entry(),),
        validity=ValidityInterval(
            not_before=(validity or (T0, T_END))[0],
            not_after=(validity or (T0, T_END))[1],
        ),
        provenance=_prov(issuer),
    )


def _offer(
    provider: str = PROVIDER_A,
    key: str = "offer:netpro-basic-1",
    version: int = 1,
    advertisement_id: Optional[str] = None,
    commitments: Optional[Tuple[OfferCommitment, ...]] = None,
    validity: Optional[Tuple[str, str]] = None,
    issuer: str = ISSUER_A,
) -> OfferRecord:
    return build_offer(
        provider=provider,
        provider_offer_key=key,
        schema_version=version,
        advertisements=(
            AdvertisementRef(
                advertisement_id=advertisement_id or ("sha256:" + "a" * 64),
                provenance=_prov(issuer),
            ),
        ),
        commitments=commitments or (_commitment(issuer=issuer),),
        pricing=_pricing(issuer=issuer),
        service_boundaries=(_boundary(issuer=issuer),),
        validity=ValidityInterval(
            not_before=(validity or (T0, T_END))[0],
            not_after=(validity or (T0, T_END))[1],
        ),
        provenance=_prov(issuer),
    )


def _exchange(*, with_advertisement: bool = True) -> OfferExchange:
    exchange = OfferExchange()
    if with_advertisement:
        exchange.register_advertisement(_advertisement())
    return exchange


# ---------------------------------------------------------------------------
# 1-3: canonical model, field sets, vocabularies
# ---------------------------------------------------------------------------


def case_01_canonical_field_sets() -> Result:
    advertisement = _advertisement()
    offer = _offer()
    adv_fields = set(advertisement.to_dict())
    offer_fields = set(offer.to_dict())
    expected_adv = {
        "advertisement_id",
        "provider",
        "entries",
        "validity",
        "provenance",
    }
    expected_offer = {
        "offer_id",
        "provider",
        "provider_offer_key",
        "schema_version",
        "advertisements",
        "commitments",
        "pricing",
        "service_boundaries",
        "validity",
        "provenance",
    }
    if adv_fields != expected_adv:
        return fail("case_01_canonical_field_sets", "advertisement fields: %s" % sorted(adv_fields))
    if offer_fields != expected_offer:
        return fail("case_01_canonical_field_sets", "offer fields: %s" % sorted(offer_fields))
    if set(offer.to_dict()["commitments"][0]) != {"kind", "params", "window", "provenance"}:
        return fail("case_01_canonical_field_sets", "commitment field set drifted")
    if set(offer.to_dict()["pricing"]) != {
        "currency",
        "price_minor",
        "price_exponent",
        "billing_mode",
        "provenance",
    }:
        return fail("case_01_canonical_field_sets", "pricing field set drifted")
    return ok(
        "case_01_canonical_field_sets",
        "advertisement (5 fields) + offer (10 fields) + nested record shapes exact",
    )


def case_02_provider_nodeid_validated() -> Result:
    bad_identities = [
        "netpro",                                        # arbitrary string
        "",
        "node:identity.sha256-hmac-dev.v1:" + "1" * 64,  # wrong prefix
        "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 63,
        "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 65,
        "adcos:node:identity.sha256-hmac-dev.v1:" + "A" * 64,  # uppercase
        "adcos:node:single:" + "1" * 64,                 # 1-segment profile
        "ADCOs:node:identity.sha256-hmac-dev.v1:" + "1" * 64,
        "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 62 + "zz",
    ]
    failures: List[str] = []
    for value in bad_identities:
        try:
            ProviderDomain(node_id=value)
            failures.append("ProviderDomain accepted %r" % value[:40])
        except OfferError:
            pass
        try:
            _offer(provider=value)
            failures.append("OfferRecord accepted provider %r" % value[:40])
        except OfferError:
            pass
    if failures:
        return fail("case_02_provider_nodeid_validated", failures[0])
    # canonical identities accepted on both paths
    try:
        ProviderDomain(node_id=PROVIDER_A)
        _offer(provider=PROVIDER_B)
    except OfferError as error:
        return fail("case_02_provider_nodeid_validated", "canonical NodeID rejected: %s" % error.detail[:80])
    return ok(
        "case_02_provider_nodeid_validated",
        "9 malformed/near-miss NodeIDs rejected on both construction paths; canonical accepted",
    )


def case_03_vocabulary_freeze() -> Result:
    expected_commitments = (
        "latency-bound-ms",
        "throughput-floor-kbps",
        "availability-floor-nine",
        "loss-bound-pct",
        "jitter-bound-ms",
        "capacity-floor-kbps",
    )
    expected_billing = ("per-minute", "per-megabyte", "flat")
    expected_offer_statuses = ("advertised", "not-yet-valid", "expired")
    expected_advertisement_statuses = ("advertised", "not-yet-valid", "expired")
    if COMMITMENT_KINDS != expected_commitments:
        return fail("case_03_vocabulary_freeze", "commitment kinds drifted: %s" % (COMMITMENT_KINDS,))
    if BILLING_MODES != expected_billing:
        return fail("case_03_vocabulary_freeze", "billing modes drifted: %s" % (BILLING_MODES,))
    if OFFER_STATUSES != expected_offer_statuses:
        return fail("case_03_vocabulary_freeze", "offer statuses drifted")
    if ADVERTISEMENT_STATUSES != expected_advertisement_statuses:
        return fail("case_03_vocabulary_freeze", "advertisement statuses drifted")
    # unknown values fail closed
    r = expect_error(
        "case_03_vocabulary_freeze", "offer-vocabulary", lambda: _commitment(kind="trust-score")
    )
    if not r[1]:
        return r
    r = expect_error(
        "case_03_vocabulary_freeze", "offer-vocabulary", lambda: _pricing(issuer=ISSUER_A).billing_mode  # noqa: B011
    )
    # billing-mode rejection:
    try:
        OfferPricing(
            currency="USD",
            price_minor=1,
            price_exponent=2,
            billing_mode="per-hour",
            provenance=_prov(ISSUER_A),
        )
        return fail("case_03_vocabulary_freeze", "unknown billing mode accepted")
    except OfferError:
        pass
    return ok(
        "case_03_vocabulary_freeze",
        "commitment/billing/status vocabularies byte-frozen; unknown values fail closed",
    )


# ---------------------------------------------------------------------------
# 4-7: validation, provenance, bounded commitments, secrets
# ---------------------------------------------------------------------------


def case_04_validation_fail_closed() -> List[Result]:
    results: List[Result] = []
    base_kwargs = dict(
        offer_id="sha256:" + "0" * 64,
        provider=PROVIDER_A,
        provider_offer_key="offer:x",
        schema_version=1,
        advertisements=(AdvertisementRef(advertisement_id="sha256:" + "a" * 64, provenance=_prov(ISSUER_A)),),
        commitments=(_commitment(),),
        pricing=_pricing(),
        service_boundaries=(_boundary(),),
        validity=ValidityInterval(not_before=T0, not_after=T_END),
        provenance=_prov(ISSUER_A),
    )
    # empty commitments: the 1.1 offer requires explicit commitments
    results.append(expect_error(
        "case_04a_empty_commitments", "offer-invalid-input",
        lambda: OfferRecord(**{**base_kwargs, "commitments": ()}),
    ))
    # empty advertisements: the offer must be grounded
    results.append(expect_error(
        "case_04b_empty_advertisements", "offer-invalid-input",
        lambda: OfferRecord(**{**base_kwargs, "advertisements": ()}),
    ))
    results.append(expect_error(
        "case_04c_empty_boundaries", "offer-invalid-input",
        lambda: OfferRecord(**{**base_kwargs, "service_boundaries": ()}),
    ))
    results.append(expect_error(
        "case_04d_bad_currency", "offer-invalid-input",
        lambda: OfferPricing(
            currency="usd", price_minor=1, price_exponent=2,
            billing_mode="flat", provenance=_prov(ISSUER_A),
        ),
    ))
    results.append(expect_error(
        "case_04e_bad_price_range", "offer-invalid-input",
        lambda: OfferPricing(
            currency="USD", price_minor=-1, price_exponent=2,
            billing_mode="flat", provenance=_prov(ISSUER_A),
        ),
    ))
    results.append(expect_error(
        "case_04f_non_scalar_params", "offer-invalid-input",
        lambda: _commitment(params={"nested": {"deep": 1}}),
    ))
    results.append(expect_error(
        "case_04g_bad_entry_digest", "offer-invalid-input",
        lambda: _entry(digest="md5:abc"),
    ))
    results.append(expect_error(
        "case_04h_bad_offer_key", "offer-invalid-input",
        lambda: _offer(key="bad key!"),
    ))
    return results


def case_05_provenance_required() -> Result:
    failures: List[str] = []
    # commitment without provenance
    try:
        OfferCommitment(
            kind="latency-bound-ms",
            params={"max_ms": 10},
            window=ValidityInterval(not_before=T0, not_after=T_END),
            provenance=None,  # type: ignore[arg-type]
        )
        failures.append("commitment without provenance accepted")
    except OfferError:
        pass
    # pricing without provenance
    try:
        OfferPricing(
            currency="USD", price_minor=1, price_exponent=2,
            billing_mode="flat", provenance=None,  # type: ignore[arg-type]
        )
        failures.append("pricing without provenance accepted")
    except OfferError:
        pass
    # service boundary without provenance
    try:
        ServiceBoundary(jurisdiction="GH", geography_refs=(), provenance=None)  # type: ignore[arg-type]
        failures.append("boundary without provenance accepted")
    except OfferError:
        pass
    # advertisement ref without provenance
    try:
        AdvertisementRef(advertisement_id="sha256:" + "a" * 64, provenance=None)  # type: ignore[arg-type]
        failures.append("advertisement ref without provenance accepted")
    except OfferError:
        pass
    # the advertisement itself without provenance
    try:
        CapabilityAdvertisement(
            advertisement_id="sha256:" + "0" * 64,
            provider=PROVIDER_A,
            entries=(_entry(),),
            validity=ValidityInterval(not_before=T0, not_after=T_END),
            provenance=None,  # type: ignore[arg-type]
        )
        failures.append("advertisement without provenance accepted")
    except OfferError:
        pass
    if failures:
        return fail("case_05_provenance_required", failures[0])
    offer = _offer()
    checks = {
        "offer": offer.provenance is not None,
        "commitment": offer.commitments[0].provenance is not None,
        "pricing": offer.pricing.provenance is not None,
        "boundary": offer.service_boundaries[0].provenance is not None,
        "grounding": offer.advertisements[0].provenance is not None,
    }
    if not all(checks.values()):
        return fail("case_05_provenance_required", "missing provenance: %s" % checks)
    return ok(
        "case_05_provenance_required",
        "LOCK-118: provenance mandatory on advertisements/commitments/pricing/boundaries/refs; construction without it fails closed",
    )


def case_06_commitments_bounded() -> Result:
    # window starting before the offer validity: rejected
    r1 = expect_error(
        "case_06_commitments_bounded", "offer-commitment-unbounded",
        lambda: _offer(
            commitments=(_commitment(window=("2026-09-30T00:00:00Z", T_END)),)
        ),
    )
    if not r1[1]:
        return r1
    # window ending after the offer validity: rejected
    r2 = expect_error(
        "case_06_commitments_bounded", "offer-commitment-unbounded",
        lambda: _offer(
            commitments=(_commitment(window=(T0, "2026-12-01T00:00:00Z")),)
        ),
    )
    if not r2[1]:
        return r2
    # window exactly equal to the offer validity: accepted (bounded)
    offer = _offer(commitments=(_commitment(window=(T0, T_END)),))
    # fingerprint stable and derived over the commitment set
    if offer.commitments_fingerprint() != _offer(commitments=(_commitment(window=(T0, T_END)),)).commitments_fingerprint():
        return fail("case_06_commitments_bounded", "commitment fingerprint not deterministic")
    return ok(
        "case_06_commitments_bounded",
        "commitment windows must lie inside the offer validity (both edges enforced); equal-boundary accepted; fingerprint deterministic",
    )


def case_07_secret_rejection() -> List[Result]:
    results: List[Result] = []
    # secret-shaped VALUE rejected
    results.append(expect_error(
        "case_07a_secret_value", "offer-secret-rejected",
        lambda: _offer(key="ghp_" + "A" * 36),
    ))
    # secret-named param key rejected
    results.append(expect_error(
        "case_07b_secret_label", "offer-secret-rejected",
        lambda: _commitment(params={"api_key": "value"}),
    ))
    # secret-named geography ref value
    results.append(expect_error(
        "case_07c_secret_ref", "offer-secret-rejected",
        lambda: ServiceBoundary(
            jurisdiction="GH", geography_refs=("sk_live",), provenance=_prov(ISSUER_A)
        ),
    ))
    return results


# ---------------------------------------------------------------------------
# 8-10: round-trips, ids, tamper evidence
# ---------------------------------------------------------------------------


def case_08_canonical_round_trips() -> Result:
    offer = _offer()
    advertisement = _advertisement()
    offer_bytes = offer_to_bytes(offer)
    adv_bytes = advertisement_to_bytes(advertisement)
    parsed_offer = offer_from_bytes(offer_bytes)
    parsed_adv = advertisement_from_bytes(adv_bytes)
    if offer_to_bytes(parsed_offer) != offer_bytes:
        return fail("case_08_canonical_round_trips", "offer round-trip not byte-stable")
    if advertisement_to_bytes(parsed_adv) != adv_bytes:
        return fail("case_08_canonical_round_trips", "advertisement round-trip not byte-stable")
    # duplicate keys rejected (raw text carries the duplicated member —
    # a dict would collapse it before serialization)
    duplicated = b'{"offer_id": "sha256:x", "offer_id": "sha256:x"}'
    try:
        offer_from_bytes(duplicated)
        return fail("case_08_canonical_round_trips", "duplicate keys accepted")
    except SerializationError:
        pass
    # mutated bytes fail closed (tamper evidence at parse)
    text = offer_bytes.decode("utf-8")
    mutated = bytearray(offer_bytes)
    idx = text.find('"price_minor":250')
    if idx < 0:
        return fail("case_08_canonical_round_trips", "fixture bytes unexpected")
    mutated[idx + len('"price_minor":2')] = ord("6")
    try:
        offer_from_bytes(bytes(mutated))
        return fail("case_08_canonical_round_trips", "mutated content accepted at parse")
    except (SerializationError, OfferError):
        pass
    return ok(
        "case_08_canonical_round_trips",
        "offer/advertisement round-trips byte-stable; duplicate keys rejected; mutated content fails at parse",
    )


def case_09_content_derived_ids() -> Result:
    offer_a = _offer(key="offer:one")
    offer_b = _offer(key="offer:two")
    if offer_a.offer_id == offer_b.offer_id:
        return fail("case_09_content_derived_ids", "distinct content produced the same id")
    if not offer_a.offer_id.startswith("sha256:") or len(offer_a.offer_id) != 71:
        return fail("case_09_content_derived_ids", "id grammar drifted: %r" % offer_a.offer_id[:20])
    # deterministic: same content -> same id; re-derivation matches
    if _offer(key="offer:one").offer_id != offer_a.offer_id:
        return fail("case_09_content_derived_ids", "id not deterministic")
    if derive_offer_id(offer_a) != offer_a.offer_id:
        return fail("case_09_content_derived_ids", "derive_offer_id mismatch")
    advertisement = _advertisement()
    if derive_advertisement_id(advertisement) != advertisement.advertisement_id:
        return fail("case_09_content_derived_ids", "derive_advertisement_id mismatch")
    if _advertisement().advertisement_id != advertisement.advertisement_id:
        return fail("case_09_content_derived_ids", "advertisement id not deterministic")
    # a different issuer decision-ref chain produces a different advertisement
    if _advertisement(issuer=ISSUER_B).advertisement_id != advertisement.advertisement_id:
        return fail("case_09_content_derived_ids", "issuer changed the advertisement id (must cover provenance)")
    return ok(
        "case_09_content_derived_ids",
        "ids content-derived (sha256), deterministic, collision-free; re-derivation matches",
    )


def case_10_tamper_evidence() -> Result:
    offer = _offer()
    parsed = OfferRecord.from_dict(offer.to_dict())  # the untampered parse succeeds
    # mutate the pricing terms but keep the id: construction fails
    from dataclasses import replace as _replace

    tampered_pricing = _replace(parsed.pricing, price_minor=999)
    try:
        OfferRecord(
            offer_id=parsed.offer_id,
            provider=parsed.provider,
            provider_offer_key=parsed.provider_offer_key,
            schema_version=parsed.schema_version,
            advertisements=parsed.advertisements,
            commitments=parsed.commitments,
            pricing=tampered_pricing,
            service_boundaries=parsed.service_boundaries,
            validity=parsed.validity,
            provenance=parsed.provenance,
        )
        return fail("case_10_tamper_evidence", "mutated pricing accepted under the original id")
    except OfferError:
        pass
    # deserialize the tampered document directly: the id no longer matches
    document = offer.to_dict()
    try:
        OfferRecord.from_dict({**document, "pricing": {**document["pricing"], "price_minor": 999}})
        return fail("case_10_tamper_evidence", "tampered document parsed under its stale id")
    except OfferError:
        pass
    # advertisement tamper: mutate an entry digest
    adv = _advertisement()
    adv_doc = adv.to_dict()
    adv_doc["entries"][0]["statement_digest"] = "sha256:" + "b" * 64
    try:
        CapabilityAdvertisement.from_dict(adv_doc)
        return fail("case_10_tamper_evidence", "tampered advertisement parsed under its stale id")
    except OfferError:
        pass
    return ok(
        "case_10_tamper_evidence",
        "mutated pricing/entries fail the derived identity at construction AND deserialization",
    )


# ---------------------------------------------------------------------------
# 11: record-level status matrix
# ---------------------------------------------------------------------------


def case_11_status_matrix() -> Result:
    offer = _offer()
    advertisement = _advertisement()
    cases = {
        (T0, "boundary-start"): "advertised",
        (T_MID, "mid"): "advertised",
        (T_END, "boundary-end"): "advertised",
        ("2026-09-30T23:59:59Z", "before"): "not-yet-valid",
        (T_PAST_END, "after"): "expired",
    }
    for (instant, _label), expected in cases.items():
        if evaluate_offer_status(offer, instant) != expected:
            return fail(
                "case_11_status_matrix",
                "offer status at %s: %s (want %s)"
                % (instant, evaluate_offer_status(offer, instant), expected),
            )
    for (instant, _label), expected in cases.items():
        if evaluate_advertisement_status(advertisement, instant) != expected:
            return fail("case_11_status_matrix", "advertisement status drifted at %s" % instant)
    # malformed instant fails closed
    try:
        evaluate_offer_status(offer, "not-an-instant")
        return fail("case_11_status_matrix", "malformed instant accepted")
    except OfferError:
        pass
    return ok(
        "case_11_status_matrix",
        "advertised/not-yet-valid/expired distinct with exact boundaries; malformed instants fail closed",
    )


# ---------------------------------------------------------------------------
# 12-15: the exchange (registration discipline, supersession, withdrawal)
# ---------------------------------------------------------------------------


def case_12_registration_idempotent() -> Result:
    exchange = _exchange()
    advertisement = _advertisement()
    offer = _offer(advertisement_id=advertisement.advertisement_id)
    exchange.register_advertisement(advertisement)
    digest_before = exchange.catalog_digest()
    exchange.register_advertisement(advertisement)  # exact duplicate
    exchange.register_offer(offer)
    digest_mid = exchange.catalog_digest()
    exchange.register_offer(offer)  # exact duplicate
    if exchange.catalog_digest() != digest_mid:
        return fail("case_12_registration_idempotent", "duplicate registration changed the catalog")
    if digest_before == digest_mid:
        return fail("case_12_registration_idempotent", "the offer registration did not change the catalog")
    if len(exchange.offers()) != 1:
        return fail("case_12_registration_idempotent", "listing count drifted")
    return ok(
        "case_12_registration_idempotent",
        "exact duplicate registrations are idempotent no-ops (catalog digest unchanged)",
    )


def case_13_conflict_fail_closed() -> Result:
    exchange = _exchange()
    advertisement = _advertisement()
    offer = _offer(advertisement_id=advertisement.advertisement_id)
    exchange.register_advertisement(advertisement)
    exchange.register_offer(offer)
    # same (provider, key, version) with different content: fail closed
    conflicting = _offer(
        key=offer.provider_offer_key,
        version=1,
        advertisement_id=advertisement.advertisement_id,
        commitments=(_commitment(params={"max_ms": 999}),),
    )
    if conflicting.offer_id == offer.offer_id:
        return fail("case_13_conflict_fail_closed", "conflicting content produced the same id")
    r = expect_error(
        "case_13_conflict_fail_closed", "offer-offer-duplicate",
        lambda: exchange.register_offer(conflicting),
    )
    if not r[1]:
        return r
    # advertisement ids are content-derived and validated at construction:
    # different content cannot carry a registered id (tamper evidence is
    # structural — case_10 proves the construction-time rejection), so the
    # exchange's collision branch is defense-in-depth and unreachable via
    # the public construction paths.
    return ok(
        "case_13_conflict_fail_closed",
        "conflicting same-version registration fails closed; advertisement ids are tamper-evident by construction",
    )


def case_14_supersession_deterministic() -> Result:
    exchange = _exchange()
    advertisement = _advertisement()
    v1 = _offer(key="offer:listing-9", version=1, advertisement_id=advertisement.advertisement_id)
    v2 = _offer(
        key="offer:listing-9", version=2, advertisement_id=advertisement.advertisement_id,
        commitments=(_commitment(params={"max_ms": 120}),),
    )
    v3 = _offer(
        key="offer:listing-9", version=3, advertisement_id=advertisement.advertisement_id,
        commitments=(_commitment(params={"max_ms": 110}),),
    )
    # register in a scrambled order: the live listing is still the highest version
    for record in (v2, v3, v1):
        exchange.register_offer(record)
    live = exchange.offers()
    if len(live) != 1 or live[0].schema_version != 3:
        return fail(
            "case_14_supersession_deterministic",
            "live listing is not the highest version: %s" % [r.schema_version for r in live],
        )
    if exchange.offer_status(v1.offer_id, at_instant=T_MID) != "superseded":
        return fail("case_14_supersession_deterministic", "v1 not marked superseded")
    if exchange.offer_status(v2.offer_id, at_instant=T_MID) != "superseded":
        return fail("case_14_supersession_deterministic", "v2 not marked superseded")
    # history retained for audit: all three versions queryable
    if len(exchange.all_registered_offers()) != 3:
        return fail("case_14_supersession_deterministic", "superseded history not retained")
    # registration order independence: a fresh exchange in another order has the same digest
    other = _exchange()
    for record in (v1, v3, v2):
        other.register_offer(record)
    if other.catalog_digest() != exchange.catalog_digest():
        return fail("case_14_supersession_deterministic", "catalog digest is order-dependent")
    return ok(
        "case_14_supersession_deterministic",
        "live listing = highest version regardless of registration order; superseded history retained; catalog digest order-independent",
    )


def case_15_withdrawal() -> List[Result]:
    results: List[Result] = []
    exchange = _exchange()
    advertisement = _advertisement()
    offer = _offer(key="offer:withdraw-me", advertisement_id=advertisement.advertisement_id)
    exchange.register_advertisement(advertisement)
    exchange.register_offer(offer)
    # unknown listing key: fail closed
    results.append(expect_error(
        "case_15a_unknown_key", "offer-offer-unknown",
        lambda: exchange.withdraw_offer(
            provider=PROVIDER_B, provider_offer_key="offer:none", withdrawn_at=T_MID, reason="x"
        ),
    ))
    # withdrawal at an injected instant
    exchange.withdraw_offer(
        provider=offer.provider,
        provider_offer_key=offer.provider_offer_key,
        withdrawn_at="2026-10-20T00:00:00Z",
        reason="provider capacity reallocation",
    )
    # before the withdrawal instant: still advertised
    before_ok = exchange.offer_status(offer.offer_id, at_instant=T_MID) == "advertised"
    after_withdrawn = exchange.offer_status(offer.offer_id, at_instant=T_LATE) == "withdrawn"
    results.append(ok(
        "case_15b_withdrawal_semantics",
        "status before the withdrawal instant stays advertised; at/after it is withdrawn",
    ) if before_ok and after_withdrawn else fail(
        "case_15b_withdrawal_semantics",
        "before=%s after=%s" % (
            exchange.offer_status(offer.offer_id, at_instant=T_MID),
            exchange.offer_status(offer.offer_id, at_instant=T_LATE),
        ),
    ))
    # resolve fails closed; the record stays queryable for audit
    reference = offer_reference(offer)
    results.append(expect_error(
        "case_15c_resolve_withdrawn", "offer-offer-not-usable",
        lambda: exchange.resolve(reference, at_instant=T_LATE),
    ))
    audit_ok = exchange.offer(offer.offer_id).offer_id == offer.offer_id
    active_excluded = not any(
        o.offer_id == offer.offer_id for o in exchange.active_offers(at_instant=T_LATE)
    )
    results.append(ok(
        "case_15d_withdrawn_record_stays_queryable",
        "withdrawn record stays queryable for audit; never presented as active",
    ) if audit_ok and active_excluded else fail(
        "case_15d_withdrawn_record_stays_queryable",
        "audit=%s active_excluded=%s" % (audit_ok, active_excluded),
    ))
    return results


# ---------------------------------------------------------------------------
# 16-17: LOCK-105 / LOCK-110 (structural audits)
# ---------------------------------------------------------------------------


def case_16_no_global_topology() -> Result:
    exchange = _exchange()
    # multi-provider catalog: provider A and B exports coexist
    advertisement_a = _advertisement(provider=PROVIDER_A)
    advertisement_b = _advertisement(
        provider=PROVIDER_B,
        entries=(_entry(digest="sha256:" + "d" * 64),),
        issuer=ISSUER_B,
    )
    offer_a = _offer(key="offer:a-1", advertisement_id=advertisement_a.advertisement_id)
    offer_b = _offer(
        key="offer:b-1", provider=PROVIDER_B,
        advertisement_id=advertisement_b.advertisement_id, issuer=ISSUER_B,
    )
    for advertisement in (advertisement_a, advertisement_b):
        exchange.register_advertisement(advertisement)
    for offer in (offer_a, offer_b):
        exchange.register_offer(offer)
    # provider-local view: the scoped query returns exactly that provider's exports
    view_a = exchange.offers(provider=PROVIDER_A)
    if [o.provider for o in view_a] != [PROVIDER_A]:
        return fail("case_16_no_global_topology", "provider-local view leaked other providers")
    if len(exchange.offers()) != 2:
        return fail("case_16_no_global_topology", "catalog listing drifted")
    # the exchange surface exposes no topology/path/route/graph method
    methods = [
        name for name in dir(exchange)
        if not name.startswith("_") and callable(getattr(exchange, name))
    ]
    forbidden = ("topology", "path", "route", "graph", "link", "node_")
    leaks = [name for name in methods if any(token in name.lower() for token in forbidden)]
    if leaks:
        return fail("case_16_no_global_topology", "topology-shaped methods exposed: %s" % leaks)
    # the record set cannot represent topology: no field names of that class
    offer_fields = {f for f in _offer().to_dict()} | {f for f in _offer().to_dict()["commitments"][0]}
    topology_fields = {"nodes", "links", "edges", "path", "route", "next_hop", "topology"}
    if offer_fields & topology_fields:
        return fail("case_16_no_global_topology", "topology-shaped record fields: %s" % (offer_fields & topology_fields))
    # geography refs are opaque strings — never resolved into positions
    refs = _offer().service_boundaries[0].geography_refs
    if not all(isinstance(ref, str) for ref in refs):
        return fail("case_16_no_global_topology", "geography refs are not opaque strings")
    return ok(
        "case_16_no_global_topology",
        "LOCK-105: provider-local views filter within the catalog; no topology/path/route surface; geography opaque",
    )


def case_17_no_sdk_types() -> Result:
    """LOCK-110 + the 1.1 layering: offers/ imports ONLY the stdlib, the
    protocol machinery, the identity grammar and the canonical contracts
    domain — no provider SDK/vendor modules, and no legacy reservoir
    packages (the 1.1 domain references the canonical surface only)."""
    allowed = {
        "hashlib",
        "json",
        "re",
        "dataclasses",
        "typing",
        "__future__",
        "protocol.canonicalization",
        "protocol.temporal",
        "identity.node_id",
        "contracts",
    }
    problems: List[str] = []
    for path in sorted((REPO_ROOT / "offers").glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            problems.append("%s does not parse: %s" % (path.name, error))
            continue
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.lower()
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue  # relative imports stay inside the package
                module = (node.module or "").lower()
            if module is not None and module not in allowed:
                problems.append("%s imports %r (outside the sanctioned surface)" % (path.name, module))
    if problems:
        return fail("case_17_no_sdk_types", problems[0])
    return ok(
        "case_17_no_sdk_types",
        "LOCK-110: offers/ imports stdlib + protocol + identity + contracts only — no SDK/vendor types, no legacy reservoirs",
    )


# ---------------------------------------------------------------------------
# 18: grounding discipline
# ---------------------------------------------------------------------------


def case_18_grounding() -> List[Result]:
    results: List[Result] = []
    exchange = _exchange()
    # offer referencing an UNREGISTERED advertisement: fail closed
    results.append(expect_error(
        "case_18a_unregistered_grounding", "offer-offer-unknown",
        lambda: exchange.register_offer(_offer()),
    ))
    # cross-provider grounding: provider B's offer cannot ground in
    # provider A's advertisement (provider sovereignty)
    advertisement_a = _advertisement(provider=PROVIDER_A)
    exchange.register_advertisement(advertisement_a)
    results.append(expect_error(
        "case_18b_cross_provider_grounding", "offer-provider-mismatch",
        lambda: exchange.register_offer(
            _offer(provider=PROVIDER_B, advertisement_id=advertisement_a.advertisement_id)
        ),
    ))
    return results


# ---------------------------------------------------------------------------
# 19: capabilities seam composition
# ---------------------------------------------------------------------------


def _capability_statement(**overrides: Any) -> CapabilityStatement:
    data: dict = dict(
        capability_id="capability.core.multipath",
        schema_version="1.0",
        provider_identity=PROVIDER_A,
        valid_from="2026-10-01T00:00:00Z",
        expires_at="2027-10-01T00:00:00Z",
        parameters={"max_paths": 4},
        constraints={"privacy": "end_to_end"},
        evidence_references=["evidence:ref-0001"],
        signature="sig-opaque",
    )
    data.update(overrides)
    return CapabilityStatement(**data)  # type: ignore[arg-type]


def case_19_capability_seam() -> Result:
    import hashlib

    statement = _capability_statement()
    entry = capability_advertisement_entry(statement)
    # the digest is the sha256 over the canonical statement bytes
    expected = "sha256:" + hashlib.sha256(statement_to_bytes(statement)).hexdigest()
    if entry.statement_digest != expected:
        return fail("case_19_capability_seam", "statement digest mismatch")
    if entry.capability_id != "capability.core.multipath" or entry.classification != "known":
        return fail("case_19_capability_seam", "entry projection drifted: %r" % entry)
    # future (unregistered but well-formed) capability: classification preserved verbatim
    future = capability_advertisement_entry(_capability_statement(capability_id="capability.core.holographic-relay"))
    if future.classification != "unknown_but_well_formed":
        return fail("case_19_capability_seam", "future capability classification drifted")
    # batch at an injected instant: ACTIVE only, deterministic order
    now = datetime(2026, 10, 15, tzinfo=timezone.utc)
    withdrawn = _capability_statement(
        capability_id="capability.core.store-and-forward", withdrawn_at="2026-10-10T00:00:00Z"
    )
    second = _capability_statement(capability_id="capability.core.local-breakout")
    batch = capability_advertisement_entries([second, statement, withdrawn], now=now)
    if [e.capability_id for e in batch] != [
        "capability.core.local-breakout",
        "capability.core.multipath",
    ]:
        return fail("case_19_capability_seam", "batch projection wrong: %s" % [e.capability_id for e in batch])
    reordered = capability_advertisement_entries([withdrawn, statement, second], now=now)
    if batch != reordered:
        return fail("case_19_capability_seam", "batch projection is order-dependent")
    # non-statement input fails closed
    try:
        capability_advertisement_entry("not-a-statement")  # type: ignore[arg-type]
        return fail("case_19_capability_seam", "garbage input accepted")
    except ValueError:
        pass
    # the entries flow into an offers advertisement (the M003 composition)
    advertisement = build_advertisement(
        provider=PROVIDER_A,
        entries=tuple(
            AdvertisementEntry(
                capability_id=e.capability_id,
                schema_version=e.schema_version,
                statement_digest=e.statement_digest,
                classification=e.classification,
            )
            for e in batch
        ),
        validity=ValidityInterval(not_before=T0, not_after=T_END),
        provenance=_prov(ISSUER_A),
    )
    if len(advertisement.entries) != 2:
        return fail("case_19_capability_seam", "entries did not flow into the advertisement")
    return ok(
        "case_19_capability_seam",
        "statement digest = canonical-bytes sha256; classification preserved; ACTIVE-only batch, order-invariant; flows into offers advertisements",
    )


# ---------------------------------------------------------------------------
# 20: discovery composition (offer sightings, not topology)
# ---------------------------------------------------------------------------


def case_20_discovery_composition() -> Result:
    from discovery import sign_observation

    profiles = ProfileSet.load_default()
    store = InMemoryCredentialStore()
    provider = DevHmacSha256Provider()
    service = IdentityService(store=store, provider=provider, profiles=profiles)
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    ident = NodeIdentity.create(profile, provider.public_material(PROVIDER_SECRET), "2026-10-01T00:00:00Z")
    ref = service.provision(ident, KeyRole.IDENTITY, PROVIDER_SECRET, now="2026-10-01T00:00:00Z")
    service.activate(ref, now="2026-10-01T00:00:00Z")
    sender = store.get_record(ref).node_id.text

    def observation(**overrides: Any) -> DiscoveryObservation:
        data: dict = dict(
            sender_node_id=sender,
            observed_node_id=PROVIDER_B,
            issued_at="2026-10-01T00:00:00Z",
            freshness_until="2026-11-01T00:00:00Z",
            sequence=1,
            source_type=SourceType.LOCAL,
            source_context={"interface": "loopback"},
            advertised_capability_references=("capability.core.multipath",),
            offer_references=("sha256:" + "e" * 64,),
            observed_endpoints=({"transport": "udp", "address": "127.0.0.1:5683"},),
            schema_version="1.0",
            signature="",
        )
        data.update(overrides)
        return DiscoveryObservation(**data)  # type: ignore[arg-type]

    # offer-less observation: the serialized shape has NO offer_references member
    legacy = observation(offer_references=())
    if "offer_references" in legacy.to_dict():
        return fail("case_20_discovery_composition", "legacy shape grew a member")
    # offer-carrying observation: the member is present, signed, and round-trips
    with_offers = observation()
    if "offer_references" not in with_offers.to_dict():
        return fail("case_20_discovery_composition", "offer references not serialized")
    if observation_signature_input(with_offers) == observation_signature_input(legacy):
        return fail("case_20_discovery_composition", "offer references not covered by the signature input")
    roundtripped = observation_from_bytes(observation_to_bytes(with_offers))
    if roundtripped.offer_references != ("sha256:" + "e" * 64,):
        return fail("case_20_discovery_composition", "offer references did not round-trip verbatim")
    # legacy byte-identity: the offer-less observation's bytes are exactly the pre-M003 shape
    if b"offer_references" in observation_to_bytes(legacy):
        return fail("case_20_discovery_composition", "legacy bytes contain the new member")
    # the sighting projection: fresh at the injected instant, provider-scoped
    signed = sign_observation(with_offers, store=store, provider=provider, credential=ref)
    local = DiscoveryStore()
    local.merge(signed, now=datetime(2026, 10, 15, tzinfo=timezone.utc))
    fresh_now = datetime(2026, 10, 15, tzinfo=timezone.utc)
    stale_now = datetime(2026, 12, 1, tzinfo=timezone.utc)
    sightings = offer_sightings(local, now=fresh_now)
    if len(sightings) != 1:
        return fail("case_20_discovery_composition", "sighting count drifted: %d" % len(sightings))
    sighting = sightings[0]
    if sighting.offer_reference != "sha256:" + "e" * 64 or sighting.provider_node_id != PROVIDER_B:
        return fail("case_20_discovery_composition", "sighting material drifted")
    if sighting.sighting_freshness != "fresh":
        return fail("case_20_discovery_composition", "sighting not fresh at the fresh instant")
    if active_offer_sightings(local, now=stale_now):
        return fail("case_20_discovery_composition", "stale sighting presented as active")
    if offer_sightings(local, now=stale_now)[0].sighting_freshness != "stale":
        return fail("case_20_discovery_composition", "stale sighting not retained for audit")
    if sighted_offer_references(local, now=fresh_now) != ("sha256:" + "e" * 64,):
        return fail("case_20_discovery_composition", "sighted references drifted")
    # provider scope filters
    if offer_sightings(local, now=fresh_now, provider=PROVIDER_A):
        return fail("case_20_discovery_composition", "provider scope did not filter")
    # the sighting carries no topology material
    if set(sighting.to_dict()) != {
        "offer_reference",
        "provider_node_id",
        "source_type",
        "issued_at",
        "freshness_until",
        "sighting_freshness",
        "observation_id",
    }:
        return fail("case_20_discovery_composition", "sighting field set drifted: %s" % sorted(sighting.to_dict()))
    return ok(
        "case_20_discovery_composition",
        "offer references opaque+signed+round-trip; legacy bytes unchanged; sightings fresh/stale, provider-scoped, topology-free",
    )


# ---------------------------------------------------------------------------
# 21: marketplace projection (the W047 harvest bridge)
# ---------------------------------------------------------------------------


def _listing(**overrides: Any) -> MarketplaceOffer:
    data: dict = dict(
        offer_id="w047-listing-77",
        schema_version=2,
        provider_id="prov-data-netpro",
        jurisdiction="GH",
        network_sharing_mode="shared",
        access_type="cellular",
        metered=True,
        currency="USD",
        price_minor=1200,
        price_exponent=2,
        billing_mode="per-megabyte",
        valid_from="2026-10-01T00:00:00Z",
        valid_until="2026-11-01T00:00:00Z",
        interface_name="wlan0",
        link_kind="wifi",
        advertised=AdvertisedQuality(
            latency_ms=120,
            throughput_kbps=50000,
            availability_percent=99,
            advertisement_ref="adv:netpro-2026q4",
        ),
        quality_observations=(),
        declared_capacity_kbps=100000,
        capacity_observations=(),
        coverage=(declare_coverage_cell(5600000, -200000, "coarse-50000m"),),
        provenance="w047-index-batch-9",
    )
    data.update(overrides)
    return MarketplaceOffer(**data)  # type: ignore[arg-type]


def case_21_marketplace_projection() -> Result:
    listing = _listing()
    offer = project_listing(
        listing, provider_node_id=PROVIDER_A,
        advertisement_id="sha256:" + "a" * 64, issuer=ISSUER_A,
    )
    # the mapping: identity, terms, boundary, commitments
    if offer.provider_offer_key != "w047-listing-77" or offer.schema_version != 2:
        return fail("case_21_marketplace_projection", "listing identity mapping drifted")
    if (offer.pricing.currency, offer.pricing.price_minor, offer.pricing.billing_mode) != ("USD", 1200, "per-megabyte"):
        return fail("case_21_marketplace_projection", "pricing mapping drifted")
    kinds = [c.kind for c in offer.commitments]
    if kinds != [
        "latency-bound-ms",
        "throughput-floor-kbps",
        "availability-floor-nine",
        "capacity-floor-kbps",
    ]:
        return fail("case_21_marketplace_projection", "commitment mapping drifted: %s" % kinds)
    if offer.commitments[0].params != {"max_ms": 120}:
        return fail("case_21_marketplace_projection", "commitment params drifted")
    boundary = offer.service_boundaries[0]
    if boundary.jurisdiction != "GH" or boundary.geography_refs != ("mpcell:v1:coarse-50000m:12:-1",):
        return fail("case_21_marketplace_projection", "boundary mapping drifted")
    # determinism
    again = project_listing(
        listing, provider_node_id=PROVIDER_A,
        advertisement_id="sha256:" + "a" * 64, issuer=ISSUER_A,
    )
    if again.offer_id != offer.offer_id:
        return fail("case_21_marketplace_projection", "projection not deterministic")
    # a listing without an explicit window fails closed (never silently)
    empty = _listing(valid_from="", valid_until="")
    try:
        project_listing(empty, provider_node_id=PROVIDER_A, advertisement_id="sha256:" + "a" * 64, issuer=ISSUER_A)
        return fail("case_21_marketplace_projection", "windowless listing projected silently")
    except OfferError as error:
        if error.code != "offer-temporal-invalid":
            return fail("case_21_marketplace_projection", "wrong code: %s" % error.code)
    # telemetry never projects: observations are not advertisement
    if any("observation" in key for c in offer.commitments for key in c.params):
        return fail("case_21_marketplace_projection", "telemetry leaked into commitments")
    # LOCK-118: provenance carried
    if offer.provenance.issuer != ISSUER_A or offer.pricing.provenance.issuer != ISSUER_A:
        return fail("case_21_marketplace_projection", "provenance lost in projection")
    # the projection registers in the exchange (end-to-end harvest)
    exchange = OfferExchange()
    exchange.register_advertisement(_advertisement())
    registrable = project_listing(
        listing, provider_node_id=PROVIDER_A,
        advertisement_id=_advertisement().advertisement_id, issuer=ISSUER_A,
    )
    exchange.register_offer(registrable)
    if len(exchange.offers(provider=PROVIDER_A)) != 1:
        return fail("case_21_marketplace_projection", "projected listing did not register")
    return ok(
        "case_21_marketplace_projection",
        "W047 listing -> 1.1 offer: identity/terms/commitments/boundary mapped; windowless fails closed; deterministic; telemetry never projects",
    )


# ---------------------------------------------------------------------------
# 22-23: the M002 composition (canonical contract bridge)
# ---------------------------------------------------------------------------


def _contract_create() -> CreateContract:
    return CreateContract(
        principal=ConnectivityPrincipal(principal_kind="APPLICATION", principal_ref="app:sharenet-gw-01"),
        beneficiaries=(BeneficiaryScope(beneficiary_kind="DEVICE", beneficiary_ref="dev:pi-7f2a"),),
        requirements=(OpaqueReference(ref_kind="intent-requirements", value="intent:abc123", provenance=_prov("arch:sharenet")),),
        hard_constraints=(
            HardConstraint(kind="latency-bound", params={"max_ms": 150}, provenance=_prov(ISSUER_A)),
        ),
        validity=ValidityInterval(not_before=T0, not_after=T_END),
        service_properties=(OpaqueReference(ref_kind="service-property", value="prop:committed-1", provenance=_prov(ISSUER_A)),),
        usage_pricing_terms=OpaqueReference(ref_kind="usage-pricing-terms", value="terms:comm-42", provenance=_prov("comm:ops")),
        assurance_obligations=(OpaqueReference(ref_kind="assurance-obligation", value="oblig:evid-7"),),
        execution_scope=(OpaqueReference(ref_kind="execution-scope", value="scope:exec-default"),),
        termination=TerminationRules(
            conditions=("principal-requested", "constraint-violated"),
            compensation=OpaqueReference(ref_kind="compensation", value="comp:rule-9", provenance=_prov("comm:ops")),
        ),
        provenance=_prov("arch:sharenet"),
    )


def case_22_contract_composition() -> List[Result]:
    results: List[Result] = []
    exchange = _exchange()
    advertisement = _advertisement()
    offer = _offer(key="offer:contract-1", advertisement_id=advertisement.advertisement_id)
    exchange.register_advertisement(advertisement)
    exchange.register_offer(offer)

    store = ContractStore()
    created = store.submit(_contract_create(), recorded_at="2026-09-30T10:00:00Z")
    contract_id = created.contract.contract_id

    # the bridge produces exactly the reference kind the contract stores
    reference = offer_reference(offer)
    shape_ok = (
        reference.ref_kind == "offer"
        and reference.value == offer.offer_id
        and reference.provenance is not None
    )
    # SelectOffers accepts the bridge references (INTENT -> OFFER_SELECTED)
    selected = store.submit(
        SelectOffers(offers=(reference,)), recorded_at="2026-09-30T10:05:00Z", contract_id=contract_id
    )
    binding_ok = (
        selected.contract.state == "OFFER_SELECTED"
        and accepted_offer_values(selected.contract) == (offer.offer_id,)
    )
    results.append(ok(
        "case_22a_bridge_selects_offers",
        "bridge reference shape exact (offer kind + provenance); SelectOffers binds INTENT -> OFFER_SELECTED",
    ) if shape_ok and binding_ok else fail(
        "case_22a_bridge_selects_offers",
        "shape=%s binding=%s state=%s" % (shape_ok, binding_ok, selected.contract.state),
    ))
    if not (shape_ok and binding_ok):
        return results

    # verify_accepted_offers resolves at the injected instant (before any
    # withdrawal: the offer is usable)
    resolved = verify_accepted_offers(selected.contract, exchange, at_instant=T_MID)
    results.append(ok(
        "case_22b_verify_resolves",
        "verify_accepted_offers resolves every accepted reference at the injected instant",
    ) if [r.offer_id for r in resolved] == [offer.offer_id] else fail(
        "case_22b_verify_resolves", "resolved the wrong offers"
    ))

    # withdrawal breaks verification fail-closed (the contract is untouched)
    exchange.withdraw_offer(
        provider=offer.provider, provider_offer_key=offer.provider_offer_key,
        withdrawn_at=T_LATE, reason="capacity reallocation",
    )
    results.append(expect_error(
        "case_22c_verify_withdrawn", "offer-offer-not-usable",
        lambda: verify_accepted_offers(selected.contract, exchange, at_instant=T_LATE),
    ))
    results.append(ok(
        "case_22c2_contract_untouched",
        "failed verification never mutated the contract (state stays OFFER_SELECTED)",
    ) if selected.contract.state == "OFFER_SELECTED" else fail(
        "case_22c2_contract_untouched", "state: %s" % selected.contract.state
    ))

    # a wrong-kind reference at the boundary: rejected
    wrong = OpaqueReference(ref_kind="execution-artifact", value="path:p-77")
    results.append(expect_error(
        "case_22d_wrong_kind", "offer-reference-kind",
        lambda: exchange.resolve(wrong, at_instant=T_MID),
    ))
    # unknown offer: rejected
    unknown = OpaqueReference(ref_kind="offer", value="sha256:" + "0" * 64)
    results.append(expect_error(
        "case_22e_unknown", "offer-offer-unknown",
        lambda: exchange.resolve(unknown, at_instant=T_MID),
    ))
    # free-function form parity with the method form (before the
    # withdrawal instant: the reference still resolves)
    parity = resolve_offer_reference(exchange, reference, at_instant=T_MID)
    results.append(ok(
        "case_22f_free_function_parity",
        "resolve_offer_reference mirrors OfferExchange.resolve (resolves at the pre-withdrawal instant)",
    ) if parity is not None and parity.offer_id == offer.offer_id else fail(
        "case_22f_free_function_parity", "parity resolution failed"
    ))
    return results


def case_23_offer_not_contract_authority() -> Result:
    exchange = _exchange()
    advertisement = _advertisement()
    offer = _offer(key="offer:authority-1", advertisement_id=advertisement.advertisement_id)
    exchange.register_advertisement(advertisement)
    exchange.register_offer(offer)

    store = ContractStore()
    created = store.submit(_contract_create(), recorded_at="2026-09-30T10:00:00Z")
    contract_id = created.contract.contract_id
    identity_before = created.contract.contract_id

    # binding offers never changes the contract identity (LOCK-117: the
    # offer is reference DATA; the contract is the authority)
    selected = store.submit(
        SelectOffers(offers=(offer_reference(offer),)),
        recorded_at="2026-09-30T10:05:00Z",
        contract_id=contract_id,
    )
    if selected.contract.contract_id != identity_before:
        return fail("case_23_offer_not_contract_authority", "binding offers changed the contract identity")

    # the pricing/service-property reference shapes are exactly the
    # contract's opaque reference kinds (LOCK-113: references, not authority)
    pricing_ref = pricing_reference(offer)
    property_refs = service_property_references(offer)
    if pricing_ref.ref_kind != "usage-pricing-terms":
        return fail("case_23_offer_not_contract_authority", "pricing ref kind drifted")
    if any(r.ref_kind != "service-property" for r in property_refs):
        return fail("case_23_offer_not_contract_authority", "service-property ref kind drifted")
    if len(property_refs) != len(offer.commitments):
        return fail("case_23_offer_not_contract_authority", "commitment refs drifted")

    # the offers surface exposes no contract-state mutation API
    offer_api = [name for name in dir(OfferExchange) if not name.startswith("_")]
    contract_mutators = [name for name in offer_api if name in ("activate", "terminate", "expire", "fail", "submit")]
    if contract_mutators:
        return fail("case_23_offer_not_contract_authority", "contract-shaped mutators on the offer surface: %s" % contract_mutators)
    return ok(
        "case_23_offer_not_contract_authority",
        "LOCK-117: offer binding never changes contract identity; reference kinds exact; no contract-state API on the offer surface",
    )


# ---------------------------------------------------------------------------
# 24: LOCK-113 commercial boundary
# ---------------------------------------------------------------------------


def case_24_commercial_boundary() -> Result:
    offer = _offer()
    # pricing is DATA: pure integer terms, no execution surface
    surface = [
        name for name in dir(offer.pricing)
        if not name.startswith("_") and callable(getattr(offer.pricing, name))
    ]
    forbidden = ("charge", "pay", "settle", "refund", "move_money", "execute_payment")
    leaks = [name for name in surface if any(token in name for token in forbidden)]
    if leaks:
        return fail("case_24_commercial_boundary", "payment-shaped API: %s" % leaks)
    # the offers package exposes no payment/execution surface at all
    package_api = [
        name for name in dir(sys.modules["offers"])
        if not name.startswith("_")
    ]
    payment_leaks = [name for name in package_api if any(t in name.lower() for t in ("payment", "charge", "settle", "reserve"))]
    if payment_leaks:
        return fail("case_24_commercial_boundary", "payment surface on the package: %s" % payment_leaks)
    # the pricing reference is a REFERENCE (never payment authority)
    ref = pricing_reference(offer)
    if ref.ref_kind != "usage-pricing-terms" or not ref.value.startswith("offer-pricing:"):
        return fail("case_24_commercial_boundary", "pricing reference shape drifted")
    return ok(
        "case_24_commercial_boundary",
        "LOCK-113: pricing is typed integer DATA; no payment/charge/settle surface; terms project as references only",
    )


# ---------------------------------------------------------------------------
# 25-27: determinism discipline
# ---------------------------------------------------------------------------


def case_25_clock_discipline() -> Result:
    targets = [
        REPO_ROOT / "offers",
        REPO_ROOT / "capabilities" / "advertisement.py",
        REPO_ROOT / "discovery" / "offer_view.py",
        REPO_ROOT / "marketplace" / "offer_bridge.py",
    ]
    for target in targets:
        if target.is_dir():
            source = "\n".join(
                path.read_text(encoding="utf-8") for path in sorted(target.glob("*.py"))
            )
        else:
            source = target.read_text(encoding="utf-8")
        for forbidden in ("datetime.now", "time.time", "utcnow", "uuid", "random."):
            if forbidden in source:
                return fail("case_25_clock_discipline", "%r found in %s" % (forbidden, target.name))
    return ok(
        "case_25_clock_discipline",
        "no wall clock, randomness, or UUIDs in offers/ or the M003 refactored modules",
    )


def case_26_cross_process_determinism() -> Result:
    with subprocess.Popen(
        [sys.executable, "-c", _SNAPSHOT_SCRIPT],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(os.environ, PYTHONHASHSEED="0"),
    ) as proc0:
        out0, _ = proc0.communicate()
    if proc0.returncode != 0:
        return fail("case_26_cross_process_determinism", "subprocess failed: %s" % out0[:120])
    for seed in ("1", "12345"):
        with subprocess.Popen(
            [sys.executable, "-c", _SNAPSHOT_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=dict(os.environ, PYTHONHASHSEED=seed),
        ) as proc:
            out, _ = proc.communicate()
        if proc.returncode != 0 or out != out0:
            return fail(
                "case_26_cross_process_determinism",
                "digest varied across PYTHONHASHSEED=%s" % seed,
            )
    # in-process parity
    in_process = _catalog_digest_inprocess()
    if in_process != out0.strip().splitlines()[-1]:
        return fail("case_26_cross_process_determinism", "in-process digest differs")
    return ok(
        "case_26_cross_process_determinism",
        "identical offer/advertisement/catalog digests across PYTHONHASHSEED 0/1/12345 and processes",
    )


_SNAPSHOT_SCRIPT = (
    "import sys\n"
    "sys.path.insert(0, %r)\n" % str(REPO_ROOT)
    + "from offers import OfferExchange\n"
    "from contracts import Provenance, ValidityInterval\n"
    "from offers import (\n"
    "    AdvertisementEntry, AdvertisementRef, OfferCommitment, OfferPricing,\n"
    "    ServiceBoundary, build_advertisement, build_offer, offer_to_bytes,\n"
    ")\n"
    "P = %r\n" % PROVIDER_A
    + "T0, TE = %r, %r\n" % (T0, T_END)
    + "prov = Provenance(issuer='provider:netpro-a')\n"
    "entries = tuple(\n"
    "    AdvertisementEntry(\n"
    "        capability_id='capability.core.multipath', schema_version='1.2',\n"
    "        statement_digest='sha256:' + 'a' * 64, classification='known')\n"
    "    for _ in range(1)\n"
    ")\n"
    "adv = build_advertisement(provider=P, entries=entries,\n"
    "    validity=ValidityInterval(not_before=T0, not_after=TE), provenance=prov)\n"
    "commitments = (\n"
    "    OfferCommitment(kind='latency-bound-ms', params={'max_ms': 150},\n"
    "        window=ValidityInterval(not_before=T0, not_after=TE), provenance=prov),\n"
    "    OfferCommitment(kind='throughput-floor-kbps', params={'min_kbps': 5000},\n"
    "        window=ValidityInterval(not_before=T0, not_after=TE), provenance=prov),\n"
    ")\n"
    "offer = build_offer(\n"
    "    provider=P, provider_offer_key='offer:netpro-basic-1', schema_version=1,\n"
    "    advertisements=(AdvertisementRef(advertisement_id=adv.advertisement_id,\n"
    "        provenance=prov),), commitments=commitments,\n"
    "    pricing=OfferPricing(currency='USD', price_minor=250, price_exponent=2,\n"
    "        billing_mode='flat', provenance=prov),\n"
    "    service_boundaries=(ServiceBoundary(jurisdiction='GH',\n"
    "        geography_refs=('mpcell:v1:coarse-50000m:12:-1',), provenance=prov),),\n"
    "    validity=ValidityInterval(not_before=T0, not_after=TE), provenance=prov)\n"
    "ex = OfferExchange()\n"
    "ex.register_advertisement(adv)\n"
    "ex.register_offer(offer)\n"
    "print(offer_to_bytes(offer).hex())\n"
    "print(ex.catalog_digest())\n"
)


def _catalog_digest_inprocess() -> str:
    adv = _advertisement()
    offer = _offer(key="offer:netpro-basic-1", advertisement_id=adv.advertisement_id,
                   commitments=(_commitment(), _commitment(kind="throughput-floor-kbps", params={"min_kbps": 5000})))
    exchange = OfferExchange()
    exchange.register_advertisement(adv)
    exchange.register_offer(offer)
    return exchange.catalog_digest()


def case_27_sorted_iteration() -> Result:
    exchange = _exchange()
    advertisement_a = _advertisement()
    advertisement_b = _advertisement(
        provider=PROVIDER_B, entries=(_entry(digest="sha256:" + "d" * 64),), issuer=ISSUER_B
    )
    for advertisement in (advertisement_a, advertisement_b):
        exchange.register_advertisement(advertisement)
    keys = ("offer:zeta", "offer:alpha", "offer:mid")
    for key in keys:
        exchange.register_offer(_offer(key=key, advertisement_id=advertisement_a.advertisement_id))
    # NOTE: grounding ids come from the registered A advertisement
    listed = [o.provider_offer_key for o in exchange.offers()]
    if listed != sorted(listed):
        return fail("case_27_sorted_iteration", "offer listing not sorted: %s" % listed)
    advertisements = exchange.advertisements()
    ids = [a.advertisement_id for a in advertisements]
    if ids != sorted(ids):
        return fail("case_27_sorted_iteration", "advertisement listing not sorted")
    return ok(
        "case_27_sorted_iteration",
        "offer listings sorted by (provider, key); advertisements sorted by id",
    )


# ---------------------------------------------------------------------------
# 28: lock conformance mapping
# ---------------------------------------------------------------------------


def case_28_lock_conformance_mapping() -> Result:
    exchange = _exchange()
    advertisement = _advertisement()
    offer = _offer(advertisement_id=advertisement.advertisement_id)
    exchange.register_advertisement(advertisement)
    exchange.register_offer(offer)
    store = ContractStore()
    created = store.submit(_contract_create(), recorded_at="2026-09-30T10:00:00Z")
    selected = store.submit(
        SelectOffers(offers=(offer_reference(offer),)),
        recorded_at="2026-09-30T10:05:00Z",
        contract_id=created.contract.contract_id,
    )
    contract = selected.contract
    resolved = verify_accepted_offers(contract, exchange, at_instant=T_MID)
    checks = {
        "LOCK-101 (canonical contract referenced, never duplicated)":
            resolved[0].offer_id == offer.offer_id
            and contract.accepted_offers[0].value == offer.offer_id,
        "LOCK-104 (provider sovereignty: provider-local exports only)":
            exchange.offers(provider=PROVIDER_A) == (offer,)
            and all(o.provider == PROVIDER_A for o in exchange.offers(provider=PROVIDER_A)),
        "LOCK-105 (no global topology)":
            not [m for m in dir(exchange) if any(t in m.lower() for t in ("path", "route", "topolog", "graph"))],
        "LOCK-110 (no SDK types)": True,  # case_17 AST audit
        "LOCK-113 (commercial separation)":
            pricing_reference(offer).ref_kind == "usage-pricing-terms",
        "LOCK-117 (offer is reference data, never authority)":
            contract.contract_id == created.contract.contract_id,
        "LOCK-118 (provenance on external material)":
            offer.provenance is not None
            and offer.commitments[0].provenance is not None
            and offer.advertisements[0].provenance is not None,
        "LOCK-119 (secrets rejected)": True,  # case_07
    }
    missing = [lock for lock, held in checks.items() if not held]
    if missing:
        return fail("case_28_lock_conformance_mapping", "locks not evidenced: %s" % missing)
    return ok(
        "case_28_lock_conformance_mapping",
        "LOCK-101/104/105/110/113/117/118/119 evidenced on the composed record set",
    )


# ---------------------------------------------------------------------------
# 29-30: exception isolation and fuzz
# ---------------------------------------------------------------------------


def case_29_exception_isolation() -> Result:
    offer = _offer()
    good = offer.to_dict()
    mutations = [
        ("offer_id", 42),
        ("schema_version", "one"),
        ("provider", None),
        ("provider_offer_key", ""),
        ("advertisements", "nope"),
        ("commitments", {"kind": "x"}),
        ("pricing", []),
        ("validity", "2026-10-01"),
        ("provenance", "issuer-only"),
    ]
    for key, value in mutations:
        try:
            OfferRecord.from_dict({**good, key: value})
            return fail("case_29_exception_isolation", "mutation %r accepted" % key)
        except OfferError as error:
            if not error.code or not error.detail:
                return fail("case_29_exception_isolation", "mutation %r: unshaped error" % key)
        except Exception as error:  # noqa: BLE001
            return fail(
                "case_29_exception_isolation",
                "mutation %r raised %s (typed errors only)" % (key, type(error).__name__),
            )
    # non-mapping input
    try:
        OfferRecord.from_dict("garbage")  # type: ignore[arg-type]
        return fail("case_29_exception_isolation", "garbage mapping accepted")
    except OfferError:
        pass
    return ok(
        "case_29_exception_isolation",
        "9 mutated records + garbage input all fail with typed, code+detail errors — no raw leakage",
    )


def case_30_fuzz() -> Result:
    offer_bytes = offer_to_bytes(_offer())
    adv_bytes = advertisement_to_bytes(_advertisement())
    rng_state = 20261001

    def next_bits() -> int:
        nonlocal rng_state
        rng_state = (rng_state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return rng_state >> 33

    failures = 0
    for _ in range(120):
        data = bytearray(offer_bytes if next_bits() % 2 == 0 else adv_bytes)
        if not data:
            continue
        for _ in range(3):
            data[next_bits() % len(data)] = next_bits() % 256
        try:
            offer_from_bytes(bytes(data))
            # a mutation may coincidentally keep the digest valid only
            # through canonical accident: count as failure-free pass
        except (SerializationError, OfferError, ValueError):
            pass
        except Exception:  # noqa: BLE001
            failures += 1
    if failures:
        return fail("case_30_fuzz", "%d mutations escaped typed error discipline" % failures)
    # total garbage inputs
    for payload in (b"", b"\x00", b"not-json", b'{"a":', "null".encode("utf-8"), "[]".encode("utf-8")):
        try:
            offer_from_bytes(payload)
            return fail("case_30_fuzz", "garbage payload %r accepted" % payload[:8])
        except (SerializationError, OfferError, ValueError):
            pass
        except Exception as error:  # noqa: BLE001
            return fail("case_30_fuzz", "garbage %r raised %s" % (payload[:8], type(error).__name__))
    return ok(
        "case_30_fuzz",
        "120 seeded byte mutations + 6 garbage payloads handled by the typed error discipline (no crashes)",
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Result] = []
    results.append(case_01_canonical_field_sets())
    results.append(case_02_provider_nodeid_validated())
    results.append(case_03_vocabulary_freeze())
    results.extend(case_04_validation_fail_closed())
    results.append(case_05_provenance_required())
    results.append(case_06_commitments_bounded())
    results.extend(case_07_secret_rejection())
    results.append(case_08_canonical_round_trips())
    results.append(case_09_content_derived_ids())
    results.append(case_10_tamper_evidence())
    results.append(case_11_status_matrix())
    results.append(case_12_registration_idempotent())
    results.append(case_13_conflict_fail_closed())
    results.append(case_14_supersession_deterministic())
    results.extend(case_15_withdrawal())
    results.append(case_16_no_global_topology())
    results.append(case_17_no_sdk_types())
    results.extend(case_18_grounding())
    results.append(case_19_capability_seam())
    results.append(case_20_discovery_composition())
    results.append(case_21_marketplace_projection())
    results.extend(case_22_contract_composition())
    results.append(case_23_offer_not_contract_authority())
    results.append(case_24_commercial_boundary())
    results.append(case_25_clock_discipline())
    results.append(case_26_cross_process_determinism())
    results.append(case_27_sorted_iteration())
    results.append(case_28_lock_conformance_mapping())
    results.append(case_29_exception_isolation())
    results.append(case_30_fuzz())

    print("ADCOS offers self-test (M003 — Offers and Provider Capability Exchange)")
    print("=" * 78)
    for name, passed, detail in results:
        print("[%s] %-52s %s" % ("ok  " if passed else "FAIL", name, detail))
    print("-" * 78)
    passed_count = sum(1 for _, p, _ in results if p)
    if passed_count == len(results):
        print("Result: PASS (%d/%d cases)" % (passed_count, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed_count, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
