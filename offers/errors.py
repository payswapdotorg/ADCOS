"""Typed error model for the ADCOS offers package (M003).

Every failure carries a typed reason (fail closed; no stringly-typed
error taxonomy) and every reason is namespaced ``offer-`` so composed
surfaces can never confuse an offer-exchange reason with a contract
reason, a capability reason, or a marketplace reason. Error detail is
deterministic and never echoes secret-shaped material (LOCK-119).
"""

from __future__ import annotations


class OfferReason:
    """The frozen M003 offer-exchange reason vocabulary."""

    #: malformed input at any public boundary
    INVALID_INPUT = "offer-invalid-input"
    #: a temporal value is malformed or an interval is impossible
    TEMPORAL_INVALID = "offer-temporal-invalid"
    #: a supplied content-derived id does not match the derived identity
    #: (tamper evidence)
    ID_MISMATCH = "offer-id-mismatch"
    #: a value outside a frozen vocabulary
    VOCABULARY = "offer-vocabulary"
    #: secret-shaped material rejected at the boundary (LOCK-119)
    SECRET_REJECTED = "offer-secret-rejected"
    #: externally asserted material without issuer + provenance (LOCK-118)
    PROVENANCE_REQUIRED = "offer-provenance-required"
    #: a commitment window outside the offer validity interval
    #: (commitments are explicit AND bounded)
    COMMITMENT_UNBOUNDED = "offer-commitment-unbounded"
    #: a provider value inconsistent with the record's provider domain
    PROVIDER_MISMATCH = "offer-provider-mismatch"
    #: reading an offer key the exchange does not hold
    OFFER_UNKNOWN = "offer-offer-unknown"
    #: registering a conflicting record for an existing key
    OFFER_DUPLICATE = "offer-offer-duplicate"
    #: an offer is not currently usable (withdrawn or expired) at the
    #: injected evaluation instant
    OFFER_NOT_USABLE = "offer-offer-not-usable"
    #: an advertisement is not currently usable (withdrawn or expired)
    ADVERTISEMENT_NOT_USABLE = "offer-advertisement-not-usable"
    #: an opaque reference of the wrong kind presented at the boundary
    #: (LOCK-117 discipline: the offers surface only resolves its own
    #: reference kind)
    REFERENCE_KIND = "offer-reference-kind"


class OfferError(ValueError):
    """Raised when an offers record or exchange operation violates its
    contract (fail closed). ``code`` is a stable machine-readable
    reason from :class:`OfferReason`."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail
