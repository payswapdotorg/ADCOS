"""ADCOS contract-constraint policy evaluation (M004 — Eligibility and
Policy; R7-CORE-001 child, DEC-0101; frozen 1.1 sections 2/9: the
``Eligibility + Policy`` stage of the closed loop, AROUND the canonical
contract).

Migration-matrix classification (spec/migration/classification-matrix.md):
"Policy: RETAIN + REFACTOR -> Eligibility + contract constraints".  This
module is the REFACTOR half — the harvested WORK-010 policy disciplines
(deny-by-default, deterministic conflict resolution, fail-closed typed
errors, injected instants, canonical bytes) re-targeted onto the 1.1
authority model: explicit rules that guard contract-domain actions and
evaluate against contract/offer reference FACTS at an injected instant.

Consumption discipline (LOCK-101, the harvested WORK-045 snapshot seam —
the strongest by-reference form): this module NEVER imports the
canonical domains.  The evaluation consumes caller-composed pure-DATA
snapshots built from the canonical public surfaces —
``contracts/`` (M002, DEC-0102) for the contract reference facts and
``offers/`` (M003, DEC-0103) for the resolved offer facts.  The module
never queries, instantiates, or mutates any canonical authority, and
never re-implements contract or offer semantics: state, validity,
constraint kinds and offer usability are READ as opaque DATA by the
composing caller.  The canonical vocabularies (principal kinds,
constraint kinds, contract states, the M002 command kinds behind the
guarded actions) stay owned by their canonical authorities — this
module treats them as opaque selector strings and never enumerates
them (no second vocabulary authority that could drift); the
composition boundary (the M004 battery) pins the projection against
the canonical source.

Landing note (disclosed in docs/M004-evidence.md): the matrix routes
Policy to the single target authority "Eligibility + contract
constraints", and the module lands in ``eligibility/`` because the
M009-accepted payment battery (``tools/payment_selftest.py`` case_38,
DEC-0109 — not M004 material) freezes the whole ``policy`` family
against any delta, while this family's frozen import discipline
(stdlib + ``protocol.canonicalization`` + ``agent.clock`` only) is
satisfied by the snapshot design.

The central boundary (exercised case-by-case in the M004 battery):

    CONTRACT-CONSTRAINT DECISION
      = evaluation of explicit rules against explicit contract/offer
        reference FACTS at an injected instant

    CONTRACT-CONSTRAINT DECISION  !=  CONTRACT AUTHORITY (LOCK-101:
        the canonical ConnectivityContract and its store stay the
        sole authority; this module never sees a contract object —
        only caller-composed reference facts)
    CONTRACT-CONSTRAINT DECISION  !=  OFFER SEMANTICS (LOCK-101:
        offer usability/validity/withdrawal are the M003 exchange's
        own; they arrive as the ``usable`` DATA flag on composed
        offer facts)
    CONTRACT-CONSTRAINT DECISION  !=  ELIGIBILITY CONFERENCE (an
        ALLOW never confers eligibility — the M004 eligibility
        surface in ``contract_eligibility.py`` answers eligibility;
        policy answers permission)
    CONTRACT-CONSTRAINT DECISION  !=  PROVIDER SDK SURFACE (LOCK-110:
        providers appear only as opaque reference values; the
        evaluation is technology-neutral)

Determinism discipline (LOCK-119): injected RFC 3339 UTC instants only
(no wall clock); canonical JSON over ``protocol.canonicalization``;
sorted iteration everywhere; content-derived digests; no randomness,
no network; secret-shaped labels and values are rejected at
construction and deserialization time.

Harvested WORK-010 semantics preserved case-for-case (see the M004
battery section): deny-by-default for every guarded action; explicit
deny beats allow at equal precedence; higher specificity then higher
priority wins; equal-precedence ambiguity fails closed; require-review
never silently becomes allow; a missing fact is a non-match, never an
approval; the decision is attributable to its matched rule ids and
policy version (audit trail).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from agent.clock import AgentError, parse_utc

# ----------------------------------------------------------------------
# Typed error model (namespaced ``contract-constraint-*``; fail closed)
# ----------------------------------------------------------------------


class ContractConstraintReason:
    """The frozen M004 contract-constraint reason vocabulary (namespaced
    so a composed surface can never confuse a contract-constraint reason
    with a contract reason, an offer reason, or an eligibility reason)."""

    #: malformed input at any public boundary
    INVALID_INPUT = "contract-constraint-invalid-input"
    #: a temporal value is malformed or an interval is impossible
    TEMPORAL_INVALID = "contract-constraint-temporal-invalid"
    #: a value outside a frozen vocabulary
    VOCABULARY = "contract-constraint-vocabulary"
    #: secret-shaped material rejected at the boundary (LOCK-119)
    SECRET_REJECTED = "contract-constraint-secret-rejected"
    #: externally asserted material without an issuer (LOCK-118)
    PROVENANCE_REQUIRED = "contract-constraint-provenance-required"
    #: a supplied content-derived id does not match the derived identity
    ID_MISMATCH = "contract-constraint-id-mismatch"


class ContractConstraintError(ValueError):
    """Raised when a contract-constraint record or evaluation input
    violates its boundary contract (fail closed).  ``code`` is a stable
    machine-readable reason from :class:`ContractConstraintReason`; the
    detail is deterministic and never echoes secret-shaped material
    (LOCK-119)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


# ----------------------------------------------------------------------
# Frozen vocabularies (M004-local; canonical vocabularies are consumed
# as opaque DATA — never enumerated here, never a second authority)
# ----------------------------------------------------------------------


