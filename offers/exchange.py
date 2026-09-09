"""The provider-domain offer exchange (M003, Architecture 1.1 section 5).

``OfferExchange`` is the deterministic offer/capability exchange
surface: providers publish capability advertisements and offers, and
consumers query them. It is the harvested-and-refactored successor of
the W047 listing index discipline:

- the catalog is built functionally (same input set -> byte-identical
  listing, digests included): registrations are idempotent by content,
  identical (provider, listing key, version) re-registrations are
  no-ops, and a CONFLICTING same-version registration fails closed
  (``offer-duplicate``) — listings are immutable DATA;
- supersession is DETERMINISTIC: for one (provider, listing key) the
  LIVE listing is the HIGHEST registered schema version; superseded
  versions remain queryable for audit (never deleted, never mutated);
- withdrawal is an explicit, provider-scoped act recorded with its
  instant; withdrawn listings never present as usable at or after the
  withdrawal instant (fail closed at resolution time, never a silent
  disappearance — the record stays queryable for audit/provenance).

LOCK-105 (no global topology) is structural here:

- the exchange holds ONLY what providers exported per frozen 1.1
  section 5 — capability advertisements, offers, commitments, terms —
  as opaque, provenance-carrying DATA;
- every query is a FILTER within the catalog (optionally scoped to one
  provider domain — the provider-local view); NO query composes,
  joins, or aggregates material ACROSS provider domains (cross-provider
  composition is an M006+ execution-plan concern, deliberately absent);
- there is no node/link/path/graph surface: no method accepts or
  returns topology, and the record set cannot represent it;
- a provider's view is provider-local: ``offers(provider=...)`` returns
  exactly that provider's exports, never an inference about any other
  provider's infrastructure.

Determinism: injected instants only (no wall clock); sorted iteration
everywhere (by (provider, key), by id); content-derived identities;
registration order never leaks into any listing (PYTHONHASHSEED-safe).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from contracts import OpaqueReference

from .errors import OfferError, OfferReason
from .model import (
    CapabilityAdvertisement,
    OfferRecord,
    evaluate_advertisement_status,
    evaluate_offer_status,
)


@dataclass(frozen=True)
class WithdrawalRecord:
    """An explicit provider withdrawal of one listing key (audit trail:
    the withdrawn record stays queryable; withdrawal never deletes)."""

    provider: str
    provider_offer_key: str
    withdrawn_at: str
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider:
            raise OfferError(
                OfferReason.INVALID_INPUT, "withdrawal.provider must be a non-empty string"
            )
        if not isinstance(self.provider_offer_key, str) or not self.provider_offer_key:
            raise OfferError(
                OfferReason.INVALID_INPUT,
                "withdrawal.provider_offer_key must be a non-empty string",
            )
        try:
            parse_instant(self.withdrawn_at)
        except TemporalError as error:
            raise OfferError(
                OfferReason.TEMPORAL_INVALID, "withdrawal.withdrawn_at is invalid: %s" % error
            ) from None
        if not isinstance(self.reason, str) or not self.reason:
            raise OfferError(
                OfferReason.INVALID_INPUT, "withdrawal.reason must be a non-empty string"
            )


class OfferExchange:
    """The deterministic provider-domain offer exchange.

    Registration surface (pure functions of the input records):

    - ``register_advertisement``: idempotent by content-derived id;
      a DIFFERENT advertisement carrying an already-registered id fails
      closed (tamper evidence — ids are content-derived, so this is a
      collision, not a legitimate re-registration).
    - ``register_offer``: the W047 index discipline (idempotent /
      conflicting / supersession, per (provider, listing key) with
      schema-version ordering). The offer's grounding advertisements
      must already be registered (an offer is grounded in capability
      advertisements, never free-floating).
    - ``withdraw_offer``: an explicit provider-scoped withdrawal with
      an injected instant; the provider must own the listing key.

    Query surface (deterministic, sorted, LOCK-105 discipline):

    - ``advertisements`` / ``advertisement``: registered capability
      advertisements (audit-inclusive).
    - ``offers``: the LIVE listings (highest version per key), sorted
      by (provider, listing key), optionally scoped to one provider.
    - ``offer`` / ``resolve``: fail-closed reads by id; ``resolve``
      additionally requires the offer to be USABLE at the injected
      evaluation instant (advertised, within validity, not withdrawn,
      live version).
    - ``offer_status``: the full status vocabulary at an instant.
    """

    def __init__(self) -> None:
        self._advertisements: Dict[str, CapabilityAdvertisement] = {}
        self._by_key: Dict[Tuple[str, str], List[OfferRecord]] = {}
        self._by_id: Dict[str, Tuple[str, str]] = {}
        self._withdrawals: Dict[Tuple[str, str], WithdrawalRecord] = {}

    # ------------------------------------------------------------------
    # Registration (deterministic, fail-closed, idempotent)
    # ------------------------------------------------------------------

    def register_advertisement(
        self, advertisement: CapabilityAdvertisement
    ) -> None:
        if not isinstance(advertisement, CapabilityAdvertisement):
            raise OfferError(
                OfferReason.INVALID_INPUT,
                "register_advertisement requires a CapabilityAdvertisement record",
            )
        existing = self._advertisements.get(advertisement.advertisement_id)
        if existing is not None:
            if existing.canonical_bytes() != advertisement.canonical_bytes():
                raise OfferError(
                    OfferReason.OFFER_DUPLICATE,
                    "advertisement id %s registered with conflicting content — "
                    "ids are content-derived; this is a tamper collision"
                    % advertisement.advertisement_id[:24],
                )
            return  # identical re-registration: idempotent
        self._advertisements[advertisement.advertisement_id] = advertisement

    def register_offer(self, offer: OfferRecord) -> None:
        if not isinstance(offer, OfferRecord):
            raise OfferError(
                OfferReason.INVALID_INPUT,
                "register_offer requires an OfferRecord record",
            )
        # an offer is grounded in registered capability advertisements
        for i, ref in enumerate(offer.advertisements):
            if ref.advertisement_id not in self._advertisements:
                raise OfferError(
                    OfferReason.OFFER_UNKNOWN,
                    "offer.advertisements[%d] references an unregistered "
                    "capability advertisement — offers are grounded in "
                    "registered advertisements" % i,
                )
            grounding = self._advertisements[ref.advertisement_id]
            if grounding.provider != offer.provider:
                raise OfferError(
                    OfferReason.PROVIDER_MISMATCH,
                    "offer.advertisements[%d] grounds in a different provider's "
                    "advertisement (LOCK-104: provider domains are sovereign; "
                    "an offer is grounded by its OWN provider's advertisements)" % i,
                )
        key = (offer.provider, offer.provider_offer_key)
        history = self._by_key.setdefault(key, [])
        for existing in history:
            if existing.schema_version == offer.schema_version:
                if existing.offer_id == offer.offer_id:
                    return  # identical re-registration: idempotent
                raise OfferError(
                    OfferReason.OFFER_DUPLICATE,
                    "listing %s/%s version %d registered with conflicting content"
                    % (offer.provider[:24], offer.provider_offer_key, offer.schema_version),
                )
        self._by_id[offer.offer_id] = key
        history.append(offer)
        # deterministic supersession: keep the history sorted by version
        history.sort(key=lambda record: record.schema_version)

    def withdraw_offer(
        self, *, provider: str, provider_offer_key: str, withdrawn_at: str, reason: str
    ) -> WithdrawalRecord:
        """Record an explicit withdrawal (the provider's own act).

        Withdrawal is provider-scoped: only the listing's own provider
        can withdraw it. The withdrawn listing stays queryable for
        audit; it never presents as usable at or after the withdrawal
        instant."""
        key = (provider, provider_offer_key)
        if key not in self._by_key:
            raise OfferError(
                OfferReason.OFFER_UNKNOWN,
                "listing %s/%s is not registered" % (provider[:24], provider_offer_key),
            )
        withdrawal = WithdrawalRecord(
            provider=provider,
            provider_offer_key=provider_offer_key,
            withdrawn_at=withdrawn_at,
            reason=reason,
        )
        self._withdrawals[key] = withdrawal
        return withdrawal

    # ------------------------------------------------------------------
    # Reads (deterministic, sorted; LOCK-105: filters, never joins)
    # ------------------------------------------------------------------

    def advertisements(self) -> Tuple[CapabilityAdvertisement, ...]:
        """All registered capability advertisements, sorted by id."""
        return tuple(
            self._advertisements[advertisement_id]
            for advertisement_id in sorted(self._advertisements)
        )

    def advertisement(self, advertisement_id: str) -> CapabilityAdvertisement:
        advertisement = self._advertisements.get(advertisement_id)
        if advertisement is None:
            raise OfferError(
                OfferReason.OFFER_UNKNOWN,
                "advertisement %s is not registered" % advertisement_id[:24],
            )
        return advertisement

    def offers(
        self, *, provider: Optional[str] = None
    ) -> Tuple[OfferRecord, ...]:
        """The LIVE listings (highest version per key), sorted by
        (provider, listing key).

        ``provider`` scopes the query to one provider domain — the
        provider-local view. The listing is a FILTER over registered
        provider exports: it never composes material across providers
        and never represents or implies a network topology."""
        keys = (
            key for key in self._by_key if provider is None or key[0] == provider
        )
        return tuple(self._by_key[key][-1] for key in sorted(keys))

    def all_registered_offers(
        self, *, provider: Optional[str] = None
    ) -> Tuple[OfferRecord, ...]:
        """Every registered version of every listing key (audit view),
        sorted by (provider, listing key, schema version)."""
        result: List[OfferRecord] = []
        for key in sorted(self._by_key):
            if provider is not None and key[0] != provider:
                continue
            result.extend(self._by_key[key])
        return tuple(result)

    def offer(self, offer_id: str) -> OfferRecord:
        """Read one registered record by id (audit-inclusive: superseded
        and withdrawn records resolve here). Fail-closed when unknown."""
        key = self._by_id.get(offer_id)
        if key is None:
            raise OfferError(
                OfferReason.OFFER_UNKNOWN,
                "offer %s is not registered" % offer_id[:24],
            )
        for record in self._by_key[key]:
            if record.offer_id == offer_id:
                return record
        raise OfferError(
            OfferReason.OFFER_UNKNOWN,
            "offer %s is not registered" % offer_id[:24],
        )

    def offer_status(self, offer_id: str, *, at_instant: str) -> str:
        """The exchange-level status vocabulary at the injected instant:

        ``advertised`` / ``not-yet-valid`` / ``expired`` (record-level),
        plus ``withdrawn`` (an explicit withdrawal covers the instant)
        and ``superseded`` (a higher version is live for the key)."""
        record = self.offer(offer_id)
        key = (record.provider, record.provider_offer_key)
        withdrawal = self._withdrawals.get(key)
        if withdrawal is not None:
            # withdrawal is effective from its recorded instant onward,
            # clamped to the offer's own window opening (a withdrawal can
            # never apply before the offer exists); checked before expiry
            # — withdrawal is an explicit act, expiry is time-based
            effective_from = max(
                parse_instant(withdrawal.withdrawn_at),
                parse_instant(record.validity.not_before),
            )
            if parse_instant(at_instant) >= effective_from:
                return "withdrawn"
        if self._by_key[key][-1].schema_version > record.schema_version:
            return "superseded"
        return evaluate_offer_status(record, at_instant)

    def advertisement_status(self, advertisement_id: str, *, at_instant: str) -> str:
        """The advertisement status at the injected instant."""
        return evaluate_advertisement_status(
            self.advertisement(advertisement_id), at_instant
        )

    def active_advertisements(
        self, *, at_instant: str, provider: Optional[str] = None
    ) -> Tuple[CapabilityAdvertisement, ...]:
        """Advertisements that are usable at the injected instant
        (record-level ``advertised`` status), sorted by id, optionally
        scoped to one provider."""
        return tuple(
            advertisement
            for advertisement in self.advertisements()
            if (provider is None or advertisement.provider == provider)
            and evaluate_advertisement_status(advertisement, at_instant) == "advertised"
        )

    def active_offers(
        self, *, at_instant: str, provider: Optional[str] = None
    ) -> Tuple[OfferRecord, ...]:
        """The live listings usable at the injected instant (advertised,
        within validity, not withdrawn, not superseded), sorted by
        (provider, listing key). A filter — never a cross-provider
        composition, never a topology."""
        result: List[OfferRecord] = []
        for record in self.offers(provider=provider):
            if self.offer_status(record.offer_id, at_instant=at_instant) == "advertised":
                result.append(record)
        return tuple(result)

    def resolve(
        self, reference: OpaqueReference, *, at_instant: str
    ) -> OfferRecord:
        """Resolve a contract-shaped offer reference to the LIVE,
        USABLE offer record at the injected instant.

        Fail-closed on: the wrong reference kind (LOCK-117 discipline —
        the offers surface resolves exactly its own reference kind),
        unknown ids, and not-currently-usable offers (withdrawn /
        expired / not-yet-valid / superseded). The record stays
        available through ``offer`` for audit — resolution failure is
        an evaluation verdict, never a catalog mutation."""
        if not isinstance(reference, OpaqueReference):
            raise OfferError(
                OfferReason.INVALID_INPUT,
                "resolve requires a contracts.OpaqueReference",
            )
        if reference.ref_kind != "offer":
            raise OfferError(
                OfferReason.REFERENCE_KIND,
                "resolve accepts exactly the offer reference kind (found %s)"
                % reference.ref_kind,
            )
        record = self.offer(reference.value)
        status = self.offer_status(record.offer_id, at_instant=at_instant)
        if status != "advertised":
            raise OfferError(
                OfferReason.OFFER_NOT_USABLE,
                "offer %s is %s at the evaluation instant — offers resolve "
                "only when usable" % (record.offer_id[:24], status),
            )
        return record

    def withdrawal(self, provider: str, provider_offer_key: str) -> Optional[WithdrawalRecord]:
        """The withdrawal record for a listing key, if any (audit)."""
        return self._withdrawals.get((provider, provider_offer_key))

    def catalog_digest(self) -> str:
        """A digest over the full catalog state (advertisements, all
        registered versions, withdrawals) — deterministic: identical
        registration sequences produce identical digests, and the
        digest is order-independent by construction (sorted inputs)."""
        document = {
            "advertisements": [
                a.to_dict() for a in self.advertisements()
            ],
            "offers": [o.to_dict() for o in self.all_registered_offers()],
            "withdrawals": [
                {
                    "provider": w.provider,
                    "provider_offer_key": w.provider_offer_key,
                    "withdrawn_at": w.withdrawn_at,
                    "reason": w.reason,
                }
                for w in (
                    self._withdrawals[key] for key in sorted(self._withdrawals)
                )
            ],
        }
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(document)
        ).hexdigest()


def resolve_offer_reference(
    exchange: OfferExchange, reference: OpaqueReference, *, at_instant: str
) -> OfferRecord:
    """Resolve a contract-shaped offer reference against the exchange
    (the free-function form of ``OfferExchange.resolve``)."""
    return exchange.resolve(reference, at_instant=at_instant)
