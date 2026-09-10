"""ADCOS contract-reference eligibility evaluation (M004 — Eligibility
and Policy; R7-CORE-001 child, DEC-0101; frozen 1.1 section 2: the
``Eligibility + Policy`` stage of the closed loop, AROUND the canonical
contract).

Migration-matrix classification (spec/migration/classification-matrix.md):
"Policy: RETAIN + REFACTOR -> Eligibility + contract constraints" — the
eligibility half.  This module is the REFACTOR onto the 1.1 authority
model of the eligibility disciplines HARVESTED from the legacy W045
reservoir: fail-closed explicit rule DATA; the decision-DATA denial
family separated from the raised typed-error family; fixed check order
with deterministic, deduplicated, order-preserving denial reasons;
versioned rules whose updates change NEW evaluation behavior without
rewriting historical outcome records; reference-only boundaries.

Consumption discipline (LOCK-101, the harvested W045 snapshot seam —
the strongest by-reference form): this module NEVER imports the
canonical domains.  The evaluation consumes caller-composed pure-DATA
snapshots built from the canonical public surfaces — ``contracts/``
(M002, DEC-0102) for the contract reference facts and ``offers/``
(M003, DEC-0103) for the resolved offer facts.  The module never
queries, instantiates, or mutates any canonical authority, and never
re-implements contract or offer semantics: the contract lifecycle
state, the terminal classification, the validity window and offer
usability are READ as opaque DATA by the composing caller.  The
canonical vocabularies stay owned by their canonical authorities.

Landing note (disclosed in docs/M004-evidence.md): the matrix routes
Policy to the single target authority "Eligibility + contract
constraints", and the module lands in ``eligibility/`` because the
M009-accepted payment battery (``tools/payment_selftest.py`` case_38,
DEC-0109 — not M004 material) freezes the whole ``policy`` family
against any delta, while this family's frozen import discipline
(stdlib + ``protocol.canonicalization`` + ``agent.clock`` only) is
satisfied by the snapshot design.

The central boundary (exercised case-by-case in the M004 battery):

    CONTRACT-REFERENCE ELIGIBILITY
      = deterministic evaluation of explicit eligibility rules
        against composed offer/contract reference FACTS at an
        injected instant

    ELIGIBILITY  !=  CONTRACT AUTHORITY (LOCK-101: the canonical
        ConnectivityContract and its store stay the sole authority;
        this module never sees a contract object — only
        caller-composed reference facts)
    ELIGIBILITY  !=  OFFER SEMANTICS (LOCK-101: offer usability/
        validity/withdrawal are the M003 exchange's own; they arrive
        as the ``usable`` DATA flag on composed offer facts)
    ELIGIBILITY  !=  POLICY PERMISSION (the constraint boundary in
        ``contract_constraints.py`` answers whether an action is
        permitted; eligibility answers whether references are
        admissible — neither derives the other)
    ELIGIBILITY  !=  PAYMENT AUTHORITY (LOCK-113: no payment surface;
        commercial material rides as opaque references)
    ELIGIBILITY  !=  PROVIDER SDK SURFACE (LOCK-110: providers appear
        only as opaque typed reference values; evaluation is
        technology-neutral)

Denial reasons are decision DATA (never raised): an evaluation that
denies is a normal outcome.  Raised typed errors are reserved for
input-integrity violations at the boundary (malformed facts, bad
rulesets, malformed instants) — the harvested W045 separation.

Determinism discipline (LOCK-119): injected RFC 3339 UTC instants only
(no wall clock); canonical JSON over ``protocol.canonicalization``;
fixed check order; sorted, deduplicated, order-preserving reason
tuples; content-derived digests; no randomness, no network;
secret-shaped labels and values rejected at construction time.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from agent.clock import AgentError, parse_utc

from .contract_constraints import OfferReferenceFacts, ValidityWindow

# ----------------------------------------------------------------------
# Typed error model (namespaced ``contract-eligibility-*``; fail closed)
# ----------------------------------------------------------------------


class ContractEligibilityReason:
    """The frozen M004 contract-eligibility reason vocabulary.  The
    raised family (integrity violations) and the decision-DATA denial
    family are strictly separated — the harvested W045 discipline."""

    # -- raised family (input integrity; NEVER a denial outcome) ------
    INVALID_INPUT = "contract-eligibility-invalid-input"
    TEMPORAL_INVALID = "contract-eligibility-temporal-invalid"
    VOCABULARY = "contract-eligibility-vocabulary"
    SECRET_REJECTED = "contract-eligibility-secret-rejected"
    PROVENANCE_REQUIRED = "contract-eligibility-provenance-required"

    # -- decision-DATA denial family (normal outcomes; never raised) --
    PROVIDER_NOT_PERMITTED = "provider-not-permitted"
    JURISDICTION_NOT_COVERED = "jurisdiction-not-covered"
    OFFER_NOT_USABLE = "offer-not-usable"
    CONTRACT_NOT_LIVE = "contract-not-live"
    CONTRACT_TERMINAL = "contract-terminal"
    NO_ACCEPTED_OFFERS = "no-accepted-offers"

    @classmethod
    def denial_values(cls) -> Tuple[str, ...]:
        return (
            cls.PROVIDER_NOT_PERMITTED,
            cls.JURISDICTION_NOT_COVERED,
            cls.OFFER_NOT_USABLE,
            cls.CONTRACT_NOT_LIVE,
            cls.CONTRACT_TERMINAL,
            cls.NO_ACCEPTED_OFFERS,
        )


class ContractEligibilityError(ValueError):
    """Raised when an eligibility input violates its boundary contract
    (fail closed).  ``code`` is a stable machine-readable reason from
    :class:`ContractEligibilityReason` — always the raised family,
    never a denial code (denials are DATA)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


