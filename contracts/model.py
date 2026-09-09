"""ADCOS connectivity-contract domain model (M002 — Connectivity Contract Core).

The canonical durable object of Architecture 1.1: ``ConnectivityContract``
is THE authority for acquired connectivity (LOCK-101). A ``Path``,
``Session``, ``Tunnel``, ``Bearer``, ``AdapterBinding``, ``eSIM``, adapter
or provider record never becomes a second contract authority (LOCK-117):
execution artifacts ride as opaque references only, and no construction
path accepts an execution artifact as an authority input.

Authority boundaries (the layering contract, frozen 1.1 sections 3-13):

- **Intent stays technology-neutral (LOCK-102).** Normalized requirements
  enter the contract as opaque typed references; M002 never interprets
  intent semantics and never selects implementation mechanisms.
- **Offers stay M003.** Accepted offer references are opaque, provenance-
  carrying records; M002 stores them, never evaluates them.
- **Eligibility/policy stays M004.** The contract records hard constraints;
  it never evaluates policy and never confers eligibility.
- **Evidence/assurance stays M005.** Assurance obligations are opaque
  references; assurance evaluation results enter as recorded commands.
- **Execution planning stays M006.** Permitted execution scope is an opaque
  reference set; the contract never composes execution plans.
- **Adapters stay M007 (LOCK-110).** Provider-native SDK types never enter
  this model; provider material is opaque data.
- **Usage/commercial stays M009 (LOCK-113).** Usage and pricing terms are
  opaque commercial references; the contract never moves money and never
  hosts payment authority.
- **Provenance is first-class (LOCK-118).** Externally asserted commitments
  carry issuer and provenance.
- **Secrets never enter (LOCK-119).** Secret-looking material is rejected
  at construction and deserialization time.

Lifecycle (frozen 1.1 §11 commercial reference lifecycle plus the §9
assurance-aware terminal set):

    INTENT -> OFFER_SELECTED -> CONTRACT_ACTIVE -> EXECUTION_ACTIVE
            -> DELIVERY -> ASSURED -> USAGE_FINAL
            -> SETTLEMENT_PENDING -> SETTLED

with the explicit non-terminal degraded state (§9) and the terminal states
SETTLED, TERMINATED (deliberate), EXPIRED (lease/validity expiry) and
FAILED. Hard constraints are IMMUTABLE from construction onward
(LOCK-108: no silent weakening — there is no command that mutates them;
renegotiation is explicit supersession, a new contract).

Determinism: content-derived ids over canonical JSON (``sha256:`` +
hex digest); a supplied id must match the derived value (tamper evidence
at construction AND deserialization); injected RFC 3339 UTC instants
only; no wall clock, no randomness, no UUIDs, no network; sorted
iteration everywhere (PYTHONHASHSEED-safe); fail-closed errors with
stable machine-readable codes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

# ----------------------------------------------------------------------
# Error and reason vocabulary (contract-local; adding a value is a
# deliberate vocabulary change on this M002 surface)
# ----------------------------------------------------------------------


class ContractError(ValueError):
    """Fail-closed contract error with a stable machine-readable ``code``
    and deterministic ``detail`` (secret material is never echoed)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ContractReason:
    # lifecycle successes (one per accepted command kind)
    CREATED = "created"
    OFFERS_SELECTED = "offers-selected"
    ACTIVATED = "activated"
    EXECUTION_ACTIVATED = "execution-activated"
    DELIVERED = "delivered"
    ASSURED = "assured"
    DEGRADED = "degraded-recorded"
    USAGE_FINAL = "usage-final"
    SETTLEMENT_PENDING = "settlement-pending"
    SETTLED = "settled"
    TERMINATED = "terminated"
    EXPIRED = "expired"
    FAILED = "failed"
    ARTIFACT_BOUND = "artifact-bound"
    LEASE_GRANTED = "lease-granted"
    LEASE_RENEWED = "lease-renewed"
    LEASE_REVOKED = "lease-revoked"

    # fail-closed codes
    INVALID_INPUT = "invalid-input"
    INVALID_STATE = "invalid-state"
    INVALID_TRANSITION = "invalid-transition"
    UNKNOWN_CONTRACT = "unknown-contract"
    CONTRACT_TERMINAL = "contract-terminal"
    CONSTRAINT_IMMUTABLE = "constraint-immutable"
    NOT_YET_VALID = "not-yet-valid"
    EXPIRED = "expired"
    TEMPORAL_INVALID = "temporal-invalid"
    ID_MISMATCH = "id-mismatch"
    SECRET_REJECTED = "secret-rejected"
    VOCABULARY = "vocabulary"

    # journal discipline (the W057/W052 merge semantics)
    DUPLICATE = "duplicate"
    REPLAY_STALE = "replay-stale"
    SEQUENCE_CONFLICT = "sequence-conflict"
    SEQUENCE_GAP = "sequence-gap"
    JOURNAL_TAMPER = "journal-tamper"


# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------

PRINCIPAL_KINDS: Tuple[str, ...] = (
    "USER",
    "DEVICE",
    "APPLICATION",
    "ORGANIZATION",
    "GOVERNMENT",
    "NGO",
    "NETWORK_OPERATOR",
    "SERVICE",
)

# The contract-level lifecycle states: the frozen 1.1 §11 reference
# lifecycle plus the §9 explicit degraded state and the terminal set.
CONTRACT_STATES: Tuple[str, ...] = (
    "INTENT",
    "OFFER_SELECTED",
    "CONTRACT_ACTIVE",
    "EXECUTION_ACTIVE",
    "DELIVERY",
    "ASSURED",
    "DEGRADED",
    "USAGE_FINAL",
    "SETTLEMENT_PENDING",
    "SETTLED",
    "TERMINATED",
    "EXPIRED",
    "FAILED",
)

TERMINAL_STATES: Tuple[str, ...] = ("SETTLED", "TERMINATED", "EXPIRED", "FAILED")

# Legal contract-state transitions. Supersession (renegotiation) is NOT a
# transition: it is a new contract referencing the superseded one.
CONTRACT_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "INTENT": ("OFFER_SELECTED", "TERMINATED", "FAILED"),
    "OFFER_SELECTED": ("CONTRACT_ACTIVE", "TERMINATED", "FAILED"),
    "CONTRACT_ACTIVE": ("EXECUTION_ACTIVE", "TERMINATED", "EXPIRED", "FAILED"),
    "EXECUTION_ACTIVE": ("DELIVERY", "DEGRADED", "TERMINATED", "EXPIRED", "FAILED"),
    "DELIVERY": ("ASSURED", "DEGRADED", "TERMINATED", "EXPIRED", "FAILED"),
    "ASSURED": ("USAGE_FINAL", "DEGRADED", "TERMINATED", "EXPIRED", "FAILED"),
    "DEGRADED": ("ASSURED", "TERMINATED", "EXPIRED", "FAILED"),
    "USAGE_FINAL": ("SETTLEMENT_PENDING", "TERMINATED", "FAILED"),
    "SETTLEMENT_PENDING": ("SETTLED", "TERMINATED", "FAILED"),
}

