"""The M003 <-> M002 bridge: offer references toward the canonical
contract domain.

Offers REFERENCE the canonical ``ConnectivityContract`` domain (LOCK-101:
``contracts/`` is the sole canonical authority for contract semantics);
they never re-implement or duplicate it. This module is the exact
reference surface:

- ``offer_reference`` — the contract-shaped ``OpaqueReference`` an
  offer produces for the canonical ``SelectOffers`` command (the exact
  ``offer`` reference kind with the offer's content-derived identity
  and provenance). The M002 contract stores these opaquely; M003 owns
  what they point at.
- ``pricing_reference`` / ``service_property_references`` — the
  commercial and committed-property reference shapes (LOCK-113: terms
  as references, never payment authority here; the contract holds the
  same opaque reference kinds).
- ``accepted_offer_values`` — read the offer reference VALUES out of a
  contract's ``accepted_offers`` (a read of opaque data; NO contract
  semantics are interpreted here — the contract stays the authority).
- ``verify_accepted_offers`` — resolve each accepted offer reference
  against the exchange at an injected instant and fail closed unless
  every referenced offer is currently USABLE (advertised, within
  validity, not withdrawn, live version). This is the offer
  authority's own verification of its references; it never mutates the
  contract, never confers eligibility (M004), and never evaluates
  policy.
"""

from __future__ import annotations

from typing import Tuple

from contracts import (
    ConnectivityContract,
    OpaqueReference,
    Provenance,
)

from .errors import OfferError, OfferReason
from .exchange import OfferExchange
from .model import OfferRecord


def offer_reference(offer: OfferRecord) -> OpaqueReference:
    """The contract-shaped reference for one offer (the exact shape the
    canonical ``SelectOffers`` command stores)."""
    if not isinstance(offer, OfferRecord):
        raise OfferError(
            OfferReason.INVALID_INPUT, "offer_reference requires an OfferRecord"
        )
    return OpaqueReference(
        ref_kind="offer",
        value=offer.offer_id,
        provenance=Provenance(
            issuer=offer.provenance.issuer,
            decision_refs=tuple(offer.provenance.decision_refs),
        ),
    )


def pricing_reference(offer: OfferRecord) -> OpaqueReference:
    """The commercial reference shape for the offer's pricing terms
    (LOCK-113: a reference to terms, never payment authority — money
    movement stays external; the contract holds the same
    ``usage-pricing-terms`` opaque reference kind)."""
    if not isinstance(offer, OfferRecord):
        raise OfferError(
            OfferReason.INVALID_INPUT, "pricing_reference requires an OfferRecord"
        )
    return OpaqueReference(
        ref_kind="usage-pricing-terms",
        value="offer-pricing:%s" % offer.offer_id,
        provenance=Provenance(
            issuer=offer.pricing.provenance.issuer,
            decision_refs=tuple(offer.pricing.provenance.decision_refs),
        ),
    )


def service_property_references(offer: OfferRecord) -> Tuple[OpaqueReference, ...]:
    """The committed-property reference shapes for the offer's explicit
    bounded commitments (the contract holds the same
    ``service-property`` opaque reference kind)."""
    if not isinstance(offer, OfferRecord):
        raise OfferError(
            OfferReason.INVALID_INPUT,
            "service_property_references requires an OfferRecord",
        )
    return tuple(
        OpaqueReference(
            ref_kind="service-property",
            value="offer-commitment:%s" % offer.offer_id,
            provenance=Provenance(
                issuer=commitment.provenance.issuer,
                decision_refs=tuple(commitment.provenance.decision_refs),
            ),
        )
        for commitment in offer.commitments
    )


def accepted_offer_values(
    contract: ConnectivityContract,
) -> Tuple[str, ...]:
    """Read the offer reference VALUES out of a contract's accepted
    offers (opaque data only — the contract stays the authority; this
    reads exactly the ``offer``-kinded references and nothing else)."""
    if not isinstance(contract, ConnectivityContract):
        raise OfferError(
            OfferReason.INVALID_INPUT,
            "accepted_offer_values requires a contracts.ConnectivityContract",
        )
    return tuple(
        reference.value
        for reference in contract.accepted_offers
        if reference.ref_kind == "offer"
    )


def verify_accepted_offers(
    contract: ConnectivityContract,
    exchange: OfferExchange,
    *,
    at_instant: str,
) -> Tuple[OfferRecord, ...]:
    """Resolve every accepted offer reference against the exchange at
    the injected instant.

    Fail-closed (typed errors, never contract mutation): a reference of
    the wrong kind, an unknown offer, or any offer that is not currently
    USABLE (withdrawn / expired / not-yet-valid / superseded) raises
    ``OfferError``. This is the offer authority verifying its own
    references — it confers no eligibility (M004) and evaluates no
    policy; the contract's authority is untouched."""
    if not isinstance(contract, ConnectivityContract):
        raise OfferError(
            OfferReason.INVALID_INPUT,
            "verify_accepted_offers requires a contracts.ConnectivityContract",
        )
    if not isinstance(exchange, OfferExchange):
        raise OfferError(
            OfferReason.INVALID_INPUT,
            "verify_accepted_offers requires an offers.OfferExchange",
        )
    resolved = []
    for i, reference in enumerate(contract.accepted_offers):
        if reference.ref_kind != "offer":
            raise OfferError(
                OfferReason.REFERENCE_KIND,
                "accepted_offers[%d] is a %s reference; the offer authority "
                "resolves exactly the offer reference kind"
                % (i, reference.ref_kind),
            )
        resolved.append(exchange.resolve(reference, at_instant=at_instant))
    return tuple(resolved)