_SECRET_NAME_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$")
_REF_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")
_RULESET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_JURISDICTION_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _reject_secret(value: object, label: str) -> None:
    """LOCK-119 guard: secret-shaped material never enters eligibility
    data."""
    if _SECRET_NAME_PATTERN.search(label):
        raise ContractEligibilityError(
            ContractEligibilityReason.SECRET_REJECTED,
            "%s looks like secret material; secrets never enter "
            "contract-eligibility data" % label,
        )
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.match(value):
        raise ContractEligibilityError(
            ContractEligibilityReason.SECRET_REJECTED,
            "%s carries a secret-shaped value; secrets never enter "
            "contract-eligibility data" % label,
        )


def _require_str(value: object, label: str, *, pattern: Optional[re.Pattern] = None) -> str:
    if not isinstance(value, str) or not value:
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT, "%s must be a non-empty string" % label
        )
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT, "%s has an invalid format: %r" % (label, value)
        )
    _reject_secret(value, label)
    return value


def _require_int(value: object, label: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT, "%s must be an integer" % label
        )
    if not minimum <= value <= maximum:
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "%s must be within [%d, %d]" % (label, minimum, maximum),
        )
    return value


def _require_tuple(value: object, label: str) -> Tuple[Any, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    raise ContractEligibilityError(
        ContractEligibilityReason.INVALID_INPUT, "%s must be a sequence" % label
    )


def _parse_instant(value: object, label: str):
    """Parse an RFC 3339 UTC instant through the injected clock seam
    (agent.clock — the WORK-033 discipline; no wall clock anywhere)."""
    if not isinstance(value, str) or not value:
        raise ContractEligibilityError(
            ContractEligibilityReason.TEMPORAL_INVALID,
            "%s must be a non-empty RFC 3339 UTC instant string" % label,
        )
    try:
        return parse_utc(value)
    except (AgentError, ValueError) as error:
        raise ContractEligibilityError(
            ContractEligibilityReason.TEMPORAL_INVALID, "%s is invalid: %s" % (label, error)
        ) from None


def _require_instant(value: object, label: str) -> str:
    _parse_instant(value, label)
    return str(value)


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_digest(document: Mapping[str, Any], label: str) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(document, label)).hexdigest()


def _dedupe(reasons: Sequence[str]) -> Tuple[str, ...]:
    """Deterministic deduplication preserving first-occurrence order (the
    harvested W045 discipline)."""
    seen = set()
    ordered: List[str] = []
    for code in reasons:
        if code not in seen:
            seen.add(code)
            ordered.append(code)
    return tuple(ordered)


