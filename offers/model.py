"""The M003 provider-domain offer model (Architecture 1.1 sections 2/5/6).

Value records (all immutable, all deterministic):

- **ProviderDomain** — a canonical provider-domain identity. Validated
  through the accepted identity grammar (``identity.node_id.parse_node_id``
  — never a duplicated grammar). A provider domain is an IDENTITY
  REFERENCE, never a trust claim and never a topology node: providers
  retain domain-local topology and routing authority (LOCK-104/LOCK-105).
- **AdvertisementEntry** — one capability advertisement entry: the
  capability id, the statement's schema version, the content digest of
  the canonical capability-statement bytes, and the classification the
  capabilities authority produced — all carried as DATA. The offers
  domain NEVER classifies capability ids (the WORK-002 capability
  registry owns classification; no second vocabulary authority).
- **CapabilityAdvertisement** — the provider-domain capability
  advertisement: which capability statements a provider is currently
  putting forward, over which validity window, under which provenance
  (LOCK-118: issuer + decision references, always).
- **OfferCommitment** — an EXPLICIT and BOUNDED commitment: a typed
  service commitment with scalar parameters, a commitment window that
  MUST lie inside the offer's validity interval (structural boundedness),
  and mandatory provenance (LOCK-118: every externally asserted
  commitment has issuer and provenance).
- **OfferPricing** — the commercial terms of the offer as typed DATA
  (integer minor units; frozen billing-mode vocabulary — the harvested
  W047 integer-money discipline). LOCK-113: these are terms, not
  payment authority and not payment movement; money stays external.
- **ServiceBoundary** — the provider's declared service boundary:
  jurisdiction plus OPAQUE geography references (e.g. bounded coverage
  cell ids). Geography is provider-declared DATA — never a global
  topology, never coordinates the model can resolve into positions.
- **AdvertisementRef** — a reference from an offer to the capability
  advertisement that grounds it (provenance required).
- **OfferRecord** — the provider offer: provider domain, the
  provider-assigned listing key (DATA), the listing's schema version,
  the grounding advertisements, the explicit bounded commitments, the
  pricing terms, the service boundaries, and the validity interval —
  with a content-derived, tamper-evident identity.

Identity discipline: ``offer_id`` / ``advertisement_id`` are the
canonical-JSON sha256 over the record's creation core. The identity is
stable across lifecycle evolution (withdrawal and supersession are
exchange-level facts, never record mutations — records are immutable).
A supplied id must equal the derived value: tamper evidence at
construction AND deserialization time.

The record set references the canonical ``contracts/`` domain (M002,
DEC-0102) for ``Provenance`` and ``ValidityInterval`` — the offers
domain NEVER re-implements or duplicates contract semantics (LOCK-101:
``contracts/`` is the sole canonical authority for contract semantics).

Determinism: injected RFC 3339 UTC instants only; no wall clock, no
randomness, no UUIDs, no network; sorted iteration everywhere; secrets
rejected at construction and deserialization time (LOCK-119).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from identity.node_id import NodeIdError, parse_node_id
from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from contracts import ContractError, Provenance, ValidityInterval

from .errors import OfferError, OfferReason

# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------

#: The frozen commitment vocabulary. A commitment kind names the service
#: dimension the provider commits to; the parameters carry the explicit
#: bounds (scalar values only — deterministic, no nested structures).
COMMITMENT_KINDS: Tuple[str, ...] = (
    "latency-bound-ms",
    "throughput-floor-kbps",
    "availability-floor-nine",
    "loss-bound-pct",
    "jitter-bound-ms",
    "capacity-floor-kbps",
)

#: The frozen billing-mode vocabulary (the harvested W047 commercial-terms
#: discipline; LOCK-113: terms as DATA, money movement external).
BILLING_MODES: Tuple[str, ...] = (
    "per-minute",
    "per-megabyte",
    "flat",
)

#: The frozen record-level status vocabulary evaluated at an injected
#: instant (pure function of record + instant; withdrawal and
#: supersession are exchange-level statuses on top of these).
OFFER_STATUSES: Tuple[str, ...] = (
    "advertised",
    "not-yet-valid",
    "expired",
)

#: The advertisement record-level status vocabulary.
ADVERTISEMENT_STATUSES: Tuple[str, ...] = (
    "advertised",
    "not-yet-valid",
    "expired",
)

_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_SCHEMA_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_OFFER_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")
_REF_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")

_SECRET_NAME_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$")

_ID_NAMESPACE = "adc-os-provider-offer"
_ADVERTISEMENT_NAMESPACE = "adc-os-capability-advertisement"


# ----------------------------------------------------------------------
# Internal helpers (the per-domain fail-closed discipline)
# ----------------------------------------------------------------------


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise OfferError(
            OfferReason.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_id(namespace: str, document: Mapping[str, Any], label: str) -> str:
    payload = dict(document)
    payload["namespace"] = namespace
    return "sha256:" + hashlib.sha256(_canonical_bytes(payload, label)).hexdigest()


def _require_str(value: object, label: str, *, pattern: Optional[re.Pattern] = None) -> str:
    if not isinstance(value, str) or not value:
        raise OfferError(
            OfferReason.INVALID_INPUT, "%s must be a non-empty string" % label
        )
    if pattern is not None and pattern.fullmatch(value) is None:
        raise OfferError(
            OfferReason.INVALID_INPUT, "%s has an invalid format: %r" % (label, value)
        )
    _reject_secret(value, label)
    return value


def _reject_secret(value: object, label: str) -> None:
    """LOCK-119 guard: secret-looking material never enters offer data."""
    if _SECRET_NAME_PATTERN.search(label):
        raise OfferError(
            OfferReason.SECRET_REJECTED,
            "%s looks like secret material; secrets never enter offer data" % label,
        )
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.match(value):
        raise OfferError(
            OfferReason.SECRET_REJECTED,
            "%s carries a secret-shaped value; secrets never enter offer data" % label,
        )


def _require_in(value: object, vocabulary: Sequence[str], label: str) -> str:
    if value not in vocabulary:
        raise OfferError(
            OfferReason.VOCABULARY,
            "%s must be one of %s (found %r)" % (label, ", ".join(vocabulary), value),
        )
    return str(value)


def _require_tuple(value: object, label: str, *, min_len: int = 0) -> Tuple[Any, ...]:
    if isinstance(value, tuple):
        items = value
    elif isinstance(value, list):
        items = tuple(value)
    else:
        raise OfferError(OfferReason.INVALID_INPUT, "%s must be a sequence" % label)
    if len(items) < min_len:
        raise OfferError(
            OfferReason.INVALID_INPUT, "%s requires at least %d entries" % (label, min_len)
        )
    return items


def _require_int(value: object, label: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise OfferError(OfferReason.INVALID_INPUT, "%s must be an integer" % label)
    if not minimum <= value <= maximum:
        raise OfferError(
            OfferReason.INVALID_INPUT,
            "%s must be within [%d, %d]" % (label, minimum, maximum),
        )
    return value


def _require_instant(value: object, label: str) -> str:
    try:
        parse_instant(value)
    except TemporalError as error:
        raise OfferError(
            OfferReason.TEMPORAL_INVALID, "%s is invalid: %s" % (label, error)
        ) from None
    return str(value)


def _validity_from_dict(data: object, label: str) -> ValidityInterval:
    """Parse a contracts.ValidityInterval at the offers boundary,
    wrapping the canonical domain's typed errors into offers-typed
    errors (exception isolation: a caller of the offers surface never
    sees contracts-domain error types)."""
    try:
        return ValidityInterval.from_dict(data)
    except ContractError as error:
        raise OfferError(
            OfferReason.TEMPORAL_INVALID, "%s is invalid: %s" % (label, error.detail)
        ) from None


def _provenance_from_dict(data: object, label: str) -> Provenance:
    """Parse a contracts.Provenance at the offers boundary (exception
    isolation: contracts-domain errors become offers-typed errors)."""
    try:
        return Provenance.from_dict(data)
    except ContractError as error:
        raise OfferError(
            OfferReason.INVALID_INPUT, "%s is invalid: %s" % (label, error.detail)
        ) from None


def _require_provider(value: object, label: str) -> str:
    """Provider identity is validated through the accepted identity
    grammar (identity.node_id.parse_node_id) — never a duplicated
    grammar; near-miss and malformed values fail closed."""
    if not isinstance(value, str) or not value:
        raise OfferError(
            OfferReason.INVALID_INPUT, "%s must be a canonical ADCOS NodeID" % label
        )
    try:
        parse_node_id(value)
    except NodeIdError as error:
        raise OfferError(
            OfferReason.INVALID_INPUT,
            "%s must be a canonical ADCOS NodeID "
            "(adcos:node:<profile_id>:<64 lowercase hex>): %s" % (label, error),
        ) from None
    return value


def _require_provenance(value: object, label: str) -> Provenance:
    """LOCK-118 guard: externally asserted material always carries
    issuer + provenance."""
    if not isinstance(value, Provenance):
        raise OfferError(
            OfferReason.PROVENANCE_REQUIRED,
            "%s requires a contracts.Provenance record (issuer + decision refs)",
        )
    return value


def _check_mapping_str_scalar(params: Mapping[str, Any], label: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key in sorted(params):
        if not isinstance(key, str) or not key:
            raise OfferError(
                OfferReason.INVALID_INPUT, "%s keys must be non-empty strings" % label
            )
        value = params[key]
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise OfferError(
                OfferReason.INVALID_INPUT,
                "%s[%r] must be a scalar (str/int/float)" % (label, key),
            )
        _reject_secret(value, "%s[%r]" % (label, key))
        result[key] = value
    return result


# ----------------------------------------------------------------------
# Provider domain (LOCK-104/LOCK-105: an identity reference, never a
# topology node, never a trust claim)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderDomain:
    """A canonical provider-domain identity (an identity reference).

    The NodeID grammar is validated through the accepted
    ``identity.node_id.parse_node_id`` — the offers domain never
    duplicates an identity grammar. A provider domain is NOT a trust
    claim, NOT an availability claim, and NOT a topology node: providers
    retain domain-local topology and routing authority."""

    node_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "node_id", _require_provider(self.node_id, "provider.node_id")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"node_id": self.node_id}

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ProviderDomain":
        if not isinstance(data, Mapping):
            raise OfferError(OfferReason.INVALID_INPUT, "provider must be a mapping")
        return ProviderDomain(node_id=data.get("node_id"))

    def __repr__(self) -> str:
        return "ProviderDomain(node_id=%r)" % (self.node_id[:32] + ("…" if len(self.node_id) > 32 else ""),)


# ----------------------------------------------------------------------
# Capability advertisement material (references the capabilities
# authority; never re-classifies, never duplicates its semantics)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AdvertisementEntry:
    """One capability advertisement entry (DATA from the capabilities
    authority).

    ``capability_id`` is the capability vocabulary id; the offers domain
    never classifies it (the capability registry owns classification —
    no second vocabulary authority). ``statement_digest`` is the sha256
    over the canonical capability-statement bytes (the
    ``capabilities/serialization`` machinery produces them).
    ``classification`` is the classification the capabilities authority
    produced, carried verbatim as DATA."""

    capability_id: str
    schema_version: str
    statement_digest: str
    classification: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "capability_id",
            _require_str(self.capability_id, "entry.capability_id"),
        )
        object.__setattr__(
            self,
            "schema_version",
            _require_str(
                self.schema_version, "entry.schema_version", pattern=_SCHEMA_VERSION_PATTERN
            ),
        )
        if not isinstance(self.statement_digest, str) or (
            _DIGEST_PATTERN.fullmatch(self.statement_digest) is None
        ):
            raise OfferError(
                OfferReason.INVALID_INPUT,
                "entry.statement_digest must be a content digest (sha256:<64 hex>)",
            )
        object.__setattr__(
            self,
            "classification",
            _require_str(self.classification, "entry.classification"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "schema_version": self.schema_version,
            "statement_digest": self.statement_digest,
            "classification": self.classification,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "AdvertisementEntry":
        if not isinstance(data, Mapping):
            raise OfferError(OfferReason.INVALID_INPUT, "entry must be a mapping")
        return AdvertisementEntry(
            capability_id=data.get("capability_id"),
            schema_version=data.get("schema_version"),
            statement_digest=data.get("statement_digest"),
            classification=data.get("classification"),
        )


@dataclass(frozen=True)
class CapabilityAdvertisement:
    """The provider-domain capability advertisement (LOCK-118).

    What a provider puts forward: the capability statements (as opaque
    typed entries with content digests), over which validity window,
    under which provenance. An advertisement is a CLAIM by its issuer —
    never truth, availability, authorization, or topology."""

    advertisement_id: str
    provider: str
    entries: Tuple[AdvertisementEntry, ...]
    validity: ValidityInterval
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider", _require_provider(self.provider, "advertisement.provider")
        )
        entries = _require_tuple(self.entries, "advertisement.entries", min_len=1)
        normalized = []
        for i, entry in enumerate(entries):
            if isinstance(entry, AdvertisementEntry):
                normalized.append(entry)
            elif isinstance(entry, Mapping):
                normalized.append(AdvertisementEntry.from_dict(entry))
            else:
                raise OfferError(
                    OfferReason.INVALID_INPUT,
                    "advertisement.entries[%d] must be an AdvertisementEntry" % i,
                )
        object.__setattr__(self, "entries", tuple(normalized))
        if not isinstance(self.validity, ValidityInterval):
            raise OfferError(
                OfferReason.INVALID_INPUT,
                "advertisement.validity must be a contracts.ValidityInterval",
            )
        object.__setattr__(
            self,
            "provenance",
            _require_provenance(self.provenance, "advertisement.provenance"),
        )
        # tamper evidence: the supplied id must equal the derived identity
        expected = _derive_advertisement_id_from_core(
            self.provider, self.entries, self.validity
        )
        if self.advertisement_id != expected:
            raise OfferError(
                OfferReason.ID_MISMATCH,
                "advertisement_id does not match the derived identity (tamper evidence)",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "advertisement_id": self.advertisement_id,
            "provider": self.provider,
            "entries": [e.to_dict() for e in self.entries],
            "validity": self.validity.to_dict(),
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "CapabilityAdvertisement":
        if not isinstance(data, Mapping):
            raise OfferError(OfferReason.INVALID_INPUT, "advertisement must be a mapping")
        return CapabilityAdvertisement(
            advertisement_id=data.get("advertisement_id"),
            provider=data.get("provider"),
            entries=tuple(
                AdvertisementEntry.from_dict(e) for e in data.get("entries") or ()
            ),
            validity=_validity_from_dict(data.get("validity"), "advertisement.validity"),
            provenance=_provenance_from_dict(
                data.get("provenance"), "advertisement.provenance"
            ),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "advertisement record")


def _derive_advertisement_id_from_core(
    provider: str,
    entries: Sequence[AdvertisementEntry],
    validity: ValidityInterval,
) -> str:
    document = {
        "provider": provider,
        "entries": [e.to_dict() for e in entries],
        "validity": validity.to_dict(),
    }
    return _derive_id(
        _ADVERTISEMENT_NAMESPACE, document, "advertisement id document"
    )


def derive_advertisement_id(advertisement: CapabilityAdvertisement) -> str:
    """Re-derive the identity of a constructed advertisement (tamper check)."""
    return _derive_advertisement_id_from_core(
        advertisement.provider, advertisement.entries, advertisement.validity
    )


def evaluate_advertisement_status(
    advertisement: CapabilityAdvertisement, instant: str
) -> str:
    """The record-level advertisement status at the injected instant
    (pure function of record + instant; no wall clock)."""
    _require_instant(instant, "evaluation.instant")
    if advertisement.validity.is_not_yet_valid(instant):
        return "not-yet-valid"
    if advertisement.validity.is_expired(instant):
        return "expired"
    return "advertised"


# ----------------------------------------------------------------------
# Offer material: commitments, pricing, service boundary
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class OfferCommitment:
    """An EXPLICIT and BOUNDED provider commitment (LOCK-118).

    ``kind`` names the committed service dimension; ``params`` carries
    the explicit scalar bounds; ``window`` is the commitment window
    which MUST lie inside the owning offer's validity interval
    (structural boundedness, enforced by ``OfferRecord`` construction);
    ``provenance`` is MANDATORY — every externally asserted commitment
    has issuer and provenance."""

    kind: str
    params: Mapping[str, Any]
    window: ValidityInterval
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "kind", _require_in(self.kind, COMMITMENT_KINDS, "commitment.kind")
        )
        params = self.params if isinstance(self.params, Mapping) else {}
        object.__setattr__(
            self, "params", _check_mapping_str_scalar(params, "commitment.params")
        )
        if not isinstance(self.window, ValidityInterval):
            raise OfferError(
                OfferReason.INVALID_INPUT,
                "commitment.window must be a contracts.ValidityInterval",
            )
        object.__setattr__(
            self,
            "provenance",
            _require_provenance(self.provenance, "commitment.provenance"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "params": dict(self.params),
            "window": self.window.to_dict(),
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "OfferCommitment":
        if not isinstance(data, Mapping):
            raise OfferError(OfferReason.INVALID_INPUT, "commitment must be a mapping")
        return OfferCommitment(
            kind=data.get("kind"),
            params=data.get("params") or {},
            window=_validity_from_dict(data.get("window"), "commitment.window"),
            provenance=_provenance_from_dict(data.get("provenance"), "commitment.provenance"),
        )


@dataclass(frozen=True)
class OfferPricing:
    """The commercial terms of an offer (typed DATA, LOCK-113).

    Integer minor units with an explicit decimal exponent and a frozen
    billing-mode vocabulary (the harvested W047 integer-money
    discipline: pure integer arithmetic, no floats, no money movement).
    These are TERMS — payment authority and money movement stay
    external; the offers domain executes nothing."""

    currency: str
    price_minor: int
    price_exponent: int
    billing_mode: str
    provenance: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.currency, str) or _CURRENCY_PATTERN.fullmatch(
            self.currency
        ) is None:
            raise OfferError(
                OfferReason.INVALID_INPUT,
                "pricing.currency must be a 3-letter uppercase currency code",
            )
        object.__setattr__(
            self,
            "price_minor",
            _require_int(self.price_minor, "pricing.price_minor", minimum=0, maximum=10**15),
        )
        object.__setattr__(
            self,
            "price_exponent",
            _require_int(self.price_exponent, "pricing.price_exponent", minimum=0, maximum=12),
        )
        object.__setattr__(
            self,
            "billing_mode",
            _require_in(self.billing_mode, BILLING_MODES, "pricing.billing_mode"),
        )
        object.__setattr__(
            self,
            "provenance",
            _require_provenance(self.provenance, "pricing.provenance"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "currency": self.currency,
            "price_minor": self.price_minor,
            "price_exponent": self.price_exponent,
            "billing_mode": self.billing_mode,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "OfferPricing":
        if not isinstance(data, Mapping):
            raise OfferError(OfferReason.INVALID_INPUT, "pricing must be a mapping")
        return OfferPricing(
            currency=data.get("currency"),
            price_minor=data.get("price_minor"),
            price_exponent=data.get("price_exponent"),
            billing_mode=data.get("billing_mode"),
            provenance=_provenance_from_dict(data.get("provenance"), "pricing.provenance"),
        )


@dataclass(frozen=True)
class ServiceBoundary:
    """The provider's declared service boundary.

    ``jurisdiction`` is the declared legal jurisdiction;
    ``geography_refs`` are OPAQUE references to provider-declared
    coverage material (e.g. bounded coverage cell ids produced by the
    proximity authority). Geography is provider-declared DATA: the
    offers domain never resolves it into positions, never aggregates it
    across providers, and never constructs a topology from it
    (LOCK-105)."""

    jurisdiction: str
    geography_refs: Tuple[str, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "jurisdiction",
            _require_str(self.jurisdiction, "boundary.jurisdiction"),
        )
        refs = _require_tuple(self.geography_refs, "boundary.geography_refs")
        normalized = tuple(
            _require_str(
                ref,
                "boundary.geography_refs[%d]" % i,
                pattern=_REF_VALUE_PATTERN,
            )
            for i, ref in enumerate(refs)
        )
        object.__setattr__(self, "geography_refs", normalized)
        object.__setattr__(
            self,
            "provenance",
            _require_provenance(self.provenance, "boundary.provenance"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jurisdiction": self.jurisdiction,
            "geography_refs": list(self.geography_refs),
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ServiceBoundary":
        if not isinstance(data, Mapping):
            raise OfferError(OfferReason.INVALID_INPUT, "boundary must be a mapping")
        return ServiceBoundary(
            jurisdiction=data.get("jurisdiction"),
            geography_refs=tuple(data.get("geography_refs") or ()),
            provenance=_provenance_from_dict(data.get("provenance"), "boundary.provenance"),
        )


@dataclass(frozen=True)
class AdvertisementRef:
    """A reference from an offer to the capability advertisement that
    grounds it (LOCK-118: provenance mandatory — the advertisement is
    externally asserted provider material)."""

    advertisement_id: str
    provenance: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.advertisement_id, str) or (
            _ID_PATTERN.fullmatch(self.advertisement_id) is None
        ):
            raise OfferError(
                OfferReason.INVALID_INPUT,
                "advertisement_ref.advertisement_id must be the content-derived "
                "identity (sha256:...)",
            )
        object.__setattr__(
            self,
            "provenance",
            _require_provenance(self.provenance, "advertisement_ref.provenance"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "advertisement_id": self.advertisement_id,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "AdvertisementRef":
        if not isinstance(data, Mapping):
            raise OfferError(OfferReason.INVALID_INPUT, "advertisement_ref must be a mapping")
        return AdvertisementRef(
            advertisement_id=data.get("advertisement_id"),
            provenance=_provenance_from_dict(
                data.get("provenance"), "advertisement_ref.provenance"
            ),
        )


# ----------------------------------------------------------------------
# The provider offer record
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class OfferRecord:
    """The provider offer (the M003 canonical advertisement of terms).

    Field set: the content-derived identity; the provider domain; the
    provider-assigned listing key (DATA — the provider's own id for the
    listing, never a NodeID and never trust); the listing's schema
    version (supersession ordering — the deterministic W047 index
    discipline); the grounding capability advertisements (at least
    one); the explicit bounded commitments (at least one); the pricing
    terms; the service boundaries (at least one); the validity
    interval; and the provenance (LOCK-118).

    Records are IMMUTABLE: withdrawal and supersession are exchange-
    level facts; the identity is stable across lifecycle evolution.
    Every externally asserted member (advertisements, commitments,
    pricing, boundaries, the offer itself) carries issuer + provenance.
    """

    offer_id: str
    provider: str
    provider_offer_key: str
    schema_version: int
    advertisements: Tuple[AdvertisementRef, ...]
    commitments: Tuple[OfferCommitment, ...]
    pricing: OfferPricing
    service_boundaries: Tuple[ServiceBoundary, ...]
    validity: ValidityInterval
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider", _require_provider(self.provider, "offer.provider")
        )
        object.__setattr__(
            self,
            "provider_offer_key",
            _require_str(
                self.provider_offer_key, "offer.provider_offer_key", pattern=_OFFER_KEY_PATTERN
            ),
        )
        object.__setattr__(
            self,
            "schema_version",
            _require_int(self.schema_version, "offer.schema_version", minimum=1, maximum=10**6),
        )
        advertisements = _require_tuple(
            self.advertisements, "offer.advertisements", min_len=1
        )
        normalized_ads = []
        for i, ref in enumerate(advertisements):
            if isinstance(ref, AdvertisementRef):
                normalized_ads.append(ref)
            elif isinstance(ref, Mapping):
                normalized_ads.append(AdvertisementRef.from_dict(ref))
            else:
                raise OfferError(
                    OfferReason.INVALID_INPUT,
                    "offer.advertisements[%d] must be an AdvertisementRef" % i,
                )
        object.__setattr__(self, "advertisements", tuple(normalized_ads))
        commitments = _require_tuple(self.commitments, "offer.commitments", min_len=1)
        normalized = []
        for i, commitment in enumerate(commitments):
            if isinstance(commitment, OfferCommitment):
                normalized.append(commitment)
            elif isinstance(commitment, Mapping):
                normalized.append(OfferCommitment.from_dict(commitment))
            else:
                raise OfferError(
                    OfferReason.INVALID_INPUT,
                    "offer.commitments[%d] must be an OfferCommitment" % i,
                )
        object.__setattr__(self, "commitments", tuple(normalized))
        if not isinstance(self.pricing, OfferPricing) and isinstance(
            self.pricing, Mapping
        ):
            object.__setattr__(self, "pricing", OfferPricing.from_dict(self.pricing))
        if not isinstance(self.pricing, OfferPricing):
            raise OfferError(
                OfferReason.INVALID_INPUT, "offer.pricing must be an OfferPricing record"
            )
        boundaries = _require_tuple(
            self.service_boundaries, "offer.service_boundaries", min_len=1
        )
        normalized_bounds = []
        for i, boundary in enumerate(boundaries):
            if isinstance(boundary, ServiceBoundary):
                normalized_bounds.append(boundary)
            elif isinstance(boundary, Mapping):
                normalized_bounds.append(ServiceBoundary.from_dict(boundary))
            else:
                raise OfferError(
                    OfferReason.INVALID_INPUT,
                    "offer.service_boundaries[%d] must be a ServiceBoundary" % i,
                )
        object.__setattr__(self, "service_boundaries", tuple(normalized_bounds))
        if not isinstance(self.validity, ValidityInterval):
            raise OfferError(
                OfferReason.INVALID_INPUT,
                "offer.validity must be a contracts.ValidityInterval",
            )
        # commitments are bounded: every commitment window lies inside the
        # offer's validity interval (structural boundedness)
        for i, commitment in enumerate(self.commitments):
            if parse_instant(commitment.window.not_before) < parse_instant(
                self.validity.not_before
            ) or parse_instant(commitment.window.not_after) > parse_instant(
                self.validity.not_after
            ):
                raise OfferError(
                    OfferReason.COMMITMENT_UNBOUNDED,
                    "commitments[%d] window [%s, %s] is outside the offer validity "
                    "[%s, %s] — commitments are explicit AND bounded"
                    % (
                        i,
                        commitment.window.not_before,
                        commitment.window.not_after,
                        self.validity.not_before,
                        self.validity.not_after,
                    ),
                )
        object.__setattr__(
            self,
            "provenance",
            _require_provenance(self.provenance, "offer.provenance"),
        )
        # tamper evidence: the supplied id must equal the derived identity
        expected = _derive_offer_id_from_core(
            self.provider,
            self.provider_offer_key,
            self.schema_version,
            self.advertisements,
            self.commitments,
            self.pricing,
            self.service_boundaries,
            self.validity,
        )
        if self.offer_id != expected:
            raise OfferError(
                OfferReason.ID_MISMATCH,
                "offer_id does not match the derived identity (tamper evidence)",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offer_id": self.offer_id,
            "provider": self.provider,
            "provider_offer_key": self.provider_offer_key,
            "schema_version": self.schema_version,
            "advertisements": [a.to_dict() for a in self.advertisements],
            "commitments": [c.to_dict() for c in self.commitments],
            "pricing": self.pricing.to_dict(),
            "service_boundaries": [b.to_dict() for b in self.service_boundaries],
            "validity": self.validity.to_dict(),
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "OfferRecord":
        if not isinstance(data, Mapping):
            raise OfferError(OfferReason.INVALID_INPUT, "offer must be a mapping")
        return OfferRecord(
            offer_id=data.get("offer_id"),
            provider=data.get("provider"),
            provider_offer_key=data.get("provider_offer_key"),
            schema_version=data.get("schema_version"),
            advertisements=tuple(
                AdvertisementRef.from_dict(a) for a in data.get("advertisements") or ()
            ),
            commitments=tuple(
                OfferCommitment.from_dict(c) for c in data.get("commitments") or ()
            ),
            pricing=OfferPricing.from_dict(data.get("pricing")),
            service_boundaries=tuple(
                ServiceBoundary.from_dict(b)
                for b in data.get("service_boundaries") or ()
            ),
            validity=_validity_from_dict(data.get("validity"), "offer.validity"),
            provenance=_provenance_from_dict(data.get("provenance"), "offer.provenance"),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "offer record")

    def commitments_fingerprint(self) -> str:
        """A digest over the commitment set (bounded-commitment evidence:
        consumers can prove the commitment set was not mutated by
        comparing fingerprints)."""
        document = [c.to_dict() for c in self.commitments]
        return "sha256:" + hashlib.sha256(
            _canonical_bytes({"commitments": document}, "commitment set")
        ).hexdigest()


def _derive_offer_id_from_core(
    provider: str,
    provider_offer_key: str,
    schema_version: int,
    advertisements: Sequence[AdvertisementRef],
    commitments: Sequence[OfferCommitment],
    pricing: OfferPricing,
    service_boundaries: Sequence[ServiceBoundary],
    validity: ValidityInterval,
) -> str:
    """Content-derived offer identity over the creation core.

    The id document covers the provider, listing key, schema version,
    grounding advertisements, commitments, pricing, service boundaries
    and validity — the fields that make the offer THIS offer. The
    identity is stable across lifecycle evolution (withdrawal and
    supersession are exchange-level facts; records are immutable)."""
    document = {
        "provider": provider,
        "provider_offer_key": provider_offer_key,
        "schema_version": schema_version,
        "advertisements": [a.to_dict() for a in advertisements],
        "commitments": [c.to_dict() for c in commitments],
        "pricing": pricing.to_dict(),
        "service_boundaries": [b.to_dict() for b in service_boundaries],
        "validity": validity.to_dict(),
    }
    return _derive_id(_ID_NAMESPACE, document, "offer id document")


def derive_offer_id(offer: OfferRecord) -> str:
    """Re-derive the identity of a constructed offer (tamper check)."""
    return _derive_offer_id_from_core(
        offer.provider,
        offer.provider_offer_key,
        offer.schema_version,
        offer.advertisements,
        offer.commitments,
        offer.pricing,
        offer.service_boundaries,
        offer.validity,
    )


def evaluate_offer_status(offer: OfferRecord, instant: str) -> str:
    """The record-level offer status at the injected instant (pure
    function of record + instant; no wall clock). Exchange-level
    statuses (``withdrawn`` / ``superseded``) are evaluated by the
    exchange on top of this."""
    _require_instant(instant, "evaluation.instant")
    if offer.validity.is_not_yet_valid(instant):
        return "not-yet-valid"
    if offer.validity.is_expired(instant):
        return "expired"
    return "advertised"


# ----------------------------------------------------------------------
# Builders (content-derived identities computed at construction)
# ----------------------------------------------------------------------


def build_advertisement(
    *,
    provider: str,
    entries: Sequence[AdvertisementEntry],
    validity: ValidityInterval,
    provenance: Provenance,
) -> CapabilityAdvertisement:
    """Build a capability advertisement with its content-derived identity."""
    advertisement_id = _derive_advertisement_id_from_core(provider, entries, validity)
    return CapabilityAdvertisement(
        advertisement_id=advertisement_id,
        provider=provider,
        entries=tuple(entries),
        validity=validity,
        provenance=provenance,
    )


def build_offer(
    *,
    provider: str,
    provider_offer_key: str,
    schema_version: int,
    advertisements: Sequence[AdvertisementRef],
    commitments: Sequence[OfferCommitment],
    pricing: OfferPricing,
    service_boundaries: Sequence[ServiceBoundary],
    validity: ValidityInterval,
    provenance: Provenance,
) -> OfferRecord:
    """Build an offer with its content-derived identity."""
    offer_id = _derive_offer_id_from_core(
        provider,
        provider_offer_key,
        schema_version,
        advertisements,
        commitments,
        pricing,
        service_boundaries,
        validity,
    )
    return OfferRecord(
        offer_id=offer_id,
        provider=provider,
        provider_offer_key=provider_offer_key,
        schema_version=schema_version,
        advertisements=tuple(advertisements),
        commitments=tuple(commitments),
        pricing=pricing,
        service_boundaries=tuple(service_boundaries),
        validity=validity,
        provenance=provenance,
    )
