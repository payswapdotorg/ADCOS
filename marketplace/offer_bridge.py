"""The W047 -> Architecture 1.1 offer projection bridge (M003 refactor).

The marketplace (WORK-047) is migration-reservoir material for the M003
offer exchange: this module projects ONE immutable W047 marketplace
listing onto the Architecture 1.1 provider-domain offer record
(``offers.OfferRecord``) so legacy catalog material can flow onto the
1.1 offer-exchange surface.

What the projection carries (the 1.1 §5 export list — exactly what a
provider exports for interoperability):

- the listing identity: the provider's canonical NodeID (an explicit
  bridge input — the W047 listing's ``provider_id`` is provider-assigned
  DATA, never a NodeID; the projection never invents an identity), the
  provider-assigned listing key, and the listing's schema version;
- the grounding: ONE registered capability advertisement reference
  (an explicit bridge input — an offer is grounded in its provider's
  capability advertisement, never free-floating);
- the commitments: the listing's ADVERTISED quality and declared
  capacity projected as explicit, bounded ``OfferCommitment`` records
  (latency bound, throughput floor, availability floor, capacity
  floor) — advertisement material only, never telemetry;
- the pricing terms: the W047 integer-money commercial terms projected
  verbatim (LOCK-113: terms as DATA — the W047 payment-capability
  composition and every payment semantic stays in the marketplace
  family, external to the offers domain);
- the service boundary: the listing jurisdiction plus the declared
  coverage cells as OPAQUE geography references (the quantized cell
  ids verbatim — never resolved into positions, never aggregated into
  topology);
- the validity: the listing window (BOTH endpoints REQUIRED — the 1.1
  offer model has an explicit validity interval; a legacy listing
  without a window cannot project and fails closed, never silently).

What the projection deliberately DOES NOT carry (the honest demotions):

- quality/capacity OBSERVATIONS (telemetry): advertisement is never
  observation — the 1.1 evidence/assurance track (M005) owns typed
  evidence; the projection carries the advertised dimensions only;
- the delivery substrate identity (``interface_name``/``link_kind``)
  and every NetworkPath handoff concern: execution material is
  demoted to the execution track (M006+; the matrix: "Node / Link /
  Path graph → DEMOTE → Execution model, not contract model");
- the W045 eligibility composition: policy/eligibility evaluation is
  the M004 track — the projection confers no eligibility;
- the W051 reservation/lease coordination: the commercial track (M009).

Determinism: a pure function of (listing, inputs) — content-derived
offer identity, no clock, no randomness; two projections of the same
listing with the same inputs produce byte-identical records.
"""

from __future__ import annotations

from typing import Sequence, Tuple

from offers import (
    COMMITMENT_KINDS,
    AdvertisementRef,
    OfferCommitment,
    OfferError,
    OfferPricing,
    OfferRecord,
    ServiceBoundary,
    build_offer,
)
from contracts import Provenance, ValidityInterval

from .model import MarketplaceOffer