# ----------------------------------------------------------------------
# The eligibility ruleset (explicit, versioned, issuer-carrying DATA)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ContractEligibilityRuleset:
    """The explicit eligibility rule DATA for contract-reference
    evaluation.

    Field set: the ruleset identity and version (rule updates change
    NEW evaluation behavior without rewriting historical outcome
    records — the harvested W045 versioning discipline); the MANDATORY
    issuer and decision references (LOCK-118: an anonymous ruleset is
    never evaluable); the ruleset's own validity window (evaluated at
    the INJECTED instant); the permitted provider domains (an explicit
    allow-list — a provider outside the list is not eligible; LOCK-110:
    opaque reference values, never SDK types); and the permitted
    jurisdictions (the jurisdictions in which connectivity may be
    acquired — an offer whose service boundaries cover none of them is
    not eligible).

    Both allow-lists are explicit by construction: an empty permitted
    set denies everything (fail closed), never silently permits."""

    ruleset_id: str
    version: int
    issuer: str
    permitted_providers: Tuple[str, ...]
    permitted_jurisdictions: Tuple[str, ...]
    valid_from: str = ""
    valid_until: str = ""
    decision_refs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "ruleset_id",
            _require_str(
                self.ruleset_id, "ruleset.ruleset_id", pattern=_RULESET_ID_PATTERN
            ),
        )
        object.__setattr__(
            self,
            "version",
            _require_int(self.version, "ruleset.version", minimum=1, maximum=10**6),
        )
        object.__setattr__(
            self, "issuer", _require_str(self.issuer, "ruleset.issuer")
        )
        providers = _require_tuple(self.permitted_providers, "ruleset.permitted_providers")
        object.__setattr__(
            self,
            "permitted_providers",
            tuple(
                _require_str(
                    value,
                    "ruleset.permitted_providers[%d]" % i,
                    pattern=_REF_VALUE_PATTERN,
                )
                for i, value in enumerate(providers)
            ),
        )
        jurisdictions = _require_tuple(
            self.permitted_jurisdictions, "ruleset.permitted_jurisdictions"
        )
        object.__setattr__(
            self,
            "permitted_jurisdictions",
            tuple(
                _require_str(
                    value,
                    "ruleset.permitted_jurisdictions[%d]" % i,
                    pattern=_JURISDICTION_PATTERN,
                )
                for i, value in enumerate(jurisdictions)
            ),
        )
        if self.valid_from:
            object.__setattr__(
                self, "valid_from", _require_instant(self.valid_from, "ruleset.valid_from")
            )
        if self.valid_until:
            object.__setattr__(
                self, "valid_until", _require_instant(self.valid_until, "ruleset.valid_until")
            )
        if self.valid_from and self.valid_until:
            if _parse_instant(self.valid_from, "ruleset.valid_from") > _parse_instant(
                self.valid_until, "ruleset.valid_until"
            ):
                raise ContractEligibilityError(
                    ContractEligibilityReason.TEMPORAL_INVALID,
                    "ruleset.valid_until is before ruleset.valid_from",
                )
        refs = _require_tuple(self.decision_refs, "ruleset.decision_refs")
        object.__setattr__(
            self,
            "decision_refs",
            tuple(
                _require_str(
                    value, "ruleset.decision_refs[%d]" % i, pattern=_REF_VALUE_PATTERN
                )
                for i, value in enumerate(refs)
            ),
        )

    def content(self) -> Dict[str, Any]:
        return {
            "ruleset_id": self.ruleset_id,
            "version": self.version,
            "issuer": self.issuer,
            "permitted_providers": list(self.permitted_providers),
            "permitted_jurisdictions": list(self.permitted_jurisdictions),
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "decision_refs": list(self.decision_refs),
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content()

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ContractEligibilityRuleset":
        if not isinstance(data, Mapping):
            raise ContractEligibilityError(
                ContractEligibilityReason.INVALID_INPUT, "ruleset must be a mapping"
            )
        return ContractEligibilityRuleset(
            ruleset_id=data.get("ruleset_id"),
            version=data.get("version"),
            issuer=data.get("issuer") or "",
            permitted_providers=tuple(data.get("permitted_providers") or ()),
            permitted_jurisdictions=tuple(data.get("permitted_jurisdictions") or ()),
            valid_from=data.get("valid_from") or "",
            valid_until=data.get("valid_until") or "",
            decision_refs=tuple(data.get("decision_refs") or ()),
        )

    def digest(self) -> str:
        return _derive_digest(self.content(), "ruleset record")

    def is_live(self, instant: str) -> bool:
        """Is the ruleset's own validity window live at the injected
        instant? (Inclusive bounds.)"""
        if self.valid_from and _parse_instant(instant, "instant") < _parse_instant(
            self.valid_from, "ruleset.valid_from"
        ):
            return False
        if self.valid_until and _parse_instant(instant, "instant") > _parse_instant(
            self.valid_until, "ruleset.valid_until"
        ):
            return False
        return True


# ----------------------------------------------------------------------
# The composed facts (caller-built snapshots of the canonical surfaces)
# ----------------------------------------------------------------------


#: The caller-composed facts for ONE offer reference — shared with the
#: constraint boundary (defined once, in ``contract_constraints``):
#: pure DATA read off the canonical public surfaces.  Offer usability
#: semantics stay M003's own; the ``usable`` flag carries the verdict.
OfferReferenceEligibilityFacts = OfferReferenceFacts


@dataclass(frozen=True)
class ContractReferenceFacts:
    """The caller-composed reference facts for ONE canonical contract —
    pure DATA read off the canonical M002 public surface: the contract
    identity, the lifecycle state (opaque DATA — the state machine
    stays M002's own), the terminal classification flag (derived by the
    composing caller from the canonical TERMINAL_STATES vocabulary —
    consumed by reference), the validity window (read verbatim), and
    the per-offer eligibility facts for every accepted offer reference
    (in the contract's own accepted-offer order)."""

    contract_id: str
    state: str
    state_is_terminal: bool
    validity: ValidityWindow
    offer_facts: Tuple[OfferReferenceEligibilityFacts, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "contract_id",
            _require_str(self.contract_id, "contract_facts.contract_id"),
        )
        object.__setattr__(
            self, "state", _require_str(self.state, "contract_facts.state")
        )
        object.__setattr__(
            self, "state_is_terminal", bool(self.state_is_terminal)
        )
        if isinstance(self.validity, ValidityWindow):
            pass
        elif isinstance(self.validity, Mapping):
            object.__setattr__(
                self, "validity", ValidityWindow.from_dict(self.validity)
            )
        else:
            raise ContractEligibilityError(
                ContractEligibilityReason.INVALID_INPUT,
                "contract_facts.validity must be a ValidityWindow record",
            )
        facts = _require_tuple(self.offer_facts, "contract_facts.offer_facts")
        object.__setattr__(
            self,
            "offer_facts",
            tuple(
                fact
                if isinstance(fact, OfferReferenceEligibilityFacts)
                else OfferReferenceEligibilityFacts(
                    value=fact.get("value"),
                    offer_id=fact.get("offer_id"),
                    provider=fact.get("provider"),
                    jurisdictions=tuple(fact.get("jurisdictions") or ()),
                    usable=fact.get("usable"),
                )
                for fact in facts
            ),
        )

    def content(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "state": self.state,
            "state_is_terminal": self.state_is_terminal,
            "validity": self.validity.to_dict(),
            "offer_facts": [f.to_dict() for f in self.offer_facts],
        }


# ----------------------------------------------------------------------
# The outcome records (decision DATA; canonical-serializable)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class OfferReferenceEligibility:
    """The eligibility outcome for ONE offer reference: ``eligible``
    iff NO denial reason fired; the ordered, deduplicated denial reason
    codes (DATA, never raised); the composed reference facts; the
    ruleset identity/version; the injected evaluation instant; and the
    content-derived evaluation digest (tamper evidence over the
    outcome basis)."""

    eligible: bool
    reasons: Tuple[str, ...]
    offer_id: str
    provider: str
    jurisdictions: Tuple[str, ...]
    ruleset_id: str
    ruleset_version: int
    at_instant: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "eligible", bool(self.eligible))
        reasons = _require_tuple(self.reasons, "outcome.reasons")
        for i, code in enumerate(reasons):
            if code not in ContractEligibilityReason.denial_values():
                raise ContractEligibilityError(
                    ContractEligibilityReason.VOCABULARY,
                    "outcome.reasons[%d] %r is not a denial reason code" % (i, code),
                )
        object.__setattr__(self, "reasons", _dedupe(reasons))
        if self.eligible and self.reasons:
            raise ContractEligibilityError(
                ContractEligibilityReason.INVALID_INPUT,
                "an eligible outcome must carry no denial reasons",
            )
        object.__setattr__(
            self, "offer_id", _require_str(self.offer_id, "outcome.offer_id")
        )
        object.__setattr__(
            self, "provider", _require_str(self.provider, "outcome.provider")
        )
        jurisdictions = _require_tuple(self.jurisdictions, "outcome.jurisdictions")
        object.__setattr__(
            self,
            "jurisdictions",
            tuple(
                _require_str(value, "outcome.jurisdictions[%d]" % i)
                for i, value in enumerate(jurisdictions)
            ),
        )
        object.__setattr__(
            self,
            "ruleset_id",
            _require_str(self.ruleset_id, "outcome.ruleset_id"),
        )
        object.__setattr__(
            self,
            "ruleset_version",
            _require_int(
                self.ruleset_version, "outcome.ruleset_version", minimum=1, maximum=10**6
            ),
        )
        object.__setattr__(
            self, "at_instant", _require_instant(self.at_instant, "outcome.at_instant")
        )

    def content(self) -> Dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "offer_id": self.offer_id,
            "provider": self.provider,
            "jurisdictions": list(self.jurisdictions),
            "ruleset_id": self.ruleset_id,
            "ruleset_version": self.ruleset_version,
            "at_instant": self.at_instant,
        }

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.content())
        data["evaluation_digest"] = self.evaluation_digest
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "OfferReferenceEligibility":
        if not isinstance(data, Mapping):
            raise ContractEligibilityError(
                ContractEligibilityReason.INVALID_INPUT,
                "offer eligibility outcome must be a mapping",
            )
        outcome = OfferReferenceEligibility(
            eligible=data.get("eligible"),
            reasons=tuple(data.get("reasons") or ()),
            offer_id=data.get("offer_id"),
            provider=data.get("provider"),
            jurisdictions=tuple(data.get("jurisdictions") or ()),
            ruleset_id=data.get("ruleset_id"),
            ruleset_version=data.get("ruleset_version"),
            at_instant=data.get("at_instant"),
        )
        supplied = data.get("evaluation_digest")
        if supplied is not None and supplied != outcome.evaluation_digest:
            raise ContractEligibilityError(
                ContractEligibilityReason.INVALID_INPUT,
                "evaluation_digest does not match the derived identity "
                "(tamper evidence)",
            )
        return outcome

    @property
    def evaluation_digest(self) -> str:
        return _derive_digest(self.content(), "offer eligibility outcome")