# Opaque reference kinds. Each names what the reference points at OUTSIDE
# the contract authority (LOCK-117: references, never authorities).
REFERENCE_KINDS: Tuple[str, ...] = (
    "intent-requirements",       # normalized requirements snapshot (intent authority)
    "offer",                     # accepted provider offer (M003)
    "service-property",          # committed service property record
    "usage-pricing-terms",       # commercial terms / settlement reference (M009)
    "assurance-obligation",      # typed obligation (M005)
    "execution-scope",           # permitted execution scope (M006)
    "compensation",              # termination compensation rule reference
    "signature",                 # signature over the contract record
    "execution-artifact",        # Path/Session/Tunnel/Bearer/eSIM/adapter data
    "decision",                  # governance/eligibility/assurance decision reference
    "superseded-contract",       # explicit renegotiation chain link
)

# Hard-constraint kinds (the M002-local vocabulary; LOCK-108 makes the
# constraint set immutable: no command mutates it, ever).
CONSTRAINT_KINDS: Tuple[str, ...] = (
    "latency-bound",
    "throughput-floor",
    "availability-floor",
    "loss-bound",
    "jitter-bound",
    "isolation",
    "jurisdiction",
    "security-level",
    "provider-trust",
    "evidence-obligation",
    "geography",
    "priority",
)

# Termination condition kinds (frozen 1.1 §3 termination rules vocabulary).
TERMINATION_CONDITION_KINDS: Tuple[str, ...] = (
    "principal-requested",
    "validity-expired",
    "constraint-violated",
    "provider-initiated",
    "policy-directed",
    "compensation-triggered",
)

# Assurance evaluation states recorded from the M005 authority (the frozen
# 1.1 §9 vocabulary: compliant, degraded, violated, unknown/stale).
ASSURANCE_STATES: Tuple[str, ...] = (
    "compliant",
    "degraded",
    "violated",
    "unknown-stale",
)

# Lease lifecycle states (a lease is the time-bounded right to use the
# acquired connectivity UNDER a contract; the contract stays the authority).
LEASE_STATES: Tuple[str, ...] = (
    "granted",
    "active",
    "expired",
    "revoked",
    "renewed",
)

_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")
_SECRET_NAME_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$")

_ID_NAMESPACE = "adc-os-connectivity-contract"
_LEASE_NAMESPACE = "adc-os-connectivity-lease"


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise ContractError(
            ContractReason.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_id(namespace: str, document: Mapping[str, Any], label: str) -> str:
    payload = dict(document)
    payload["namespace"] = namespace
    return "sha256:" + hashlib.sha256(_canonical_bytes(payload, label)).hexdigest()


def _require_str(value: object, label: str, *, pattern: Optional[re.Pattern] = None) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(
            ContractReason.INVALID_INPUT, "%s must be a non-empty string" % label
        )
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ContractError(
            ContractReason.INVALID_INPUT, "%s has an invalid format: %r" % (label, value)
        )
    _reject_secret(value, label)
    return value


def _reject_secret(value: object, label: str) -> None:
    """LOCK-119 guard: secret-looking material never enters contract data."""
    if _SECRET_NAME_PATTERN.search(label):
        raise ContractError(
            ContractReason.SECRET_REJECTED,
            "%s looks like secret material; secrets never enter contract data" % label,
        )
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.match(value):
        raise ContractError(
            ContractReason.SECRET_REJECTED,
            "%s carries a secret-shaped value; secrets never enter contract data" % label,
        )


def _require_in(value: object, vocabulary: Sequence[str], label: str) -> str:
    if value not in vocabulary:
        raise ContractError(
            ContractReason.VOCABULARY,
            "%s must be one of %s (found %r)" % (label, ", ".join(vocabulary), value),
        )
    return str(value)


def _require_tuple(value: object, label: str, *, min_len: int = 0) -> Tuple[Any, ...]:
    if isinstance(value, tuple):
        items = value
    elif isinstance(value, list):
        items = tuple(value)
    else:
        raise ContractError(
            ContractReason.INVALID_INPUT, "%s must be a sequence" % label
        )
    if len(items) < min_len:
        raise ContractError(
            ContractReason.INVALID_INPUT, "%s requires at least %d entries" % (label, min_len)
        )
    return items


def _require_instant(value: object, label: str) -> str:
    try:
        parse_instant(value)
    except TemporalError as error:
        raise ContractError(
            ContractReason.TEMPORAL_INVALID, "%s is invalid: %s" % (label, error)
        ) from None
    return str(value)


def _check_mapping_str_scalar(params: Mapping[str, Any], label: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key in sorted(params):
        if not isinstance(key, str) or not key:
            raise ContractError(
                ContractReason.INVALID_INPUT, "%s keys must be non-empty strings" % label
            )
        value = params[key]
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ContractError(
                ContractReason.INVALID_INPUT,
                "%s[%r] must be a scalar (str/int/float)" % (label, key),
            )
        _reject_secret(value, "%s[%r]" % (label, key))
        result[key] = value
    return result


# ----------------------------------------------------------------------
# Provenance (LOCK-118: issuer + decision references, always)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Provenance:
    """Who asserted the material and under which decisions."""

    issuer: str
    decision_refs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issuer", _require_str(self.issuer, "provenance.issuer"))
        refs = _require_tuple(self.decision_refs, "provenance.decision_refs")
        normalized = tuple(
            _require_str(ref, "provenance.decision_refs[%d]" % i, pattern=_REF_VALUE_PATTERN)
            for i, ref in enumerate(refs)
        )
        object.__setattr__(self, "decision_refs", normalized)

    def to_dict(self) -> Dict[str, Any]:
        return {"issuer": self.issuer, "decision_refs": list(self.decision_refs)}

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "Provenance":
        if not isinstance(data, Mapping):
            raise ContractError(ContractReason.INVALID_INPUT, "provenance must be a mapping")
        return Provenance(
            issuer=data.get("issuer"),
            decision_refs=tuple(data.get("decision_refs") or ()),
        )


# ----------------------------------------------------------------------
# Opaque references (LOCK-117: execution artifacts and provider material
# ride as DATA, never as authority)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class OpaqueReference:
    """A typed, provenance-carrying opaque reference to material owned by
    another authority. The contract stores the reference; it never
    interprets, evaluates, or authorizes through it."""

    ref_kind: str
    value: str
    provenance: Optional[Provenance] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "ref_kind", _require_in(self.ref_kind, REFERENCE_KINDS, "reference.ref_kind")
        )
        object.__setattr__(
            self, "value", _require_str(self.value, "reference.value", pattern=_REF_VALUE_PATTERN)
        )
        if self.provenance is not None and not isinstance(self.provenance, Provenance):
            raise ContractError(
                ContractReason.INVALID_INPUT, "reference.provenance must be a Provenance record"
            )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"ref_kind": self.ref_kind, "value": self.value}
        if self.provenance is not None:
            data["provenance"] = self.provenance.to_dict()
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "OpaqueReference":
        if not isinstance(data, Mapping):
            raise ContractError(ContractReason.INVALID_INPUT, "reference must be a mapping")
        provenance = data.get("provenance")
        return OpaqueReference(
            ref_kind=data.get("ref_kind"),
            value=data.get("value"),
            provenance=Provenance.from_dict(provenance) if provenance is not None else None,
        )


