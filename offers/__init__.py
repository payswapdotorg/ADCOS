"""ADCOS offers package — M003: Offers and Provider Capability Exchange.

The provider-domain offer model of Architecture 1.1 (R7-CORE-001 child
M003, DEC-0101; frozen 1.1 sections 2/5/6): providers advertise
capabilities and publish offers — capability advertisements, offers,
validity, commitments and provenance (LOCK-118) — as provider-domain
objects that REFERENCE the canonical ``contracts/`` domain (M002,
DEC-0102). Offers never re-implement or duplicate contract semantics
(LOCK-101: ``contracts/`` is the sole canonical authority).

The central boundary (enforced throughout):

    OFFER = a provider-domain advertisement + commitment record
          ≠ CONTRACT AUTHORITY (contracts/ owns acquired connectivity)
          ≠ GLOBAL TOPOLOGY (LOCK-105: provider-local views only)
          ≠ PROVIDER SDK TYPES (LOCK-110: vendor types never enter)
          ≠ PAYMENT AUTHORITY (LOCK-113: terms are DATA, money is external)
          ≠ TRUTH (an offer is a claim by its issuer, nothing more)

Offers are per-provider domain objects. The exchange surface discovers
OFFERS, never topology: providers retain domain-local topology and
routing authority (LOCK-104/LOCK-105); the exchange exposes only what
providers export for interoperability per frozen 1.1 section 5 —
capabilities, service boundaries, offers, commitments — as opaque,
provenance-carrying DATA. Cross-provider composition is an M006+
concern and is deliberately absent here.

Determinism discipline (LOCK-119): injected RFC 3339 UTC instants only
(no wall clock), content-derived ids over canonical JSON, sorted
iteration everywhere, no randomness, no UUIDs, no network, and secrets
are rejected at construction and deserialization time.
"""

from __future__ import annotations

from .errors import OfferError, OfferReason
from .model import (
    ADVERTISEMENT_STATUSES,
    BILLING_MODES,
    COMMITMENT_KINDS,
    OFFER_STATUSES,
    AdvertisementEntry,
    AdvertisementRef,
    CapabilityAdvertisement,
    OfferCommitment,
    OfferPricing,
    OfferRecord,
    ProviderDomain,
    ServiceBoundary,
    build_advertisement,
    build_offer,
    derive_advertisement_id,
    derive_offer_id,
    evaluate_advertisement_status,
    evaluate_offer_status,
)
from .serialization import (
    SerializationError,
    advertisement_from_bytes,
    advertisement_to_bytes,
    offer_from_bytes,
    offer_to_bytes,
)
from .exchange import (
    OfferExchange,
    WithdrawalRecord,
    resolve_offer_reference,
)
from .bridge import (
    accepted_offer_values,
    offer_reference,
    pricing_reference,
    service_property_references,
    verify_accepted_offers,
)

__all__ = [
    "ADVERTISEMENT_STATUSES",
    "BILLING_MODES",
    "COMMITMENT_KINDS",
    "OFFER_STATUSES",
    "AdvertisementEntry",
    "AdvertisementRef",
    "CapabilityAdvertisement",
    "OfferCommitment",
    "OfferError",
    "OfferExchange",
    "OfferPricing",
    "OfferReason",
    "OfferRecord",
    "ProviderDomain",
    "SerializationError",
    "ServiceBoundary",
    "WithdrawalRecord",
    "accepted_offer_values",
    "advertisement_from_bytes",
    "advertisement_to_bytes",
    "build_advertisement",
    "build_offer",
    "derive_advertisement_id",
    "derive_offer_id",
    "evaluate_advertisement_status",
    "evaluate_offer_status",
    "offer_from_bytes",
    "offer_reference",
    "offer_to_bytes",
    "pricing_reference",
    "resolve_offer_reference",
    "service_property_references",
    "verify_accepted_offers",
]