@dataclass(frozen=True)
class ContractEligibility:
    """The eligibility outcome for a canonical contract's reference set:
    ``eligible`` iff the contract-level reference facts are admissible
    AND every accepted offer reference is individually eligible.  The
    denial reasons are the deterministic merge of the contract-level
    reasons (fixed order) and the per-offer reasons (in the contract's
    own accepted-offer order), deduplicated order-preserving — the
    harvested W045 reason-collection discipline."""

    eligible: bool
    reasons: Tuple[str, ...]
    contract_id: str
    contract_state: str
    offer_outcomes: Tuple[OfferReferenceEligibility, ...]
    ruleset_id: str
    ruleset_version: int
    at_instant: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "eligible", bool(self.eligible))
        reasons = _require_tuple(self.reasons, "outcome.reasons")
        for i, code in enumerate(reasons):
            if code not in ContractEligibilityReason.denial_values():
                raise ContractEligibilityError(
                    ContractEligibilityReason.VOCABULARY,
                    "outcome.reasons[%d] %r is not a denial reason code" % (i, code),
                )
        object.__setattr__(self, "reasons", _dedupe(reasons))
        if self.eligible and self.reasons:
            raise ContractEligibilityError(
                ContractEligibilityReason.INVALID_INPUT,
                "an eligible outcome must carry no denial reasons",
            )
        object.__setattr__(
            self,
            "contract_id",
            _require_str(self.contract_id, "outcome.contract_id"),
        )
        object.__setattr__(
            self,
            "contract_state",
            _require_str(self.contract_state, "outcome.contract_state"),
        )
        outcomes = _require_tuple(self.offer_outcomes, "outcome.offer_outcomes")
        object.__setattr__(
            self,
            "offer_outcomes",
            tuple(
                outcome
                if isinstance(outcome, OfferReferenceEligibility)
                else OfferReferenceEligibility.from_dict(outcome)
                for outcome in outcomes
            ),
        )
        object.__setattr__(
            self,
            "ruleset_id",
            _require_str(self.ruleset_id, "outcome.ruleset_id"),
        )
        object.__setattr__(
            self,
            "ruleset_version",
            _require_int(
                self.ruleset_version, "outcome.ruleset_version", minimum=1, maximum=10**6
            ),
        )
        object.__setattr__(
            self, "at_instant", _require_instant(self.at_instant, "outcome.at_instant")
        )

    def content(self) -> Dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "contract_id": self.contract_id,
            "contract_state": self.contract_state,
            "offer_outcomes": [o.content() for o in self.offer_outcomes],
            "ruleset_id": self.ruleset_id,
            "ruleset_version": self.ruleset_version,
            "at_instant": self.at_instant,
        }

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.content())
        data["evaluation_digest"] = self.evaluation_digest
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ContractEligibility":
        if not isinstance(data, Mapping):
            raise ContractEligibilityError(
                ContractEligibilityReason.INVALID_INPUT,
                "contract eligibility outcome must be a mapping",
            )
        outcome = ContractEligibility(
            eligible=data.get("eligible"),
            reasons=tuple(data.get("reasons") or ()),
            contract_id=data.get("contract_id"),
            contract_state=data.get("contract_state"),
            offer_outcomes=tuple(
                OfferReferenceEligibility.from_dict(o)
                for o in data.get("offer_outcomes") or ()
            ),
            ruleset_id=data.get("ruleset_id"),
            ruleset_version=data.get("ruleset_version"),
            at_instant=data.get("at_instant"),
        )
        supplied = data.get("evaluation_digest")
        if supplied is not None and supplied != outcome.evaluation_digest:
            raise ContractEligibilityError(
                ContractEligibilityReason.INVALID_INPUT,
                "evaluation_digest does not match the derived identity "
                "(tamper evidence)",
            )
        return outcome

    @property
    def evaluation_digest(self) -> str:
        return _derive_digest(self.content(), "contract eligibility outcome")