class ContractConstraintEffect:
    """The frozen M004 effect vocabulary (the harvested WORK-010 triple)."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_REVIEW = "require-review"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.ALLOW, cls.DENY, cls.REQUIRE_REVIEW)


class ContractConstraintDecisionCode:
    """The frozen M004 decision-code vocabulary (harvested WORK-010
    codes, namespaced to the contract-constraint boundary; NOT collapsed
    into a generic false — auditability requires the distinction)."""

    ALLOW = "allow"
    DENY = "deny"
    DEFAULT_DENY = "default-deny"
    REQUIRE_REVIEW = "require-review"
    FAIL_CLOSED = "fail-closed"
    POLICY_EXPIRED = "policy-expired"
    POLICY_NOT_YET_VALID = "policy-not-yet-valid"
    MISSING_FACT = "missing-fact"
    CONFLICT = "conflict"
    INVALID_POLICY = "invalid-policy"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.ALLOW,
            cls.DENY,
            cls.DEFAULT_DENY,
            cls.REQUIRE_REVIEW,
            cls.FAIL_CLOSED,
            cls.POLICY_EXPIRED,
            cls.POLICY_NOT_YET_VALID,
            cls.MISSING_FACT,
            cls.CONFLICT,
            cls.INVALID_POLICY,
        )


class ContractConstraintPredicateKind:
    """The frozen M004 predicate vocabulary: typed reference-fact
    matchers over the composed contract/offer facts.  Conditions are
    ``(predicate, arguments)`` DATA — never executable code."""

    PRINCIPAL_KIND = "principal-kind"
    PRINCIPAL_REF = "principal-ref"
    BENEFICIARY_KIND = "beneficiary-kind"
    OFFER_PROVIDER = "offer-provider"
    OFFER_JURISDICTION = "offer-jurisdiction"
    CONSTRAINT_KIND = "constraint-kind"
    CONTRACT_STATE = "contract-state"
    VALIDITY_LIVE = "validity-live"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.PRINCIPAL_KIND,
            cls.PRINCIPAL_REF,
            cls.BENEFICIARY_KIND,
            cls.OFFER_PROVIDER,
            cls.OFFER_JURISDICTION,
            cls.CONSTRAINT_KIND,
            cls.CONTRACT_STATE,
            cls.VALIDITY_LIVE,
        )


_SECRET_NAME_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$")
#: Guarded actions are OPAQUE ``contract.``-namespaced strings: the
#: canonical M002 command vocabulary is consumed BY REFERENCE at the
#: composition boundary (LOCK-101: this module never enumerates it).
_ACTION_PATTERN = re.compile(r"^contract\.[a-z][a-z0-9-]{0,63}$")
_REF_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")
_RULE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_INSTANT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"
)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _reject_secret(value: object, label: str) -> None:
    """LOCK-119 guard: secret-shaped material never enters policy data."""
    if _SECRET_NAME_PATTERN.search(label):
        raise ContractConstraintError(
            ContractConstraintReason.SECRET_REJECTED,
            "%s looks like secret material; secrets never enter "
            "contract-constraint data" % label,
        )
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.match(value):
        raise ContractConstraintError(
            ContractConstraintReason.SECRET_REJECTED,
            "%s carries a secret-shaped value; secrets never enter "
            "contract-constraint data" % label,
        )


def _require_str(value: object, label: str, *, pattern: Optional[re.Pattern] = None) -> str:
    if not isinstance(value, str) or not value:
        raise ContractConstraintError(
            ContractConstraintReason.INVALID_INPUT, "%s must be a non-empty string" % label
        )
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ContractConstraintError(
            ContractConstraintReason.INVALID_INPUT, "%s has an invalid format: %r" % (label, value)
        )
    _reject_secret(value, label)
    return value


def _require_in(value: object, vocabulary: Sequence[str], label: str) -> str:
    if value not in vocabulary:
        raise ContractConstraintError(
            ContractConstraintReason.VOCABULARY,
            "%s must be one of %s (found %r)" % (label, ", ".join(vocabulary), value),
        )
    return str(value)


def _parse_instant(value: object, label: str):
    """Parse an RFC 3339 UTC instant through the injected clock seam
    (agent.clock — the WORK-033 discipline; no wall clock anywhere)."""
    if not isinstance(value, str) or not value:
        raise ContractConstraintError(
            ContractConstraintReason.TEMPORAL_INVALID,
            "%s must be a non-empty RFC 3339 UTC instant string" % label,
        )
    try:
        return parse_utc(value)
    except (AgentError, ValueError) as error:
        raise ContractConstraintError(
            ContractConstraintReason.TEMPORAL_INVALID, "%s is invalid: %s" % (label, error)
        ) from None


def _require_instant(value: object, label: str) -> str:
    _parse_instant(value, label)
    return str(value)


def _require_int(value: object, label: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractConstraintError(
            ContractConstraintReason.INVALID_INPUT, "%s must be an integer" % label
        )
    if not minimum <= value <= maximum:
        raise ContractConstraintError(
            ContractConstraintReason.INVALID_INPUT,
            "%s must be within [%d, %d]" % (label, minimum, maximum),
        )
    return value


def _require_tuple(value: object, label: str) -> Tuple[Any, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    raise ContractConstraintError(
        ContractConstraintReason.INVALID_INPUT, "%s must be a sequence" % label
    )


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise ContractConstraintError(
            ContractConstraintReason.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_digest(document: Mapping[str, Any], label: str) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(document, label)).hexdigest()


# ----------------------------------------------------------------------
# The validity window (generic temporal DATA; consumed by reference)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ValidityWindow:
    """A closed validity window over injected instants (generic temporal
    DATA — [not_before, not_after], both bounds inclusive; the temporal
    machinery is the injected clock seam, never a wall clock).  Contract
    validity SEMANTICS stay owned by the canonical M002 domain: the
    composing caller reads the canonical record's window verbatim."""

    not_before: str
    not_after: str

    def __post_init__(self) -> None:
        before = _parse_instant(self.not_before, "window.not_before")
        after = _parse_instant(self.not_after, "window.not_after")
        if before > after:
            raise ContractConstraintError(
                ContractConstraintReason.TEMPORAL_INVALID,
                "window.not_after is before window.not_before",
            )

    def contains(self, instant: str) -> bool:
        return (
            _parse_instant(self.not_before, "window.not_before")
            <= _parse_instant(instant, "window.instant")
            <= _parse_instant(self.not_after, "window.not_after")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"not_before": self.not_before, "not_after": self.not_after}

    @staticmethod
    def from_dict(data: object) -> "ValidityWindow":
        if not isinstance(data, Mapping):
            raise ContractConstraintError(
                ContractConstraintReason.INVALID_INPUT, "window must be a mapping"
            )
        return ValidityWindow(
            not_before=data.get("not_before"), not_after=data.get("not_after")
        )