# ----------------------------------------------------------------------
# Principal and beneficiary scope (frozen 1.1 §4)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ConnectivityPrincipal:
    """The contracting principal. LOCK-103: an authorized principal (e.g.,
    an APPLICATION) may purchase or sponsor connectivity for bounded
    beneficiaries; purchasing authority never confers authority over
    application data, identities, messages, content or provider topology
    (this model carries references only, so that boundary is structural)."""

    principal_kind: str
    principal_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "principal_kind",
            _require_in(self.principal_kind, PRINCIPAL_KINDS, "principal.principal_kind"),
        )
        object.__setattr__(
            self,
            "principal_ref",
            _require_str(self.principal_ref, "principal.principal_ref", pattern=_REF_VALUE_PATTERN),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "principal_kind": self.principal_kind,
            "principal_ref": self.principal_ref,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ConnectivityPrincipal":
        if not isinstance(data, Mapping):
            raise ContractError(ContractReason.INVALID_INPUT, "principal must be a mapping")
        return ConnectivityPrincipal(
            principal_kind=data.get("principal_kind"),
            principal_ref=data.get("principal_ref"),
        )


@dataclass(frozen=True)
class BeneficiaryScope:
    """A bounded beneficiary of sponsored connectivity (LOCK-103)."""

    beneficiary_kind: str
    beneficiary_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "beneficiary_kind",
            _require_in(self.beneficiary_kind, PRINCIPAL_KINDS, "beneficiary.beneficiary_kind"),
        )
        object.__setattr__(
            self,
            "beneficiary_ref",
            _require_str(
                self.beneficiary_ref, "beneficiary.beneficiary_ref", pattern=_REF_VALUE_PATTERN
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "beneficiary_kind": self.beneficiary_kind,
            "beneficiary_ref": self.beneficiary_ref,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "BeneficiaryScope":
        if not isinstance(data, Mapping):
            raise ContractError(ContractReason.INVALID_INPUT, "beneficiary must be a mapping")
        return BeneficiaryScope(
            beneficiary_kind=data.get("beneficiary_kind"),
            beneficiary_ref=data.get("beneficiary_ref"),
        )


# ----------------------------------------------------------------------
# Hard constraints (LOCK-108: immutable, never weakened)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class HardConstraint:
    """A hard contract constraint. The constraint set is frozen at
    construction; there is no command that mutates it, and replanning may
    never silently weaken it (LOCK-108 is enforced structurally: the
    lifecycle command vocabulary has no constraint mutation path)."""

    kind: str
    params: Mapping[str, Any] = field(default_factory=dict)
    provenance: Optional[Provenance] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _require_in(self.kind, CONSTRAINT_KINDS, "constraint.kind"))
        params = self.params if isinstance(self.params, Mapping) else {}
        object.__setattr__(self, "params", _check_mapping_str_scalar(params, "constraint.params"))
        if self.provenance is not None and not isinstance(self.provenance, Provenance):
            raise ContractError(
                ContractReason.INVALID_INPUT, "constraint.provenance must be a Provenance record"
            )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"kind": self.kind, "params": dict(self.params)}
        if self.provenance is not None:
            data["provenance"] = self.provenance.to_dict()
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "HardConstraint":
        if not isinstance(data, Mapping):
            raise ContractError(ContractReason.INVALID_INPUT, "constraint must be a mapping")
        provenance = data.get("provenance")
        return HardConstraint(
            kind=data.get("kind"),
            params=data.get("params") or {},
            provenance=Provenance.from_dict(provenance) if provenance is not None else None,
        )


# ----------------------------------------------------------------------
# Validity interval (lease/expiry semantics over injected instants)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ValidityInterval:
    """The contract validity window. All temporal comparisons use injected
    instants (no wall clock)."""

    not_before: str
    not_after: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "not_before", _require_instant(self.not_before, "validity.not_before")
        )
        object.__setattr__(
            self, "not_after", _require_instant(self.not_after, "validity.not_after")
        )
        if parse_instant(self.not_before) >= parse_instant(self.not_after):
            raise ContractError(
                ContractReason.TEMPORAL_INVALID,
                "validity.not_before must precede validity.not_after",
            )

    def contains(self, instant: str) -> bool:
        parsed = parse_instant(instant)
        return parse_instant(self.not_before) <= parsed <= parse_instant(self.not_after)

    def is_expired(self, instant: str) -> bool:
        return parse_instant(instant) > parse_instant(self.not_after)

    def is_not_yet_valid(self, instant: str) -> bool:
        return parse_instant(instant) < parse_instant(self.not_before)

    def to_dict(self) -> Dict[str, Any]:
        return {"not_before": self.not_before, "not_after": self.not_after}

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ValidityInterval":
        if not isinstance(data, Mapping):
            raise ContractError(ContractReason.INVALID_INPUT, "validity must be a mapping")
        return ValidityInterval(
            not_before=data.get("not_before"), not_after=data.get("not_after")
        )