# ----------------------------------------------------------------------
# Deterministic evaluation (the pure kernel)
# ----------------------------------------------------------------------


def _check_ruleset_live(
    ruleset: ContractEligibilityRuleset, at_instant: str
) -> None:
    """Fail closed when the ruleset is not live at the injected instant
    (a stale ruleset must never silently evaluate)."""
    if not ruleset.is_live(at_instant):
        raise ContractEligibilityError(
            ContractEligibilityReason.TEMPORAL_INVALID,
            "ruleset %r is not live at the evaluation instant %s "
            "(valid %s..%s; a stale ruleset never silently evaluates)"
            % (
                ruleset.ruleset_id,
                at_instant,
                ruleset.valid_from or "-inf",
                ruleset.valid_until or "+inf",
            ),
        )


def evaluate_offer_reference_eligibility(
    facts: OfferReferenceEligibilityFacts,
    ruleset: ContractEligibilityRuleset,
    *,
    at_instant: str,
) -> OfferReferenceEligibility:
    """Evaluate ONE composed offer-reference fact set for eligibility
    at the injected instant.

    BY REFERENCE (LOCK-101): offer usability, validity, withdrawal and
    supersession are the M003 exchange's own semantics — they arrive as
    the ``usable`` DATA flag on the composed facts, never re-implemented
    here.  An unusable offer is a DENIAL (decision DATA — the reference
    is not eligible), never a raised error.

    Fail closed: a provider outside the explicit permitted list, a
    jurisdiction the explicit permitted list does not cover, an absent
    provider/jurisdiction fact — each is a denial, never an approval."""

    if not isinstance(facts, OfferReferenceEligibilityFacts):
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "evaluate_offer_reference_eligibility requires "
            "OfferReferenceEligibilityFacts",
        )
    if not isinstance(ruleset, ContractEligibilityRuleset):
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "evaluate_offer_reference_eligibility requires a "
            "ContractEligibilityRuleset",
        )
    _parse_instant(at_instant, "evaluation.at_instant")
    _check_ruleset_live(ruleset, at_instant)

    reasons: List[str] = []
    if not facts.usable:
        # The M003 exchange did not resolve the reference as usable at
        # the composition instant (withdrawn / expired / not-yet-valid /
        # superseded / unknown): an eligibility FACT — denial DATA, the
        # harvested W045 separation (never a raised error).
        reasons.append(ContractEligibilityReason.OFFER_NOT_USABLE)
        return OfferReferenceEligibility(
            eligible=False,
            reasons=tuple(reasons),
            offer_id=facts.offer_id,
            provider=facts.provider,
            jurisdictions=facts.jurisdictions,
            ruleset_id=ruleset.ruleset_id,
            ruleset_version=ruleset.version,
            at_instant=at_instant,
        )

    provider = facts.provider
    jurisdictions = facts.jurisdictions

    if provider not in ruleset.permitted_providers:
        reasons.append(ContractEligibilityReason.PROVIDER_NOT_PERMITTED)
    if not jurisdictions:
        # An offer with no service-boundary jurisdiction facts cannot
        # certify jurisdiction eligibility: fail closed.
        reasons.append(ContractEligibilityReason.JURISDICTION_NOT_COVERED)
    elif not any(
        jurisdiction in ruleset.permitted_jurisdictions
        for jurisdiction in jurisdictions
    ):
        reasons.append(ContractEligibilityReason.JURISDICTION_NOT_COVERED)

    return OfferReferenceEligibility(
        eligible=not reasons,
        reasons=_dedupe(reasons),
        offer_id=facts.offer_id,
        provider=provider,
        jurisdictions=jurisdictions,
        ruleset_id=ruleset.ruleset_id,
        ruleset_version=ruleset.version,
        at_instant=at_instant,
    )