# ----------------------------------------------------------------------
# Conditions (typed reference-fact matchers; DATA, never code)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ContractConstraintCondition:
    """One typed condition over composed contract/offer reference
    facts: ``(predicate, arguments)``.  Arguments are scalar DATA; the
    canonical vocabularies they select within (principal kinds,
    constraint kinds, contract states) are owned by the canonical
    domains — this module validates the argument GRAMMAR, and the
    composition boundary pins the values against the canonical
    vocabularies (LOCK-101: no second vocabulary authority)."""

    predicate: str
    arguments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "predicate",
            _require_in(
                self.predicate,
                ContractConstraintPredicateKind.values(),
                "condition.predicate",
            ),
        )
        if not isinstance(self.arguments, Mapping):
            raise ContractConstraintError(
                ContractConstraintReason.INVALID_INPUT,
                "condition.arguments must be a mapping of scalar DATA",
            )
        arguments: Dict[str, Any] = {}
        for key in sorted(self.arguments):
            if not isinstance(key, str) or not key:
                raise ContractConstraintError(
                    ContractConstraintReason.INVALID_INPUT,
                    "condition.arguments keys must be non-empty strings",
                )
            value = self.arguments[key]
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                raise ContractConstraintError(
                    ContractConstraintReason.INVALID_INPUT,
                    "condition.arguments[%r] must be a scalar (str/int)" % key,
                )
            _reject_secret(value, "condition.arguments[%r]" % key)
            arguments[key] = value
        object.__setattr__(self, "arguments", arguments)
        self._validate_argument_shape()

    def _validate_argument_shape(self) -> None:
        predicate = self.predicate
        if predicate == ContractConstraintPredicateKind.VALIDITY_LIVE:
            if self.arguments:
                raise ContractConstraintError(
                    ContractConstraintReason.INVALID_INPUT,
                    "predicate %s takes no arguments" % predicate,
                )
            return
        expected_key = {
            ContractConstraintPredicateKind.PRINCIPAL_KIND: "kind",
            ContractConstraintPredicateKind.BENEFICIARY_KIND: "kind",
            ContractConstraintPredicateKind.CONSTRAINT_KIND: "kind",
            ContractConstraintPredicateKind.CONTRACT_STATE: "state",
            ContractConstraintPredicateKind.PRINCIPAL_REF: "ref",
            ContractConstraintPredicateKind.OFFER_PROVIDER: "provider",
            ContractConstraintPredicateKind.OFFER_JURISDICTION: "jurisdiction",
        }.get(predicate)
        if expected_key is None:
            raise ContractConstraintError(
                ContractConstraintReason.VOCABULARY,
                "predicate %r has no argument grammar" % predicate,
            )
        if set(self.arguments) != {expected_key}:
            raise ContractConstraintError(
                ContractConstraintReason.INVALID_INPUT,
                "predicate %s requires exactly the %r argument"
                % (predicate, expected_key),
            )
        _require_str(
            self.arguments[expected_key],
            "condition.arguments.%s" % expected_key,
            pattern=_REF_VALUE_PATTERN,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"predicate": self.predicate, "arguments": dict(self.arguments)}

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ContractConstraintCondition":
        if not isinstance(data, Mapping):
            raise ContractConstraintError(
                ContractConstraintReason.INVALID_INPUT, "condition must be a mapping"
            )
        return ContractConstraintCondition(
            predicate=data.get("predicate"), arguments=data.get("arguments") or {}
        )


