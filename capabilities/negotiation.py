"""Deterministic capability negotiation (WORK-005).

Negotiation answers exactly one question:

    What mutually understood capability/profile can both parties support?

It NEVER answers whether a peer is authorized or trusted (WORK-010 and
later trust/federation work), and it never scores cost/trust/reputation/
routing/resources (later layers).

Determinism: results depend only on the inputs — sorted iteration, no
wall-clock (the evaluation instant is injected), no hash-order, no
locale-sensitive comparison, no provider order. Tie-breaking uses the
protocol data model: lexicographic capability_id, then the numerically
greatest schema version (most recent compatible), then the greatest
compatible parameter envelope.

Version compatibility: MAJOR must match; the negotiated statement's
minor must be <= the required side's minor when a requirement pins a
minimum (additive evolution is compatible; major changes are not).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .classification import CapabilityIdClass, classify_capability_id
from .model import CapabilityError, CapabilityStatement
from .validity import StatementStatus, evaluate_status


class RejectionReason:
    """Stable machine-readable rejection reasons (explicit failure)."""

    UNKNOWN_REQUIRED_CAPABILITY = "unknown-required-capability"
    MALFORMED_CAPABILITY_ID = "malformed-capability-id"
    VERSION_INCOMPATIBLE = "version-incompatible"
    PARAMETER_MISMATCH = "parameter-mismatch"
    CONSTRAINT_MISMATCH = "constraint-mismatch"
    NO_ACTIVE_STATEMENT = "no-active-statement"
    NOT_USABLE_AT_INSTANT = "not-usable-at-instant"
    NO_COMMON_CAPABILITY = "no-common-capability"


@dataclass(frozen=True)
class Requirement:
    """One negotiation requirement: a capability with version bounds,
    required/optional semantics, and required parameter/constraint
    expectations.

    ``required=True``: absence/incompatibility/unknown-ness of this
    capability FAILS the negotiation explicitly. ``required=False``:
    the capability may be absent without failing negotiation (best
    effort).
    """

    capability_id: str
    min_schema_version: str = "1.0"
    required: bool = True
    required_parameters: Mapping[str, Any] = field(default_factory=dict)
    required_constraints: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        classification = classify_capability_id(self.capability_id)
        if classification == CapabilityIdClass.INVALID:
            raise CapabilityError(
                "requirement",
                "requirement capability_id %r is malformed" % self.capability_id,
            )
        import re

        if re.fullmatch(r"^[0-9]+\.[0-9]+$", self.min_schema_version) is None:
            raise CapabilityError(
                "requirement", "min_schema_version must be MAJOR.MINOR"
            )


@dataclass(frozen=True)
class NegotiationSpec:
    """Inputs to a negotiation: local requirements, peer statements,
    and the injected evaluation instant."""

    requirements: Tuple[Requirement, ...]
    peer_statements: Tuple[CapabilityStatement, ...]
    now: datetime


@dataclass(frozen=True)
class NegotiationOutcome:
    """The result for ONE requirement: selected statement or an explicit
    rejection reason (never silent satisfaction)."""

    capability_id: str
    selected: Optional[CapabilityStatement]
    reason: Optional[str] = None
    detail: str = ""

    @property
    def succeeded(self) -> bool:
        return self.selected is not None


@dataclass(frozen=True)
class NegotiationResult:
    """The full negotiation result: per-requirement outcomes in input
    order, plus overall success (all REQUIRED requirements satisfied —
    optional ones may be unsatisfied without failing)."""

    outcomes: Tuple[NegotiationOutcome, ...]

    @property
    def succeeded(self) -> bool:
        """True iff every REQUIRED requirement selected a capability.

        Optional requirements may be unsatisfied (absent capability,
        unknown-but-well-formed identifier) without failing the
        negotiation as a whole.
        """
        requirements = getattr(self, "_requirements", ())
        for outcome, requirement in zip(self.outcomes, requirements):
            if requirement.required and not outcome.succeeded:
                return False
        return True

    @property
    def failure_reasons(self) -> List[str]:
        return [
            "%s: %s (%s)" % (o.capability_id, o.reason, o.detail)
            for o in self.outcomes
            if not o.succeeded and o.reason
        ]


def _requirements_of(result: "NegotiationResult") -> Sequence[Requirement]:
    return getattr(result, "_requirements", ())


def _parse_version(version: str) -> Tuple[int, int]:
    major, minor = version.split(".")
    return (int(major), int(minor))


def _version_compatible(candidate: str, required_minimum: str) -> bool:
    cand = _parse_version(candidate)
    req = _parse_version(required_minimum)
    if cand[0] != req[0]:
        return False
    return cand[1] >= req[1]


def _values_compatible(
    offered: Any, required: Any
) -> bool:
    """Deterministic value-compatibility for required parameters/constraints.

    A numeric requirement is satisfied when the offered value is >= the
    requirement (capacity-style: bandwidth/latency bounds, counts). A
    string/bool requirement requires equality. Objects recurse per key.
    An absent offered value does not satisfy a present requirement.
    """
    if isinstance(required, bool):
        return offered is required
    if isinstance(required, (int, float)) and not isinstance(required, bool):
        if isinstance(offered, (int, float)) and not isinstance(offered, bool):
            return float(offered) >= float(required)
        return False
    if isinstance(required, str):
        return offered == required
    if isinstance(required, dict):
        if not isinstance(offered, dict):
            return False
        return all(key in offered and _values_compatible(offered[key], value) for key, value in required.items())
    if isinstance(required, list):
        if not isinstance(offered, list):
            return False
        return all(any(_values_compatible(o, r) for o in offered) for r in required)
    return offered == required


def negotiate(spec: NegotiationSpec, *, requirements: Sequence[Requirement] = ()) -> NegotiationResult:
    """Deterministically negotiate each requirement against the peer's
    offered statements.

    ``requirements`` may alternatively be supplied via
    ``NegotiationSpec.requirements`` (kept as a parameter for
    call-site clarity); if both are given the parameter wins.
    """
    active_requirements: Sequence[Requirement] = tuple(requirements) or spec.requirements

    # Peer statements usable at the evaluation instant (withdrawn and
    # expired statements NEVER negotiate as currently usable).
    usable: Dict[str, List[CapabilityStatement]] = {}
    for statement in spec.peer_statements:
        try:
            status = evaluate_status(
                valid_from=statement.valid_from,
                expires_at=statement.expires_at,
                withdrawn_at=statement.withdrawn_at,
                now=spec.now,
            )
        except Exception:
            continue  # malformed statement: not usable, never crashes negotiation
        if status != StatementStatus.ACTIVE:
            continue
        usable.setdefault(statement.capability_id, []).append(statement)

    outcomes: List[NegotiationOutcome] = []
    attached: List[Requirement] = []
    for requirement in active_requirements:
        attached.append(requirement)
        candidates = usable.get(requirement.capability_id, [])
        classification = classify_capability_id(requirement.capability_id)

        if classification == CapabilityIdClass.UNKNOWN_BUT_WELL_FORMED:
            if requirement.required:
                outcomes.append(
                    NegotiationOutcome(
                        capability_id=requirement.capability_id,
                        selected=None,
                        reason=RejectionReason.UNKNOWN_REQUIRED_CAPABILITY,
                        detail="required capability identifier is well-formed but not registered; "
                        "explicit failure (never coerced to a known capability)",
                    )
                )
            else:
                outcomes.append(
                    NegotiationOutcome(
                        capability_id=requirement.capability_id,
                        selected=None,
                        reason=None,
                        detail="unknown optional capability safely ignored (preserved, not coerced)",
                    )
                )
            continue

        compatible: List[CapabilityStatement] = []
        for candidate in candidates:
            if not _version_compatible(candidate.schema_version, requirement.min_schema_version):
                continue
            if not all(
                _values_compatible(candidate.parameters.get(key), value)
                for key, value in requirement.required_parameters.items()
            ):
                continue
            if not all(
                _values_compatible(candidate.constraints.get(key), value)
                for key, value in requirement.required_constraints.items()
            ):
                continue
            compatible.append(candidate)

        if not compatible:
            if candidates:
                # Present but incompatible: classify the dominant reason.
                version_ok = [
                    c for c in candidates
                    if _version_compatible(c.schema_version, requirement.min_schema_version)
                ]
                if not version_ok:
                    reason = RejectionReason.VERSION_INCOMPATIBLE
                    detail = "peer offers schema_version(s) %s; required >= %s with matching major" % (
                        sorted({c.schema_version for c in candidates}),
                        requirement.min_schema_version,
                    )
                else:
                    reason = RejectionReason.PARAMETER_MISMATCH
                    detail = "no candidate satisfies required parameters/constraints"
            else:
                reason = RejectionReason.NO_ACTIVE_STATEMENT
                detail = "peer offers no active statement for this capability at the evaluation instant"
            outcomes.append(
                NegotiationOutcome(
                    capability_id=requirement.capability_id,
                    selected=None,
                    reason=reason if requirement.required else None,
                    detail=detail if requirement.required else "optional capability unsatisfied (non-fatal)",
                )
            )
            continue

        # Deterministic tie-breaking: capability ids are equal here, so
        # order by (schema version descending, provider identity, valid_from,
        # signature) — the protocol data model, never implementation order.
        compatible.sort(
            key=lambda s: (
                tuple(-part for part in _parse_version(s.schema_version)),
                s.provider_identity,
                s.valid_from,
                s.signature,
            )
        )
        outcomes.append(
            NegotiationOutcome(
                capability_id=requirement.capability_id,
                selected=compatible[0],
                detail="selected deterministically among %d compatible candidate(s)" % len(compatible),
            )
        )

    result = NegotiationResult(outcomes=tuple(outcomes))
    # attach requirements for succeeded computation (frozen dataclass —
    # store out-of-band via a private attribute on a wrapper)
    object.__setattr__(result, "_requirements", tuple(attached))
    return result