def evaluate_contract_reference_eligibility(
    facts: ContractReferenceFacts,
    ruleset: ContractEligibilityRuleset,
    *,
    at_instant: str,
) -> ContractEligibility:
    """Evaluate the eligibility of a canonical contract's reference set
    at the injected instant, over the caller-composed facts.

    A PURE function of (composed contract reference facts, ruleset,
    injected instant): no wall clock, no randomness, no network, and NO
    mutation of any authority (LOCK-101/LOCK-119).

    Contract-level checks (fixed order, the harvested W045 discipline):
    the contract must not be in a terminal lifecycle state (terminal
    contracts are settled history — never newly eligible); the
    contract's validity window must contain the evaluation instant;
    the contract must carry at least one accepted offer reference.
    Then every offer reference is evaluated individually (in the
    contract's own accepted-offer order) and the denial reasons merge
    deterministically.

    Contract semantics are READ, never re-implemented: the state, the
    terminal classification and the validity window arrive as composed
    DATA from the canonical M002 public surface."""

    if not isinstance(facts, ContractReferenceFacts):
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "evaluate_contract_reference_eligibility requires "
            "ContractReferenceFacts",
        )
    if not isinstance(ruleset, ContractEligibilityRuleset):
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "evaluate_contract_reference_eligibility requires a "
            "ContractEligibilityRuleset",
        )
    _parse_instant(at_instant, "evaluation.at_instant")
    _check_ruleset_live(ruleset, at_instant)

    contract_reasons: List[str] = []
    if facts.state_is_terminal:
        contract_reasons.append(ContractEligibilityReason.CONTRACT_TERMINAL)
    if not facts.validity.contains(at_instant):
        contract_reasons.append(ContractEligibilityReason.CONTRACT_NOT_LIVE)
    if not facts.offer_facts:
        contract_reasons.append(ContractEligibilityReason.NO_ACCEPTED_OFFERS)

    offer_outcomes = tuple(
        evaluate_offer_reference_eligibility(
            offer_facts, ruleset, at_instant=at_instant
        )
        for offer_facts in facts.offer_facts
    )

    merged = _dedupe(
        tuple(contract_reasons)
        + tuple(code for outcome in offer_outcomes for code in outcome.reasons)
    )
    return ContractEligibility(
        eligible=not merged,
        reasons=merged,
        contract_id=facts.contract_id,
        contract_state=facts.state,
        offer_outcomes=offer_outcomes,
        ruleset_id=ruleset.ruleset_id,
        ruleset_version=ruleset.version,
        at_instant=at_instant,
    )