# ----------------------------------------------------------------------
# Rules and policy sets
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ContractConstraintRule:
    """One explicit policy rule guarding contract-domain actions.

    Field set: the rule id; the guarded action (an OPAQUE
    ``contract.``-namespaced string — the canonical M002 command
    vocabulary is consumed by reference at the composition boundary);
    the effect (allow / deny / require-review); the subject selector
    (principal reference values; empty = every subject); the
    conditions; explicit precedence (``specificity`` then
    ``priority``); the rule's own validity window; the MANDATORY issuer
    and decision references (LOCK-118: an anonymous rule is never
    evaluable); and the schema version.  Rules are immutable DATA."""

    rule_id: str
    action: str
    effect: str
    subjects: Tuple[str, ...] = ()
    conditions: Tuple[ContractConstraintCondition, ...] = ()
    specificity: int = 0
    priority: int = 0
    valid_from: str = ""
    valid_until: str = ""
    issuer: str = ""
    decision_refs: Tuple[str, ...] = ()
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rule_id",
            _require_str(self.rule_id, "rule.rule_id", pattern=_RULE_ID_PATTERN),
        )
        object.__setattr__(
            self, "action", _require_str(self.action, "rule.action", pattern=_ACTION_PATTERN)
        )
        object.__setattr__(
            self,
            "effect",
            _require_in(self.effect, ContractConstraintEffect.values(), "rule.effect"),
        )
        subjects = _require_tuple(self.subjects, "rule.subjects")
        object.__setattr__(
            self,
            "subjects",
            tuple(
                _require_str(
                    value, "rule.subjects[%d]" % i, pattern=_REF_VALUE_PATTERN
                )
                for i, value in enumerate(subjects)
            ),
        )
        conditions = _require_tuple(self.conditions, "rule.conditions")
        normalized = []
        for i, condition in enumerate(conditions):
            if isinstance(condition, ContractConstraintCondition):
                normalized.append(condition)
            elif isinstance(condition, Mapping):
                normalized.append(ContractConstraintCondition.from_dict(condition))
            else:
                raise ContractConstraintError(
                    ContractConstraintReason.INVALID_INPUT,
                    "rule.conditions[%d] must be a ContractConstraintCondition" % i,
                )
        object.__setattr__(self, "conditions", tuple(normalized))
        object.__setattr__(
            self,
            "specificity",
            _require_int(self.specificity, "rule.specificity", minimum=0, maximum=10**6),
        )
        object.__setattr__(
            self,
            "priority",
            _require_int(self.priority, "rule.priority", minimum=0, maximum=10**6),
        )
        if self.valid_from:
            object.__setattr__(
                self, "valid_from", _require_instant(self.valid_from, "rule.valid_from")
            )
        if self.valid_until:
            object.__setattr__(
                self, "valid_until", _require_instant(self.valid_until, "rule.valid_until")
            )
        if self.valid_from and self.valid_until:
            if _parse_instant(self.valid_from, "rule.valid_from") > _parse_instant(
                self.valid_until, "rule.valid_until"
            ):
                raise ContractConstraintError(
                    ContractConstraintReason.TEMPORAL_INVALID,
                    "rule.valid_until is before rule.valid_from",
                )
        object.__setattr__(
            self,
            "issuer",
            _require_str(self.issuer, "rule.issuer"),
        )
        refs = _require_tuple(self.decision_refs, "rule.decision_refs")
        object.__setattr__(
            self,
            "decision_refs",
            tuple(
                _require_str(
                    value, "rule.decision_refs[%d]" % i, pattern=_REF_VALUE_PATTERN
                )
                for i, value in enumerate(refs)
            ),
        )
        object.__setattr__(
            self,
            "version",
            _require_int(self.version, "rule.version", minimum=1, maximum=10**6),
        )

    def content(self) -> Dict[str, Any]:
        """The canonical content basis (the digest/round-trip basis)."""
        return {
            "rule_id": self.rule_id,
            "action": self.action,
            "effect": self.effect,
            "subjects": list(self.subjects),
            "conditions": [c.to_dict() for c in self.conditions],
            "specificity": self.specificity,
            "priority": self.priority,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "issuer": self.issuer,
            "decision_refs": list(self.decision_refs),
            "version": self.version,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content()

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ContractConstraintRule":
        if not isinstance(data, Mapping):
            raise ContractConstraintError(
                ContractConstraintReason.INVALID_INPUT, "rule must be a mapping"
            )
        return ContractConstraintRule(
            rule_id=data.get("rule_id"),
            action=data.get("action"),
            effect=data.get("effect"),
            subjects=tuple(data.get("subjects") or ()),
            conditions=tuple(
                ContractConstraintCondition.from_dict(c)
                for c in data.get("conditions") or ()
            ),
            specificity=data.get("specificity") or 0,
            priority=data.get("priority") or 0,
            valid_from=data.get("valid_from") or "",
            valid_until=data.get("valid_until") or "",
            issuer=data.get("issuer") or "",
            decision_refs=tuple(data.get("decision_refs") or ()),
            version=data.get("version") or 1,
        )


@dataclass(frozen=True)
class ContractConstraintSet:
    """An explicit, issuer-identified set of contract-constraint rules
    with a default effect (deny — deny-by-default is structural for
    every guarded contract action) and its own validity window.  The
    issuer is MANDATORY (LOCK-118 + the harvested WORK-010
    issuer-mandatory discipline: an anonymous policy is never
    evaluable)."""

    set_id: str
    version: int
    rules: Tuple[ContractConstraintRule, ...]
    issuer: str
    default_effect: str = ContractConstraintEffect.DENY
    valid_from: str = ""
    valid_until: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "set_id",
            _require_str(self.set_id, "set.set_id", pattern=_RULE_ID_PATTERN),
        )
        object.__setattr__(
            self,
            "version",
            _require_int(self.version, "set.version", minimum=1, maximum=10**6),
        )
        object.__setattr__(
            self, "issuer", _require_str(self.issuer, "set.issuer")
        )
        object.__setattr__(
            self,
            "default_effect",
            _require_in(
                self.default_effect, ContractConstraintEffect.values(), "set.default_effect"
            ),
        )
        if self.default_effect != ContractConstraintEffect.DENY:
            raise ContractConstraintError(
                ContractConstraintReason.VOCABULARY,
                "set.default_effect must be deny — every guarded contract action is "
                "privileged; deny-by-default is structural (LOCK-108 discipline)",
            )
        rules = _require_tuple(self.rules, "set.rules")
        normalized = []
        seen_ids = set()
        for i, rule in enumerate(rules):
            if isinstance(rule, ContractConstraintRule):
                normalized.append(rule)
            elif isinstance(rule, Mapping):
                normalized.append(ContractConstraintRule.from_dict(rule))
            else:
                raise ContractConstraintError(
                    ContractConstraintReason.INVALID_INPUT,
                    "set.rules[%d] must be a ContractConstraintRule" % i,
                )
            rule_id = normalized[-1].rule_id
            if rule_id in seen_ids:
                raise ContractConstraintError(
                    ContractConstraintReason.INVALID_INPUT,
                    "duplicate rule_id %r in the constraint set" % rule_id,
                )
            seen_ids.add(rule_id)
        object.__setattr__(self, "rules", tuple(normalized))
        if self.valid_from:
            object.__setattr__(
                self, "valid_from", _require_instant(self.valid_from, "set.valid_from")
            )
        if self.valid_until:
            object.__setattr__(
                self, "valid_until", _require_instant(self.valid_until, "set.valid_until")
            )
        if self.valid_from and self.valid_until:
            if _parse_instant(self.valid_from, "set.valid_from") > _parse_instant(
                self.valid_until, "set.valid_until"
            ):
                raise ContractConstraintError(
                    ContractConstraintReason.TEMPORAL_INVALID,
                    "set.valid_until is before set.valid_from",
                )

    def content(self) -> Dict[str, Any]:
        return {
            "set_id": self.set_id,
            "version": self.version,
            "rules": [r.to_dict() for r in self.rules],
            "issuer": self.issuer,
            "default_effect": self.default_effect,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content()

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ContractConstraintSet":
        if not isinstance(data, Mapping):
            raise ContractConstraintError(
                ContractConstraintReason.INVALID_INPUT, "constraint set must be a mapping"
            )
        return ContractConstraintSet(
            set_id=data.get("set_id"),
            version=data.get("version"),
            rules=tuple(
                ContractConstraintRule.from_dict(r) for r in data.get("rules") or ()
            ),
            issuer=data.get("issuer"),
            default_effect=data.get("default_effect") or ContractConstraintEffect.DENY,
            valid_from=data.get("valid_from") or "",
            valid_until=data.get("valid_until") or "",
        )

    def digest(self) -> str:
        """Content-derived digest over the canonical set bytes."""
        return _derive_digest(self.content(), "constraint set record")


# ----------------------------------------------------------------------
# The composed facts: offer reference facts + the constraint context
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class OfferReferenceFacts:
    """The caller-composed facts about ONE accepted offer reference —
    pure DATA read off the canonical public surfaces: the reference
    value, the resolved offer id, the provider domain identity (an
    opaque reference value — LOCK-110), the service-boundary
    jurisdictions, and whether the M003 exchange currently resolves
    the reference as USABLE at the composition instant.  Offer
    usability semantics stay M003's own; this carries the verdict as
    DATA."""

    value: str
    offer_id: str
    provider: str
    jurisdictions: Tuple[str, ...]
    usable: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _require_str(self.value, "offer_facts.value")
        )
        object.__setattr__(
            self, "offer_id", _require_str(self.offer_id, "offer_facts.offer_id")
        )
        object.__setattr__(
            self, "provider", _require_str(self.provider, "offer_facts.provider")
        )
        jurisdictions = _require_tuple(self.jurisdictions, "offer_facts.jurisdictions")
        object.__setattr__(
            self,
            "jurisdictions",
            tuple(
                _require_str(value, "offer_facts.jurisdictions[%d]" % i)
                for i, value in enumerate(jurisdictions)
            ),
        )
        object.__setattr__(self, "usable", bool(self.usable))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "offer_id": self.offer_id,
            "provider": self.provider,
            "jurisdictions": list(self.jurisdictions),
            "usable": self.usable,
        }