def project_listing(
    listing: MarketplaceOffer,
    *,
    provider_node_id: str,
    advertisement_id: str,
    issuer: str,
    decision_refs: Sequence[str] = (),
) -> OfferRecord:
    """Project one W047 marketplace listing onto the 1.1 offer record.

    Fail-closed (typed errors): a non-listing input; a listing without
    an explicit validity window (both endpoints required by the 1.1
    model — the legacy optional-window surface cannot project, never
    silently); a listing whose advertised quality cannot form at least
    one commitment (the 1.1 offer requires explicit commitments).
    """
    if not isinstance(listing, MarketplaceOffer):
        raise OfferError(
            "offer-invalid-input",
            "project_listing requires a marketplace.MarketplaceOffer "
            "(found %s)" % type(listing).__name__,
        )
    if not isinstance(provider_node_id, str) or not provider_node_id:
        raise OfferError(
            "offer-invalid-input",
            "project_listing requires the provider's canonical NodeID "
            "(the W047 provider_id is DATA; the projection never invents "
            "an identity)",
        )
    if not isinstance(advertisement_id, str) or not advertisement_id:
        raise OfferError(
            "offer-invalid-input",
            "project_listing requires a registered capability advertisement "
            "id (an offer is grounded in its provider's advertisement)",
        )
    if not isinstance(issuer, str) or not issuer:
        raise OfferError(
            "offer-invalid-input",
            "project_listing requires the provenance issuer (LOCK-118)",
        )
    # the 1.1 offer model has an explicit validity interval
    if not listing.valid_from or not listing.valid_until:
        raise OfferError(
            "offer-temporal-invalid",
            "listing %s/%s has no explicit validity window — the 1.1 offer "
            "model requires one (advertised: %r..%r); the projection fails "
            "closed, never silently"
            % (listing.provider_id[:24], listing.offer_id, listing.valid_from, listing.valid_until),
        )
    try:
        validity = ValidityInterval(
            not_before=listing.valid_from, not_after=listing.valid_until
        )
    except ValueError as error:
        raise OfferError(
            "offer-temporal-invalid",
            "listing %s/%s window is not a valid 1.1 interval: %s"
            % (listing.provider_id[:24], listing.offer_id, error),
        ) from None

    provenance = Provenance(issuer=issuer, decision_refs=tuple(decision_refs))
    grounding = AdvertisementRef(
        advertisement_id=advertisement_id, provenance=provenance
    )

    # the advertised dimensions become explicit, bounded commitments
    commitments = _advertised_commitments(listing, validity, provenance)
    if not commitments:
        raise OfferError(
            "offer-invalid-input",
            "listing %s/%s advertises no projectable commitment dimensions "
            "(latency/throughput/availability/capacity all zero) — the 1.1 "
            "offer requires explicit commitments"
            % (listing.provider_id[:24], listing.offer_id),
        )

    pricing = OfferPricing(
        currency=listing.currency,
        price_minor=listing.price_minor,
        price_exponent=listing.price_exponent,
        billing_mode=listing.billing_mode,
        provenance=provenance,
    )

    boundary = ServiceBoundary(
        jurisdiction=listing.jurisdiction,
        geography_refs=tuple(bound.cell_id for bound in listing.coverage),
        provenance=provenance,
    )

    return build_offer(
        provider=provider_node_id,
        provider_offer_key=listing.offer_id,
        schema_version=listing.schema_version,
        advertisements=(grounding,),
        commitments=commitments,
        pricing=pricing,
        service_boundaries=(boundary,),
        validity=validity,
        provenance=provenance,
    )


def _advertised_commitments(
    listing: MarketplaceOffer,
    validity: ValidityInterval,
    provenance: Provenance,
) -> Tuple[OfferCommitment, ...]:
    """Project the listing's ADVERTISED quality and declared capacity
    into explicit, bounded commitments (deterministic order: the frozen
    commitment-kind vocabulary order).

    Advertisement material only — the listing's quality/capacity
    OBSERVATIONS (telemetry) are deliberately NOT projected: the 1.1
    evidence/assurance track (M005) owns typed evidence, and
    advertisement never becomes observation."""
    commitments = []
    advertised = listing.advertised
    if advertised.latency_ms > 0:
        commitments.append(
            OfferCommitment(
                kind="latency-bound-ms",
                params={"max_ms": advertised.latency_ms},
                window=validity,
                provenance=provenance,
            )
        )
    if advertised.throughput_kbps > 0:
        commitments.append(
            OfferCommitment(
                kind="throughput-floor-kbps",
                params={"min_kbps": advertised.throughput_kbps},
                window=validity,
                provenance=provenance,
            )
        )
    if advertised.availability_percent > 0:
        commitments.append(
            OfferCommitment(
                kind="availability-floor-nine",
                params={"floor_percent": advertised.availability_percent},
                window=validity,
                provenance=provenance,
            )
        )
    if listing.declared_capacity_kbps > 0:
        commitments.append(
            OfferCommitment(
                kind="capacity-floor-kbps",
                params={"min_kbps": listing.declared_capacity_kbps},
                window=validity,
                provenance=provenance,
            )
        )
    # deterministic order: the frozen vocabulary order
    order = {kind: index for index, kind in enumerate(COMMITMENT_KINDS)}
    commitments.sort(key=lambda commitment: order[commitment.kind])
    return tuple(commitments)