# ----------------------------------------------------------------------
# Termination and compensation rules (frozen 1.1 §3)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class TerminationRules:
    """When and how the contract may terminate deliberately, and the
    compensation reference (LOCK-113: compensation/settlement is an
    external commercial reference, never payment authority here)."""

    conditions: Tuple[str, ...]
    compensation: OpaqueReference

    def __post_init__(self) -> None:
        conditions = _require_tuple(self.conditions, "termination.conditions", min_len=1)
        normalized = tuple(
            _require_in(cond, TERMINATION_CONDITION_KINDS, "termination.conditions[%d]" % i)
            for i, cond in enumerate(conditions)
        )
        object.__setattr__(self, "conditions", normalized)
        if not isinstance(self.compensation, OpaqueReference):
            raise ContractError(
                ContractReason.INVALID_INPUT,
                "termination.compensation must be an OpaqueReference record",
            )
        if self.compensation.ref_kind != "compensation":
            raise ContractError(
                ContractReason.VOCABULARY,
                "termination.compensation must use the compensation reference kind",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conditions": list(self.conditions),
            "compensation": self.compensation.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "TerminationRules":
        if not isinstance(data, Mapping):
            raise ContractError(ContractReason.INVALID_INPUT, "termination must be a mapping")
        return TerminationRules(
            conditions=tuple(data.get("conditions") or ()),
            compensation=OpaqueReference.from_dict(data.get("compensation")),
        )


# ----------------------------------------------------------------------
# The canonical durable object (frozen 1.1 §3 field set)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ConnectivityContract:
    """The canonical durable object for acquired connectivity (LOCK-101).

    Field set per frozen Architecture 1.1 section 3: contract identity;
    principal and beneficiary scope; normalized requirements; accepted
    offer references; hard constraints; committed service properties;
    validity interval; usage and pricing terms; assurance obligations;
    permitted execution scope; termination and compensation rules;
    provenance; and signature references.

    ``execution_artifacts`` carries LOCK-117 data: opaque references to
    Paths/Sessions/Tunnels/Bearers/eSIMs/adapter bindings that realize the
    contract. They are DATA; they never authorize anything, and the store
    provides no path that turns an artifact into an authority.

    ``state`` is the contract-level lifecycle position; the fold
    (contracts.store) is the only writer of state transitions.
    """

    contract_id: str
    state: str
    principal: ConnectivityPrincipal
    beneficiaries: Tuple[BeneficiaryScope, ...]
    requirements: Tuple[OpaqueReference, ...]
    accepted_offers: Tuple[OpaqueReference, ...]
    hard_constraints: Tuple[HardConstraint, ...]
    service_properties: Tuple[OpaqueReference, ...]
    validity: ValidityInterval
    usage_pricing_terms: Optional[OpaqueReference]
    assurance_obligations: Tuple[OpaqueReference, ...]
    execution_scope: Tuple[OpaqueReference, ...]
    termination: TerminationRules
    provenance: Provenance
    signature_refs: Tuple[OpaqueReference, ...]
    execution_artifacts: Tuple[OpaqueReference, ...] = ()
    superseded_contract: Optional[OpaqueReference] = None
    termination_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.contract_id, str) or _ID_PATTERN.fullmatch(self.contract_id) is None:
            raise ContractError(
                ContractReason.INVALID_INPUT,
                "contract.contract_id must be the content-derived identity (sha256:...)",
            )
        object.__setattr__(self, "state", _require_in(self.state, CONTRACT_STATES, "contract.state"))
        if not isinstance(self.principal, ConnectivityPrincipal):
            raise ContractError(
                ContractReason.INVALID_INPUT, "contract.principal must be a ConnectivityPrincipal"
            )
        beneficiaries = _require_tuple(self.beneficiaries, "contract.beneficiaries")
        object.__setattr__(
            self,
            "beneficiaries",
            tuple(
                item if isinstance(item, BeneficiaryScope) else BeneficiaryScope.from_dict(item)
                for item in beneficiaries
            ),
        )
        for field_name, ref_kind in (
            ("requirements", "intent-requirements"),
            ("accepted_offers", "offer"),
            ("service_properties", "service-property"),
            ("assurance_obligations", "assurance-obligation"),
            ("execution_scope", "execution-scope"),
            ("signature_refs", "signature"),
            ("execution_artifacts", "execution-artifact"),
        ):
            items = _require_tuple(getattr(self, field_name), "contract.%s" % field_name)
            normalized = []
            for i, item in enumerate(items):
                if not isinstance(item, OpaqueReference):
                    raise ContractError(
                        ContractReason.INVALID_INPUT,
                        "contract.%s[%d] must be an OpaqueReference" % (field_name, i),
                    )
                if item.ref_kind != ref_kind:
                    raise ContractError(
                        ContractReason.VOCABULARY,
                        "contract.%s[%d] must use the %s reference kind (found %s)"
                        % (field_name, i, ref_kind, item.ref_kind),
                    )
                normalized.append(item)
            object.__setattr__(self, field_name, tuple(normalized))
        if not self.requirements:
            raise ContractError(
                ContractReason.INVALID_INPUT,
                "contract.requirements requires at least one normalized-requirements reference",
            )
        constraints = _require_tuple(self.hard_constraints, "contract.hard_constraints")
        object.__setattr__(
            self,
            "hard_constraints",
            tuple(
                item if isinstance(item, HardConstraint) else HardConstraint.from_dict(item)
                for item in constraints
            ),
        )
        if not isinstance(self.validity, ValidityInterval):
            raise ContractError(
                ContractReason.INVALID_INPUT, "contract.validity must be a ValidityInterval"
            )
        if self.usage_pricing_terms is not None:
            if not isinstance(self.usage_pricing_terms, OpaqueReference):
                raise ContractError(
                    ContractReason.INVALID_INPUT,
                    "contract.usage_pricing_terms must be an OpaqueReference",
                )
            if self.usage_pricing_terms.ref_kind != "usage-pricing-terms":
                raise ContractError(
                    ContractReason.VOCABULARY,
                    "contract.usage_pricing_terms must use the usage-pricing-terms reference kind",
                )
        if not isinstance(self.termination, TerminationRules):
            raise ContractError(
                ContractReason.INVALID_INPUT, "contract.termination must be TerminationRules"
            )
        if not isinstance(self.provenance, Provenance):
            raise ContractError(
                ContractReason.INVALID_INPUT, "contract.provenance must be a Provenance record"
            )
        if self.superseded_contract is not None and (
            not isinstance(self.superseded_contract, OpaqueReference)
            or self.superseded_contract.ref_kind != "superseded-contract"
        ):
            raise ContractError(
                ContractReason.VOCABULARY,
                "contract.superseded_contract must use the superseded-contract reference kind",
            )
        # tamper evidence: the id must equal the content-derived identity
        # over the creation core
        expected = _derive_contract_id_from_core(
            self.principal,
            self.beneficiaries,
            self.requirements,
            self.hard_constraints,
            self.validity,
        )
        if self.contract_id != expected:
            raise ContractError(
                ContractReason.ID_MISMATCH,
                "contract_id does not match the derived identity (tamper evidence)",
            )

    # -- lifecycle helpers ------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def hard_constraint_fingerprint(self) -> str:
        """A digest over the immutable constraint set (LOCK-108 evidence).

        Replanning/failover (M008) and any later consumer can prove the
        constraint set was not weakened by comparing fingerprints.
        """
        document = [constraint.to_dict() for constraint in self.hard_constraints]
        return "sha256:" + hashlib.sha256(
            _canonical_bytes({"constraints": document}, "hard constraints")
        ).hexdigest()

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "contract_id": self.contract_id,
            "state": self.state,
            "principal": self.principal.to_dict(),
            "beneficiaries": [b.to_dict() for b in self.beneficiaries],
            "requirements": [r.to_dict() for r in self.requirements],
            "accepted_offers": [o.to_dict() for o in self.accepted_offers],
            "hard_constraints": [c.to_dict() for c in self.hard_constraints],
            "service_properties": [p.to_dict() for p in self.service_properties],
            "validity": self.validity.to_dict(),
            "usage_pricing_terms": (
                self.usage_pricing_terms.to_dict() if self.usage_pricing_terms is not None else None
            ),
            "assurance_obligations": [o.to_dict() for o in self.assurance_obligations],
            "execution_scope": [s.to_dict() for s in self.execution_scope],
            "termination": self.termination.to_dict(),
            "provenance": self.provenance.to_dict(),
            "signature_refs": [s.to_dict() for s in self.signature_refs],
            "execution_artifacts": [a.to_dict() for a in self.execution_artifacts],
        }
        if self.superseded_contract is not None:
            data["superseded_contract"] = self.superseded_contract.to_dict()
        if self.termination_reason is not None:
            data["termination_reason"] = self.termination_reason
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ConnectivityContract":
        if not isinstance(data, Mapping):
            raise ContractError(ContractReason.INVALID_INPUT, "contract must be a mapping")
        usage_terms = data.get("usage_pricing_terms")
        superseded = data.get("superseded_contract")
        return ConnectivityContract(
            contract_id=data.get("contract_id"),
            state=data.get("state"),
            principal=ConnectivityPrincipal.from_dict(data.get("principal")),
            beneficiaries=tuple(
                BeneficiaryScope.from_dict(b) for b in data.get("beneficiaries") or ()
            ),
            requirements=tuple(
                OpaqueReference.from_dict(r) for r in data.get("requirements") or ()
            ),
            accepted_offers=tuple(
                OpaqueReference.from_dict(o) for o in data.get("accepted_offers") or ()
            ),
            hard_constraints=tuple(
                HardConstraint.from_dict(c) for c in data.get("hard_constraints") or ()
            ),
            service_properties=tuple(
                OpaqueReference.from_dict(p) for p in data.get("service_properties") or ()
            ),
            validity=ValidityInterval.from_dict(data.get("validity")),
            usage_pricing_terms=(
                OpaqueReference.from_dict(usage_terms) if usage_terms is not None else None
            ),
            assurance_obligations=tuple(
                OpaqueReference.from_dict(o) for o in data.get("assurance_obligations") or ()
            ),
            execution_scope=tuple(
                OpaqueReference.from_dict(s) for s in data.get("execution_scope") or ()
            ),
            termination=TerminationRules.from_dict(data.get("termination")),
            provenance=Provenance.from_dict(data.get("provenance")),
            signature_refs=tuple(
                OpaqueReference.from_dict(s) for s in data.get("signature_refs") or ()
            ),
            execution_artifacts=tuple(
                OpaqueReference.from_dict(a) for a in data.get("execution_artifacts") or ()
            ),
            superseded_contract=(
                OpaqueReference.from_dict(superseded) if superseded is not None else None
            ),
            termination_reason=data.get("termination_reason"),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "contract record")