@dataclass(frozen=True)
class ContractConstraintContext:
    """The caller-composed evaluated facts for one contract-constraint
    evaluation: the guarded action (an opaque ``contract.``-namespaced
    string pinned to the canonical M002 command vocabulary at the
    composition boundary), the principal/beneficiary reference facts,
    the contract state and hard-constraint kinds (opaque DATA read off
    the canonical record — never re-implemented semantics), the
    contract validity window, the composed offer reference facts
    (OPTIONAL — absent facts make offer-fact conditions non-matches
    with the missing-fact observation recorded, never approvals), and
    the injected evaluation instant."""

    action: str
    principal_kind: str
    principal_ref: str
    beneficiary_kinds: Tuple[str, ...]
    contract_state: str
    hard_constraint_kinds: Tuple[str, ...]
    validity: ValidityWindow
    accepted_offer_values: Tuple[str, ...]
    offer_facts: Tuple[OfferReferenceFacts, ...] = ()
    evaluation_instant: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "action", _require_str(self.action, "context.action", pattern=_ACTION_PATTERN)
        )
        object.__setattr__(
            self,
            "principal_kind",
            _require_str(self.principal_kind, "context.principal_kind"),
        )
        object.__setattr__(
            self,
            "principal_ref",
            _require_str(
                self.principal_ref, "context.principal_ref", pattern=_REF_VALUE_PATTERN
            ),
        )
        kinds = _require_tuple(self.beneficiary_kinds, "context.beneficiary_kinds")
        object.__setattr__(
            self,
            "beneficiary_kinds",
            tuple(
                _require_str(value, "context.beneficiary_kinds[%d]" % i)
                for i, value in enumerate(kinds)
            ),
        )
        object.__setattr__(
            self,
            "contract_state",
            _require_str(self.contract_state, "context.contract_state"),
        )
        constraint_kinds = _require_tuple(
            self.hard_constraint_kinds, "context.hard_constraint_kinds"
        )
        object.__setattr__(
            self,
            "hard_constraint_kinds",
            tuple(
                _require_str(value, "context.hard_constraint_kinds[%d]" % i)
                for i, value in enumerate(constraint_kinds)
            ),
        )
        if isinstance(self.validity, ValidityWindow):
            pass
        elif isinstance(self.validity, Mapping):
            object.__setattr__(
                self, "validity", ValidityWindow.from_dict(self.validity)
            )
        else:
            raise ContractConstraintError(
                ContractConstraintReason.INVALID_INPUT,
                "context.validity must be a ValidityWindow record",
            )
        values = _require_tuple(self.accepted_offer_values, "context.accepted_offer_values")
        object.__setattr__(
            self,
            "accepted_offer_values",
            tuple(
                _require_str(value, "context.accepted_offer_values[%d]" % i)
                for i, value in enumerate(values)
            ),
        )
        facts = _require_tuple(self.offer_facts, "context.offer_facts")
        normalized_facts = []
        for i, fact in enumerate(facts):
            if isinstance(fact, OfferReferenceFacts):
                normalized_facts.append(fact)
            elif isinstance(fact, Mapping):
                normalized_facts.append(
                    OfferReferenceFacts(
                        value=fact.get("value"),
                        offer_id=fact.get("offer_id"),
                        provider=fact.get("provider"),
                        jurisdictions=tuple(fact.get("jurisdictions") or ()),
                        usable=fact.get("usable"),
                    )
                )
            else:
                raise ContractConstraintError(
                    ContractConstraintReason.INVALID_INPUT,
                    "context.offer_facts[%d] must be an OfferReferenceFacts record" % i,
                )
        object.__setattr__(self, "offer_facts", tuple(normalized_facts))
        if self.evaluation_instant:
            object.__setattr__(
                self,
                "evaluation_instant",
                _require_instant(self.evaluation_instant, "context.evaluation_instant"),
            )

    def content(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "principal_kind": self.principal_kind,
            "principal_ref": self.principal_ref,
            "beneficiary_kinds": list(self.beneficiary_kinds),
            "contract_state": self.contract_state,
            "hard_constraint_kinds": list(self.hard_constraint_kinds),
            "validity": self.validity.to_dict(),
            "accepted_offer_values": list(self.accepted_offer_values),
            "offer_facts": [f.to_dict() for f in self.offer_facts],
            "evaluation_instant": self.evaluation_instant,
        }


