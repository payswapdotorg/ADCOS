"""Typed error model for the ADCOS RoamLink vertical-proof
harness (M011, R7-CORE-001 child, DEC-0101).

Every failure carries a typed reason (fail closed; no
stringly-typed error taxonomy) and every reason is namespaced
``roamlink-`` so composed surfaces can never confuse a
vertical-harness reason with a contract reason, an offer
reason, a usage reason, a commercial reason, or a developer-API
reason.  Error detail is deterministic and never echoes
secret-shaped material (LOCK-119).
"""

from __future__ import annotations


class RoamLinkReason:
    """The frozen M011 vertical-harness reason vocabulary."""

    #: malformed input at any public boundary
    INVALID_INPUT = "roamlink-invalid-input"
    #: a value outside a frozen vocabulary (e.g. an unknown
    #: provider-change kind or observation state)
    VOCABULARY = "roamlink-vocabulary"
    #: a temporal value is malformed or an interval is impossible
    TEMPORAL_INVALID = "roamlink-temporal-invalid"
    #: secret-shaped material rejected at the boundary (LOCK-119)
    SECRET_REJECTED = "roamlink-secret-rejected"
    #: a cohort handle that is not opaque (subscriber-identity
    #: shaped material may never cross the application boundary;
    #: LOCK-120/LOCK-119)
    COHORT_NOT_OPAQUE = "roamlink-cohort-not-opaque"
    #: a request body carrying vertical application semantics
    #: (mobile/eSIM/UX tokens) that ADCOS must never host
    #: (LOCK-120)
    VERTICAL_SEMANTICS_REJECTED = "roamlink-vertical-semantics-rejected"
    #: a simulation seam used outside its declared simulation
    #: role (a seam may never be consulted as a delivered child
    #: authority)
    SEAM_MISUSED = "roamlink-seam-misused"
    #: a simulated realization that violates the contract's hard
    #: constraints (LOCK-108: replanning may never weaken them;
    #: the seam fails closed instead of binding the weakening)
    CONSTRAINT_VIOLATION = "roamlink-constraint-violation"
    #: an observation (execution status / assurance event) that
    #: is not attributable to the one contract through typed
    #: references
    ATTRIBUTION_INVALID = "roamlink-attribution-invalid"
    #: a flow step executed out of order or twice
    STEP_INVALID = "roamlink-step-invalid"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.VOCABULARY,
            cls.TEMPORAL_INVALID,
            cls.SECRET_REJECTED,
            cls.COHORT_NOT_OPAQUE,
            cls.VERTICAL_SEMANTICS_REJECTED,
            cls.SEAM_MISUSED,
            cls.CONSTRAINT_VIOLATION,
            cls.ATTRIBUTION_INVALID,
            cls.STEP_INVALID,
        )


class RoamLinkError(ValueError):
    """Raised when a RoamLink vertical-harness boundary is
    violated (fail closed).  ``code`` is a stable
    machine-readable reason from :class:`RoamLinkReason`; the
    string form is ``<code>: <detail>`` and never carries raw
    exception text or secret-shaped material."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


__all__ = ["RoamLinkError", "RoamLinkReason"]