def _derive_contract_id_from_core(
    principal: ConnectivityPrincipal,
    beneficiaries: Sequence[BeneficiaryScope],
    requirements: Sequence[OpaqueReference],
    hard_constraints: Sequence[HardConstraint],
    validity: ValidityInterval,
) -> str:
    """Content-derived contract identity over the creation core.

    The id document covers the principal/beneficiary scope, normalized
    requirements, hard constraints and validity interval — the fields
    that make the contract THIS contract. The identity is stable across
    lifecycle evolution (state, offers, artifacts evolve; identity does
    not).
    """
    document = {
        "principal": principal.to_dict(),
        "beneficiaries": [b.to_dict() for b in beneficiaries],
        "requirements": [r.to_dict() for r in requirements],
        "hard_constraints": [c.to_dict() for c in hard_constraints],
        "validity": validity.to_dict(),
    }
    return _derive_id(_ID_NAMESPACE, document, "contract id document")


def derive_contract_id(contract: ConnectivityContract) -> str:
    """Re-derive the identity of a constructed contract (tamper check)."""
    return _derive_contract_id_from_core(
        contract.principal,
        contract.beneficiaries,
        contract.requirements,
        contract.hard_constraints,
        contract.validity,
    )


# ----------------------------------------------------------------------
# The contract lease (time-bounded right to use, contract-scoped)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ContractLease:
    """A contract-scoped lease: the time-bounded right to use the acquired
    connectivity UNDER a contract. The lease references the contract; the
    contract is the authority (LOCK-117 — a lease is never a second
    authority). Renewal creates a NEW lease record; it never mutates an
    existing one (audit trail)."""

    lease_id: str
    contract_id: str
    state: str
    granted_at: str
    not_before: str
    not_after: str
    revocation_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.lease_id, str) or _ID_PATTERN.fullmatch(self.lease_id) is None:
            raise ContractError(
                ContractReason.INVALID_INPUT,
                "lease.lease_id must be the content-derived identity (sha256:...)",
            )
        if not isinstance(self.contract_id, str) or _ID_PATTERN.fullmatch(self.contract_id) is None:
            raise ContractError(
                ContractReason.INVALID_INPUT,
                "lease.contract_id must be a contract identity (sha256:...)",
            )
        object.__setattr__(self, "state", _require_in(self.state, LEASE_STATES, "lease.state"))
        object.__setattr__(self, "granted_at", _require_instant(self.granted_at, "lease.granted_at"))
        object.__setattr__(self, "not_before", _require_instant(self.not_before, "lease.not_before"))
        object.__setattr__(self, "not_after", _require_instant(self.not_after, "lease.not_after"))
        if parse_instant(self.not_before) >= parse_instant(self.not_after):
            raise ContractError(
                ContractReason.TEMPORAL_INVALID, "lease.not_before must precede lease.not_after"
            )
        if self.revocation_reason is not None:
            object.__setattr__(
                self,
                "revocation_reason",
                _require_str(self.revocation_reason, "lease.revocation_reason"),
            )
        expected = _derive_lease_id_from_core(
            self.contract_id, self.granted_at, self.not_before, self.not_after
        )
        if self.lease_id != expected:
            raise ContractError(
                ContractReason.ID_MISMATCH,
                "lease_id does not match the derived identity (tamper evidence)",
            )

    def is_expired(self, instant: str) -> bool:
        return parse_instant(instant) > parse_instant(self.not_after)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "lease_id": self.lease_id,
            "contract_id": self.contract_id,
            "state": self.state,
            "granted_at": self.granted_at,
            "not_before": self.not_before,
            "not_after": self.not_after,
        }
        if self.revocation_reason is not None:
            data["revocation_reason"] = self.revocation_reason
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ContractLease":
        if not isinstance(data, Mapping):
            raise ContractError(ContractReason.INVALID_INPUT, "lease must be a mapping")
        return ContractLease(
            lease_id=data.get("lease_id"),
            contract_id=data.get("contract_id"),
            state=data.get("state"),
            granted_at=data.get("granted_at"),
            not_before=data.get("not_before"),
            not_after=data.get("not_after"),
            revocation_reason=data.get("revocation_reason"),
        )