# ----------------------------------------------------------------------
# The decision records (auditable, canonical-serializable DATA)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ContractConstraintDecision:
    """One auditable contract-constraint decision: the decision code,
    the effective outcome, the matched rule ids (deterministic order),
    the constraint-set identity/version, the guarded action, the
    injected evaluation instant, and a deterministic detail line.  The
    decision id is content-derived over the canonical bytes (tamper
    evidence: integrity, never provenance — the harvested WORK-010
    discipline)."""

    code: str
    effect: str
    matched_rule_ids: Tuple[str, ...]
    policy_set_id: str
    policy_set_version: int
    action: str
    evaluation_instant: str
    detail: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "code",
            _require_in(self.code, ContractConstraintDecisionCode.values(), "decision.code"),
        )
        object.__setattr__(
            self,
            "effect",
            _require_in(self.effect, ContractConstraintEffect.values(), "decision.effect"),
        )
        ids = _require_tuple(self.matched_rule_ids, "decision.matched_rule_ids")
        object.__setattr__(
            self,
            "matched_rule_ids",
            tuple(
                _require_str(value, "decision.matched_rule_ids[%d]" % i)
                for i, value in enumerate(ids)
            ),
        )
        object.__setattr__(
            self,
            "policy_set_id",
            _require_str(self.policy_set_id, "decision.policy_set_id"),
        )
        object.__setattr__(
            self,
            "policy_set_version",
            _require_int(
                self.policy_set_version,
                "decision.policy_set_version",
                minimum=1,
                maximum=10**6,
            ),
        )
        object.__setattr__(
            self, "action", _require_str(self.action, "decision.action", pattern=_ACTION_PATTERN)
        )
        object.__setattr__(
            self,
            "evaluation_instant",
            _require_instant(self.evaluation_instant, "decision.evaluation_instant"),
        )
        object.__setattr__(
            self, "detail", _require_str(self.detail, "decision.detail")
        )
        _reject_secret(self.detail, "decision.detail")

    def content(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "effect": self.effect,
            "matched_rule_ids": list(self.matched_rule_ids),
            "policy_set_id": self.policy_set_id,
            "policy_set_version": self.policy_set_version,
            "action": self.action,
            "evaluation_instant": self.evaluation_instant,
            "detail": self.detail,
        }

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.content())
        data["decision_id"] = self.decision_id
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ContractConstraintDecision":
        if not isinstance(data, Mapping):
            raise ContractConstraintError(
                ContractConstraintReason.INVALID_INPUT, "decision must be a mapping"
            )
        decision = ContractConstraintDecision(
            code=data.get("code"),
            effect=data.get("effect"),
            matched_rule_ids=tuple(data.get("matched_rule_ids") or ()),
            policy_set_id=data.get("policy_set_id"),
            policy_set_version=data.get("policy_set_version"),
            action=data.get("action"),
            evaluation_instant=data.get("evaluation_instant"),
            detail=data.get("detail"),
        )
        supplied_id = data.get("decision_id")
        if supplied_id is not None and supplied_id != decision.decision_id:
            raise ContractConstraintError(
                ContractConstraintReason.ID_MISMATCH,
                "decision_id does not match the derived identity (tamper evidence)",
            )
        return decision

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.content(), "decision record")

    @property
    def decision_id(self) -> str:
        return _derive_digest(self.content(), "decision record")


@dataclass(frozen=True)
class ContractConstraintEvaluationResult:
    """The evaluation outcome envelope (the harvested WORK-010 shape):
    ``ok`` marks a decision-producing evaluation (ALLOW / DENY /
    DEFAULT_DENY); every fail-closed condition produces its own code
    with ``ok=False`` and NO decision record — never a crash, never a
    generic false.  A REQUIRE_REVIEW winner carries its deferral
    decision with ``ok=False`` (never a silent ALLOW)."""

    ok: bool
    code: str
    decision: Optional[ContractConstraintDecision] = None
    detail: str = ""


# ----------------------------------------------------------------------
# Deterministic evaluation (the pure kernel)
# ----------------------------------------------------------------------


def _rule_is_live(rule: ContractConstraintRule, instant: str) -> bool:
    """Is the rule's own validity window live at the injected instant?
    (Inclusive bounds — the harvested WORK-010 boundary convention.)"""
    if rule.valid_from and _parse_instant(instant, "instant") < _parse_instant(
        rule.valid_from, "rule.valid_from"
    ):
        return False
    if rule.valid_until and _parse_instant(instant, "instant") > _parse_instant(
        rule.valid_until, "rule.valid_until"
    ):
        return False
    return True


def _evaluate_condition(
    condition: ContractConstraintCondition, context: ContractConstraintContext
) -> Tuple[bool, str]:
    """Evaluate ONE typed condition against the composed facts.

    Returns ``(matched, verdict)`` where ``verdict`` is ``"match"`` /
    ``"missing-fact"``.  A missing fact is a NON-MATCH (fail closed) —
    never an approval; the verdict distinguishes the reason for the
    audit trail."""

    predicate = condition.predicate
    arguments = condition.arguments
    if predicate == ContractConstraintPredicateKind.PRINCIPAL_KIND:
        return (context.principal_kind == arguments.get("kind"), "match")
    if predicate == ContractConstraintPredicateKind.PRINCIPAL_REF:
        return (context.principal_ref == arguments.get("ref"), "match")
    if predicate == ContractConstraintPredicateKind.BENEFICIARY_KIND:
        kind = arguments.get("kind")
        return (kind in context.beneficiary_kinds, "match")
    if predicate == ContractConstraintPredicateKind.CONTRACT_STATE:
        return (context.contract_state == arguments.get("state"), "match")
    if predicate == ContractConstraintPredicateKind.CONSTRAINT_KIND:
        return (arguments.get("kind") in context.hard_constraint_kinds, "match")
    if predicate == ContractConstraintPredicateKind.VALIDITY_LIVE:
        if not context.evaluation_instant:
            return (False, "missing-fact")
        try:
            live = context.validity.contains(context.evaluation_instant)
        except ContractConstraintError:
            return (False, "missing-fact")
        return (live, "match")
    if predicate == ContractConstraintPredicateKind.OFFER_PROVIDER:
        usable_facts = [fact for fact in context.offer_facts if fact.usable]
        if not usable_facts and not context.offer_facts:
            return (False, "missing-fact")
        provider = arguments.get("provider")
        return (
            any(fact.provider == provider for fact in usable_facts),
            "match",
        )
    if predicate == ContractConstraintPredicateKind.OFFER_JURISDICTION:
        usable_facts = [fact for fact in context.offer_facts if fact.usable]
        if not usable_facts and not context.offer_facts:
            return (False, "missing-fact")
        jurisdiction = arguments.get("jurisdiction")
        return (
            any(jurisdiction in fact.jurisdictions for fact in usable_facts),
            "match",
        )
    # Unreachable: the predicate vocabulary is closed at construction.
    return (False, "missing-fact")