# ----------------------------------------------------------------------
# Wire-form helpers (canonical-JSON round-trips)
# ----------------------------------------------------------------------


def contract_eligibility_ruleset_from_mapping(
    data: Mapping[str, Any],
) -> ContractEligibilityRuleset:
    """Reconstruct a ruleset from its canonical mapping (the wire
    form).  Fail-closed: unknown members, malformed values, a missing
    issuer and secret-shaped material are rejected (LOCK-118/119)."""
    if not isinstance(data, Mapping):
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "ruleset wire form must be a mapping",
        )
    known = {
        "ruleset_id",
        "version",
        "issuer",
        "permitted_providers",
        "permitted_jurisdictions",
        "valid_from",
        "valid_until",
        "decision_refs",
    }
    unknown = sorted(set(data) - known)
    if unknown:
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "unknown ruleset members: %s" % unknown,
        )
    return ContractEligibilityRuleset.from_dict(data)


def offer_reference_eligibility_from_mapping(
    data: Mapping[str, Any],
) -> OfferReferenceEligibility:
    """Reconstruct an offer-reference eligibility outcome from its
    canonical mapping (round-trip; tamper-evident via the derived
    digest)."""
    if not isinstance(data, Mapping):
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "outcome wire form must be a mapping",
        )
    known = {
        "eligible",
        "reasons",
        "offer_id",
        "provider",
        "jurisdictions",
        "ruleset_id",
        "ruleset_version",
        "at_instant",
        "evaluation_digest",
    }
    unknown = sorted(set(data) - known)
    if unknown:
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "unknown outcome members: %s" % unknown,
        )
    return OfferReferenceEligibility.from_dict(data)