def _derive_lease_id_from_core(
    contract_id: str, granted_at: str, not_before: str, not_after: str
) -> str:
    document = {
        "contract_id": contract_id,
        "granted_at": granted_at,
        "not_before": not_before,
        "not_after": not_after,
    }
    return _derive_id(_LEASE_NAMESPACE, document, "lease id document")


def build_lease(
    contract_id: str,
    state: str,
    granted_at: str,
    not_before: str,
    not_after: str,
    revocation_reason: Optional[str] = None,
) -> ContractLease:
    """Build a lease with its content-derived identity."""
    lease_id = _derive_lease_id_from_core(contract_id, granted_at, not_before, not_after)
    return ContractLease(
        lease_id=lease_id,
        contract_id=contract_id,
        state=state,
        granted_at=granted_at,
        not_before=not_before,
        not_after=not_after,
        revocation_reason=revocation_reason,
    )


# ----------------------------------------------------------------------
# Lifecycle commands (the fold input vocabulary; the store is the writer)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class CreateContract:
    """Create a contract in INTENT state from the canonical creation core."""

    principal: ConnectivityPrincipal
    beneficiaries: Tuple[BeneficiaryScope, ...]
    requirements: Tuple[OpaqueReference, ...]
    hard_constraints: Tuple[HardConstraint, ...]
    validity: ValidityInterval
    service_properties: Tuple[OpaqueReference, ...]
    usage_pricing_terms: Optional[OpaqueReference]
    assurance_obligations: Tuple[OpaqueReference, ...]
    execution_scope: Tuple[OpaqueReference, ...]
    termination: TerminationRules
    provenance: Provenance
    superseded_contract: Optional[OpaqueReference] = None

    def __post_init__(self) -> None:
        # fail-fast command validation (the deep field validation happens
        # in ConnectivityContract construction; this catches the empty core)
        if not _require_tuple(self.requirements, "create.requirements"):
            raise ContractError(
                ContractReason.INVALID_INPUT,
                "create.requirements requires at least one normalized-requirements reference",
            )
        if not isinstance(self.validity, ValidityInterval):
            raise ContractError(
                ContractReason.INVALID_INPUT, "create.validity must be a ValidityInterval"
            )
        if not isinstance(self.termination, TerminationRules):
            raise ContractError(
                ContractReason.INVALID_INPUT, "create.termination must be TerminationRules"
            )
        if not isinstance(self.principal, ConnectivityPrincipal):
            raise ContractError(
                ContractReason.INVALID_INPUT, "create.principal must be a ConnectivityPrincipal"
            )
        if not isinstance(self.provenance, Provenance):
            raise ContractError(
                ContractReason.INVALID_INPUT, "create.provenance must be a Provenance record"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": "create",
            "principal": self.principal.to_dict(),
            "beneficiaries": [b.to_dict() for b in self.beneficiaries],
            "requirements": [r.to_dict() for r in self.requirements],
            "hard_constraints": [c.to_dict() for c in self.hard_constraints],
            "validity": self.validity.to_dict(),
            "service_properties": [p.to_dict() for p in self.service_properties],
            "usage_pricing_terms": (
                self.usage_pricing_terms.to_dict() if self.usage_pricing_terms is not None else None
            ),
            "assurance_obligations": [o.to_dict() for o in self.assurance_obligations],
            "execution_scope": [s.to_dict() for s in self.execution_scope],
            "termination": self.termination.to_dict(),
            "provenance": self.provenance.to_dict(),
            "superseded_contract": (
                self.superseded_contract.to_dict() if self.superseded_contract is not None else None
            ),
        }


@dataclass(frozen=True)
class SelectOffers:
    """Bind the accepted offer references (INTENT -> OFFER_SELECTED)."""

    offers: Tuple[OpaqueReference, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {"command": "select-offers", "offers": [o.to_dict() for o in self.offers]}


@dataclass(frozen=True)
class ActivateContract:
    """Activate the contract (OFFER_SELECTED -> CONTRACT_ACTIVE). Requires
    at least one accepted offer and at least one signature reference."""

    activated_at: str
    signature_refs: Tuple[OpaqueReference, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": "activate",
            "activated_at": self.activated_at,
            "signature_refs": [s.to_dict() for s in self.signature_refs],
        }


@dataclass(frozen=True)
class RecordExecutionActivation:
    """Record that execution has started under the permitted scope."""

    recorded_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {"command": "record-execution-activation", "recorded_at": self.recorded_at}


@dataclass(frozen=True)
class RecordDelivery:
    """Record delivery of the acquired connectivity."""

    recorded_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {"command": "record-delivery", "recorded_at": self.recorded_at}


@dataclass(frozen=True)
class RecordAssurance:
    """Record an assurance evaluation result from the M005 authority.

    ``compliant`` advances DELIVERY -> ASSURED; ``degraded`` moves the
    contract to the explicit DEGRADED state (or records on ASSURED);
    ``violated`` fails the contract; ``unknown-stale`` records without a
    state transition (evidence-class honesty: unknown is never treated as
    compliant)."""

    recorded_at: str
    assurance_state: str
    evidence_refs: Tuple[OpaqueReference, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assurance_state",
            _require_in(self.assurance_state, ASSURANCE_STATES, "assurance.assurance_state"),
        )
        refs = _require_tuple(self.evidence_refs, "assurance.evidence_refs", min_len=1)
        normalized = []
        for i, ref in enumerate(refs):
            if not isinstance(ref, OpaqueReference):
                raise ContractError(
                    ContractReason.INVALID_INPUT,
                    "assurance.evidence_refs[%d] must be an OpaqueReference" % i,
                )
            if ref.ref_kind != "decision":
                raise ContractError(
                    ContractReason.VOCABULARY,
                    "assurance.evidence_refs[%d] must use the decision reference kind" % i,
                )
            normalized.append(ref)
        object.__setattr__(self, "evidence_refs", tuple(normalized))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": "record-assurance",
            "recorded_at": self.recorded_at,
            "assurance_state": self.assurance_state,
            "evidence_refs": [e.to_dict() for e in self.evidence_refs],
        }