def _rule_sort_key(rule: ContractConstraintRule) -> tuple:
    """The deterministic total-order conflict key (the harvested
    WORK-010 semantics, minus the domain dimension — contract policy
    has exactly one domain: the canonical contract):

        1. specificity (descending — higher wins);
        2. priority (descending — higher wins);
        3. rule_id (ascending — the final deterministic tiebreaker).
    """
    return (-rule.specificity, -rule.priority, rule.rule_id)


def _resolve_matched_conflicts(
    matched: List[ContractConstraintRule],
) -> Tuple[Optional[str], List[str], List[str]]:
    """Resolve conflicts among matched rules deterministically (the
    harvested WORK-010 ``resolve_conflicts`` semantics):

    - unique winner at the top precedence level -> its effect;
    - equal-precedence tie containing DENY -> DENY (deny beats allow);
    - equal-precedence tie containing REQUIRE_REVIEW (and no DENY) ->
      REQUIRE_REVIEW (the caller maps it to DENY + FAIL_CLOSED — never
      a silent ALLOW);
    - multiple distinct ALLOW rules at equal precedence -> None
      (CONFLICT; the caller fails closed)."""

    trace: List[str] = []
    if not matched:
        return None, [], trace
    ordered = sorted(matched, key=_rule_sort_key)
    trace.append(
        "ordered %d matched rule(s) by (specificity desc, priority desc, rule_id asc)"
        % len(ordered)
    )
    top = ordered[0]
    top_key = (top.specificity, top.priority)
    tied = [r for r in ordered if (r.specificity, r.priority) == top_key]
    if len(tied) == 1:
        trace.append(
            "unique winner: rule %r (effect=%r, specificity=%d, priority=%d)"
            % (top.rule_id, top.effect, top.specificity, top.priority)
        )
        return top.effect, [top.rule_id], trace
    effects_in_tie = sorted({r.effect for r in tied})
    tied_ids = sorted(r.rule_id for r in tied)
    trace.append(
        "equal-precedence tie among %d rule(s): %s (effects=%s)"
        % (len(tied), tied_ids, effects_in_tie)
    )
    if ContractConstraintEffect.DENY in effects_in_tie:
        winners = sorted(r.rule_id for r in tied if r.effect == ContractConstraintEffect.DENY)
        trace.append("deny beats allow at equal precedence -> DENY (winners=%s)" % winners)
        return ContractConstraintEffect.DENY, winners, trace
    if ContractConstraintEffect.REQUIRE_REVIEW in effects_in_tie:
        winners = sorted(
            r.rule_id for r in tied if r.effect == ContractConstraintEffect.REQUIRE_REVIEW
        )
        trace.append(
            "require-review at equal precedence -> DENY+FAIL_CLOSED (no silent ALLOW; "
            "winners=%s)" % winners
        )
        return ContractConstraintEffect.REQUIRE_REVIEW, winners, trace
    trace.append(
        "multiple distinct ALLOW rules at equal precedence -> CONFLICT (fail closed; "
        "disambiguate via priority/specificity) (rules=%s)" % tied_ids
    )
    return None, tied_ids, trace