def contract_eligibility_from_mapping(
    data: Mapping[str, Any],
) -> ContractEligibility:
    """Reconstruct a contract eligibility outcome from its canonical
    mapping (round-trip; tamper-evident via the derived digest)."""
    if not isinstance(data, Mapping):
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "outcome wire form must be a mapping",
        )
    known = {
        "eligible",
        "reasons",
        "contract_id",
        "contract_state",
        "offer_outcomes",
        "ruleset_id",
        "ruleset_version",
        "at_instant",
        "evaluation_digest",
    }
    unknown = sorted(set(data) - known)
    if unknown:
        raise ContractEligibilityError(
            ContractEligibilityReason.INVALID_INPUT,
            "unknown outcome members: %s" % unknown,
        )
    return ContractEligibility.from_dict(data)


__all__ = [
    "ContractEligibility",
    "ContractEligibilityError",
    "ContractEligibilityReason",
    "ContractEligibilityRuleset",
    "ContractReferenceFacts",
    "OfferReferenceEligibility",
    "OfferReferenceEligibilityFacts",
    "contract_eligibility_from_mapping",
    "contract_eligibility_ruleset_from_mapping",
    "evaluate_contract_reference_eligibility",
    "evaluate_offer_reference_eligibility",
    "offer_reference_eligibility_from_mapping",
]