@dataclass(frozen=True)
class RecordUsageFinal:
    """Record that usage accounting is final for the contract."""

    recorded_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {"command": "record-usage-final", "recorded_at": self.recorded_at}


@dataclass(frozen=True)
class RecordSettlementPending:
    """Record that settlement is pending on the external commercial rail."""

    recorded_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {"command": "record-settlement-pending", "recorded_at": self.recorded_at}


@dataclass(frozen=True)
class RecordSettled:
    """Record settlement completion (terminal SETTLED)."""

    recorded_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {"command": "record-settled", "recorded_at": self.recorded_at}


@dataclass(frozen=True)
class TerminateContract:
    """Terminate deliberately under the recorded termination rules."""

    recorded_at: str
    condition: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "condition",
            _require_in(self.condition, TERMINATION_CONDITION_KINDS, "termination.condition"),
        )
        object.__setattr__(self, "reason", _require_str(self.reason, "termination.reason"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": "terminate",
            "recorded_at": self.recorded_at,
            "condition": self.condition,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ExpireContract:
    """Expire the contract (validity/lease expiry; terminal EXPIRED)."""

    recorded_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {"command": "expire", "recorded_at": self.recorded_at}


@dataclass(frozen=True)
class FailContract:
    """Fail the contract explicitly (constraint violation or failed
    realization; terminal FAILED)."""

    recorded_at: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _require_str(self.reason, "failure.reason"))

    def to_dict(self) -> Dict[str, Any]:
        return {"command": "fail", "recorded_at": self.recorded_at, "reason": self.reason}


@dataclass(frozen=True)
class BindExecutionArtifact:
    """Bind an execution artifact reference as CONTRACT DATA (LOCK-117).

    Artifacts are recorded, never consulted for authority: the store
    exposes no path from an artifact to contract state decisions."""

    artifact: OpaqueReference

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, OpaqueReference):
            raise ContractError(
                ContractReason.INVALID_INPUT, "artifact must be an OpaqueReference"
            )
        if self.artifact.ref_kind != "execution-artifact":
            raise ContractError(
                ContractReason.VOCABULARY,
                "artifact must use the execution-artifact reference kind",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {"command": "bind-artifact", "artifact": self.artifact.to_dict()}


@dataclass(frozen=True)
class GrantLease:
    """Grant a contract-scoped lease (a new lease record)."""

    granted_at: str
    not_before: str
    not_after: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": "grant-lease",
            "granted_at": self.granted_at,
            "not_before": self.not_before,
            "not_after": self.not_after,
        }


@dataclass(frozen=True)
class RenewLease:
    """Renew a lease: creates a successor lease record; the predecessor is
    marked renewed (superseded), never mutated beyond that state flip."""

    lease_id: str
    granted_at: str
    not_before: str
    not_after: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": "renew-lease",
            "lease_id": self.lease_id,
            "granted_at": self.granted_at,
            "not_before": self.not_before,
            "not_after": self.not_after,
        }


@dataclass(frozen=True)
class RevokeLease:
    """Revoke a lease with a recorded reason (fail-closed audit)."""

    lease_id: str
    recorded_at: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _require_str(self.reason, "revocation.reason"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": "revoke-lease",
            "lease_id": self.lease_id,
            "recorded_at": self.recorded_at,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ExpireLease:
    """Expire a lease (past its not_after; terminal lease state)."""

    lease_id: str
    recorded_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": "expire-lease",
            "lease_id": self.lease_id,
            "recorded_at": self.recorded_at,
        }


COMMAND_KINDS: Tuple[str, ...] = (
    "create",
    "select-offers",
    "activate",
    "record-execution-activation",
    "record-delivery",
    "record-assurance",
    "record-usage-final",
    "record-settlement-pending",
    "record-settled",
    "terminate",
    "expire",
    "fail",
    "bind-artifact",
    "grant-lease",
    "renew-lease",
    "revoke-lease",
    "expire-lease",
)


# ----------------------------------------------------------------------
# The lifecycle kernel (pure transition evaluation)
# ----------------------------------------------------------------------


def check_transition(current: str, target: str) -> None:
    """Fail closed unless current -> target is a legal contract transition."""
    if current in TERMINAL_STATES:
        raise ContractError(
            ContractReason.CONTRACT_TERMINAL,
            "contract is terminal in %s; terminal states never transition" % current,
        )
    legal = CONTRACT_TRANSITIONS.get(current, ())
    if target not in legal:
        raise ContractError(
            ContractReason.INVALID_TRANSITION,
            "transition %s -> %s is not legal (legal: %s)"
            % (current, target, ", ".join(legal) or "none"),
        )