def evaluate_contract_constraints(
    constraint_set: ContractConstraintSet, context: ContractConstraintContext
) -> ContractConstraintEvaluationResult:
    """The deterministic contract-constraint evaluation entry point.

    A PURE function of (rules, composed contract/offer reference facts,
    injected instant): no wall clock, no randomness, no network, no
    mutation of any authority (LOCK-119 + the harvested WORK-010
    evaluation discipline).

    Outcome codes (never collapsed into a generic false):

    - ALLOW / DENY / DEFAULT_DENY (``ok=True``, an auditable decision
      record is produced);
    - REQUIRE_REVIEW (``ok=False`` — the deferral decision carries
      effect=deny; never a silent ALLOW);
    - POLICY_EXPIRED / POLICY_NOT_YET_VALID / CONFLICT / FAIL_CLOSED /
      INVALID_POLICY (``ok=False``, fail closed).

    Evaluation order (the harvested WORK-010 ordering):

    1. validate the evaluation input (typed fail-closed codes);
    2. reject constraint sets invalid at the injected instant;
    3. match rules (action, subject selector, typed conditions, rule
       validity window) — a missing fact is a non-match;
    4. resolve conflicts deterministically among matched rules;
    5. no applicable rule -> DEFAULT_DENY (deny-by-default; the
       missing-fact observation is recorded in the auditable detail);
    6. emit the auditable decision (matched rule ids + policy version).
    """

    def _closed(code: str, detail: str) -> ContractConstraintEvaluationResult:
        return ContractConstraintEvaluationResult(
            ok=False, code=code, decision=None, detail=detail
        )

    # 1. input integrity -------------------------------------------------
    if not isinstance(constraint_set, ContractConstraintSet):
        return _closed(
            ContractConstraintDecisionCode.INVALID_POLICY,
            "constraint set is not a ContractConstraintSet",
        )
    if not isinstance(context, ContractConstraintContext):
        return _closed(
            ContractConstraintDecisionCode.INVALID_POLICY,
            "context is not a ContractConstraintContext",
        )
    if not context.evaluation_instant:
        return _closed(
            ContractConstraintDecisionCode.FAIL_CLOSED,
            "evaluation_instant is required (no wall-clock fallback)",
        )
    _parse_instant(context.evaluation_instant, "context.evaluation_instant")

    instant = context.evaluation_instant

    # 2. policy temporal validity ---------------------------------------
    if constraint_set.valid_from and _parse_instant(
        instant, "instant"
    ) < _parse_instant(constraint_set.valid_from, "set.valid_from"):
        return _closed(
            ContractConstraintDecisionCode.POLICY_NOT_YET_VALID,
            "constraint set %r is not yet valid at %s"
            % (constraint_set.set_id, instant),
        )
    if constraint_set.valid_until and _parse_instant(
        instant, "instant"
    ) > _parse_instant(constraint_set.valid_until, "set.valid_until"):
        return _closed(
            ContractConstraintDecisionCode.POLICY_EXPIRED,
            "constraint set %r expired at %s (evaluated at %s)"
            % (constraint_set.set_id, constraint_set.valid_until, instant),
        )

    # 3. rule matching ----------------------------------------------------
    matched: List[ContractConstraintRule] = []
    missing_fact = False
    for rule in constraint_set.rules:
        if rule.action != context.action:
            continue
        if rule.subjects and context.principal_ref not in rule.subjects:
            continue
        if not _rule_is_live(rule, instant):
            continue
        all_matched = True
        for condition in rule.conditions:
            condition_matched, verdict = _evaluate_condition(condition, context)
            if not condition_matched:
                all_matched = False
                if verdict == "missing-fact":
                    missing_fact = True
                break
        if all_matched:
            matched.append(rule)

    # 4. conflict resolution ---------------------------------------------
    winning_effect, winner_ids, _trace = _resolve_matched_conflicts(matched)

    # 5. deny-by-default ---------------------------------------------------
    if winning_effect is None:
        if winner_ids:
            return _closed(
                ContractConstraintDecisionCode.CONFLICT,
                "unresolved equal-precedence conflict among rules %s; disambiguate "
                "via priority/specificity" % winner_ids,
            )
        # The harvested WORK-010 case_04 semantics, preserved case-for-case:
        # a missing fact makes the rule a NON-MATCH and the decision is
        # DEFAULT_DENY (decision-producing, effect=deny) — with the
        # missing-fact observation recorded in the auditable detail.
        detail = (
            "no applicable rule for action %r; every guarded contract action is "
            "privileged (deny-by-default)" % context.action
        )
        if missing_fact:
            detail += "; missing-fact recorded (a required reference fact was absent)"
        decision = ContractConstraintDecision(
            code=ContractConstraintDecisionCode.DEFAULT_DENY,
            effect=ContractConstraintEffect.DENY,
            matched_rule_ids=(),
            policy_set_id=constraint_set.set_id,
            policy_set_version=constraint_set.version,
            action=context.action,
            evaluation_instant=instant,
            detail=detail,
        )
        return ContractConstraintEvaluationResult(
            ok=True, code=decision.code, decision=decision, detail=decision.detail
        )

    # 6. the auditable decision --------------------------------------------
    if winning_effect == ContractConstraintEffect.REQUIRE_REVIEW:
        decision = ContractConstraintDecision(
            code=ContractConstraintDecisionCode.REQUIRE_REVIEW,
            effect=ContractConstraintEffect.DENY,
            matched_rule_ids=tuple(winner_ids),
            policy_set_id=constraint_set.set_id,
            policy_set_version=constraint_set.version,
            action=context.action,
            evaluation_instant=instant,
            detail="require-review winner treated as deferral: DENY + FAIL_CLOSED "
            "(never a silent ALLOW)",
        )
        return ContractConstraintEvaluationResult(
            ok=False,
            code=ContractConstraintDecisionCode.REQUIRE_REVIEW,
            decision=decision,
            detail=decision.detail,
        )
    if winning_effect == ContractConstraintEffect.ALLOW:
        decision = ContractConstraintDecision(
            code=ContractConstraintDecisionCode.ALLOW,
            effect=ContractConstraintEffect.ALLOW,
            matched_rule_ids=tuple(winner_ids),
            policy_set_id=constraint_set.set_id,
            policy_set_version=constraint_set.version,
            action=context.action,
            evaluation_instant=instant,
            detail="allowed by rules %s under policy %s v%d"
            % (winner_ids, constraint_set.set_id, constraint_set.version),
        )
    else:
        decision = ContractConstraintDecision(
            code=ContractConstraintDecisionCode.DENY,
            effect=ContractConstraintEffect.DENY,
            matched_rule_ids=tuple(winner_ids),
            policy_set_id=constraint_set.set_id,
            policy_set_version=constraint_set.version,
            action=context.action,
            evaluation_instant=instant,
            detail="denied by rules %s under policy %s v%d"
            % (winner_ids, constraint_set.set_id, constraint_set.version),
        )
    return ContractConstraintEvaluationResult(
        ok=True,
        code=decision.code,
        decision=decision,
        detail=decision.detail,
    )


# ----------------------------------------------------------------------
# Wire-form helpers (canonical-JSON round-trips)
# ----------------------------------------------------------------------


def contract_constraint_set_from_mapping(
    data: Mapping[str, Any],
) -> ContractConstraintSet:
    """Reconstruct a constraint set from its canonical mapping (the
    wire form).  Fail-closed: unknown members, malformed values, a
    missing issuer and secret-shaped material are rejected
    (LOCK-118/119)."""
    if not isinstance(data, Mapping):
        raise ContractConstraintError(
            ContractConstraintReason.INVALID_INPUT,
            "constraint set wire form must be a mapping",
        )
    known = {
        "set_id",
        "version",
        "rules",
        "issuer",
        "default_effect",
        "valid_from",
        "valid_until",
    }
    unknown = sorted(set(data) - known)
    if unknown:
        raise ContractConstraintError(
            ContractConstraintReason.INVALID_INPUT,
            "unknown constraint-set members: %s" % unknown,
        )
    return ContractConstraintSet.from_dict(data)


def contract_constraint_decision_canonical_bytes(
    decision: ContractConstraintDecision,
) -> bytes:
    """The canonical bytes of one decision (byte-stable across runs and
    processes; the digest basis)."""
    if not isinstance(decision, ContractConstraintDecision):
        raise ContractConstraintError(
            ContractConstraintReason.INVALID_INPUT,
            "contract_constraint_decision_canonical_bytes requires a "
            "ContractConstraintDecision",
        )
    return decision.canonical_bytes()


__all__ = [
    "ContractConstraintCondition",
    "ContractConstraintDecision",
    "ContractConstraintDecisionCode",
    "ContractConstraintEffect",
    "ContractConstraintError",
    "ContractConstraintEvaluationResult",
    "ContractConstraintReason",
    "ContractConstraintRule",
    "ContractConstraintSet",
    "ContractConstraintPredicateKind",
    "ContractConstraintContext",
    "OfferReferenceFacts",
    "ValidityWindow",
    "contract_constraint_decision_canonical_bytes",
    "contract_constraint_set_from_mapping",
    "evaluate_contract_constraints",
]