def apply_command(contract: ConnectivityContract, command: object) -> ConnectivityContract:
    """Pure lifecycle kernel: apply one command to one contract.

    Returns the successor contract record (identity and hard constraints
    unchanged; LOCK-108 is structural — no command carries constraints).
    Raises ContractError on any illegal input or transition.
    """
    if isinstance(command, CreateContract):
        raise ContractError(
            ContractReason.INVALID_INPUT,
            "create applies to an empty fold slot, not to an existing contract",
        )
    if contract.is_terminal:
        raise ContractError(
            ContractReason.CONTRACT_TERMINAL,
            "contract is terminal in %s; commands are rejected" % contract.state,
        )

    if isinstance(command, SelectOffers):
        check_transition(contract.state, "OFFER_SELECTED")
        if contract.state != "INTENT":
            raise ContractError(
                ContractReason.INVALID_TRANSITION,
                "offers bind exactly once (INTENT -> OFFER_SELECTED)",
            )
        offers = _require_tuple(command.offers, "select-offers.offers", min_len=1)
        for i, offer in enumerate(offers):
            if not isinstance(offer, OpaqueReference) or offer.ref_kind != "offer":
                raise ContractError(
                    ContractReason.VOCABULARY,
                    "offers[%d] must use the offer reference kind" % i,
                )
        return replace(contract, state="OFFER_SELECTED", accepted_offers=tuple(offers))

    if isinstance(command, ActivateContract):
        check_transition(contract.state, "CONTRACT_ACTIVE")
        if not contract.accepted_offers:
            raise ContractError(
                ContractReason.INVALID_STATE,
                "activation requires at least one accepted offer reference",
            )
        _require_instant(command.activated_at, "activation.activated_at")
        if contract.validity.is_not_yet_valid(command.activated_at):
            raise ContractError(
                ContractReason.NOT_YET_VALID,
                "activation instant %s precedes validity.not_before %s"
                % (command.activated_at, contract.validity.not_before),
            )
        if contract.validity.is_expired(command.activated_at):
            raise ContractError(
                ContractReason.EXPIRED,
                "activation instant %s is past validity.not_after %s"
                % (command.activated_at, contract.validity.not_after),
            )
        signatures = _require_tuple(
            command.signature_refs, "activate.signature_refs", min_len=1
        )
        for i, signature in enumerate(signatures):
            if not isinstance(signature, OpaqueReference) or signature.ref_kind != "signature":
                raise ContractError(
                    ContractReason.VOCABULARY,
                    "signature_refs[%d] must use the signature reference kind" % i,
                )
        return replace(contract, state="CONTRACT_ACTIVE", signature_refs=tuple(signatures))

    if isinstance(command, RecordExecutionActivation):
        check_transition(contract.state, "EXECUTION_ACTIVE")
        _require_instant(command.recorded_at, "execution-activation.recorded_at")
        if contract.validity.is_expired(command.recorded_at):
            raise ContractError(
                ContractReason.EXPIRED,
                "execution activation past validity expiry fails closed",
            )
        return replace(contract, state="EXECUTION_ACTIVE")

    if isinstance(command, RecordDelivery):
        check_transition(contract.state, "DELIVERY")
        _require_instant(command.recorded_at, "delivery.recorded_at")
        return replace(contract, state="DELIVERY")

    if isinstance(command, RecordAssurance):
        _require_instant(command.recorded_at, "assurance.recorded_at")
        if command.assurance_state == "compliant":
            check_transition(contract.state, "ASSURED")
            return replace(contract, state="ASSURED")
        if command.assurance_state == "degraded":
            if contract.state not in ("EXECUTION_ACTIVE", "DELIVERY", "ASSURED"):
                raise ContractError(
                    ContractReason.INVALID_TRANSITION,
                    "degraded assurance applies to active/delivered/assured contracts (found %s)"
                    % contract.state,
                )
            return replace(contract, state="DEGRADED")
        if command.assurance_state == "violated":
            check_transition(contract.state, "FAILED")
            return replace(contract, state="FAILED", termination_reason="constraint-violated")
        # unknown-stale: evidence honesty — recorded, no state change
        if contract.state not in ("EXECUTION_ACTIVE", "DELIVERY", "ASSURED", "DEGRADED"):
            raise ContractError(
                ContractReason.INVALID_TRANSITION,
                "unknown-stale assurance applies to post-activation contracts (found %s)"
                % contract.state,
            )
        return contract

    if isinstance(command, RecordUsageFinal):
        check_transition(contract.state, "USAGE_FINAL")
        _require_instant(command.recorded_at, "usage-final.recorded_at")
        return replace(contract, state="USAGE_FINAL")

    if isinstance(command, RecordSettlementPending):
        check_transition(contract.state, "SETTLEMENT_PENDING")
        _require_instant(command.recorded_at, "settlement-pending.recorded_at")
        return replace(contract, state="SETTLEMENT_PENDING")

    if isinstance(command, RecordSettled):
        check_transition(contract.state, "SETTLED")
        _require_instant(command.recorded_at, "settled.recorded_at")
        return replace(contract, state="SETTLED")

    if isinstance(command, TerminateContract):
        check_transition(contract.state, "TERMINATED")
        _require_instant(command.recorded_at, "termination.recorded_at")
        if command.condition not in contract.termination.conditions:
            raise ContractError(
                ContractReason.INVALID_STATE,
                "termination condition %s is not declared in the contract termination rules"
                % command.condition,
            )
        return replace(contract, state="TERMINATED", termination_reason=command.reason)

    if isinstance(command, ExpireContract):
        check_transition(contract.state, "EXPIRED")
        _require_instant(command.recorded_at, "expiry.recorded_at")
        if not contract.validity.is_expired(command.recorded_at):
            raise ContractError(
                ContractReason.INVALID_STATE,
                "expiry requires the evaluation instant to be past validity.not_after",
            )
        return replace(contract, state="EXPIRED", termination_reason="validity-expired")

    if isinstance(command, FailContract):
        check_transition(contract.state, "FAILED")
        _require_instant(command.recorded_at, "failure.recorded_at")
        return replace(contract, state="FAILED", termination_reason=command.reason)

    if isinstance(command, BindExecutionArtifact):
        # LOCK-117: artifacts bind as data at any non-terminal state
        if not isinstance(command.artifact, OpaqueReference):
            raise ContractError(ContractReason.INVALID_INPUT, "artifact must be an OpaqueReference")
        artifacts = contract.execution_artifacts + (command.artifact,)
        return replace(contract, execution_artifacts=artifacts)

    raise ContractError(
        ContractReason.INVALID_INPUT,
        "unsupported contract command %s" % type(command).__name__,
    )


def build_contract(command: CreateContract) -> ConnectivityContract:
    """Build the initial INTENT contract from the creation core."""
    if not isinstance(command, CreateContract):
        raise ContractError(
            ContractReason.INVALID_INPUT, "build_contract requires a CreateContract command"
        )
    contract_id = _derive_contract_id_from_core(
        command.principal,
        command.beneficiaries,
        command.requirements,
        command.hard_constraints,
        command.validity,
    )
    return ConnectivityContract(
        contract_id=contract_id,
        state="INTENT",
        principal=command.principal,
        beneficiaries=command.beneficiaries,
        requirements=command.requirements,
        accepted_offers=(),
        hard_constraints=command.hard_constraints,
        service_properties=command.service_properties,
        validity=command.validity,
        usage_pricing_terms=command.usage_pricing_terms,
        assurance_obligations=command.assurance_obligations,
        execution_scope=command.execution_scope,
        termination=command.termination,
        provenance=command.provenance,
        signature_refs=(),
        execution_artifacts=(),
        superseded_contract=command.superseded_contract,
    )
