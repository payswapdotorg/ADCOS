"""ADCOS credential-lifecycle domain model (M018 — Credential and Key
Lifecycle Operations).

The operational credential-lifecycle records of the R8 charter M018
scope, composing the accepted M014 identity/federation/client
convergence surfaces BY REFERENCE (import and compose; never
reimplement, weaken, fork, or bypass).  The authority split is
mechanical:

- **The credential lifecycle authority** is the accepted ``identity/``
  domain (WORK-004 + the M014 hardening): credential records,
  lifecycle states, ATOMIC rotation (``IdentityService.rotate`` over
  the all-or-nothing ``StoreBatch``), revocation, and the M014
  credential-lifecycle/authorization verdict vocabularies.  This
  domain never re-derives any of it — the verdict values consumed
  here are imported from ``identity.convergence`` and re-exported as
  admitting-subset DATA.
- **The admission gate** is the accepted ``client/``/``federation/``
  surface (the converged authorization runtime over the canonical
  contract lease + consent attestation + declared quota), driven
  through its public APIs (LOCK-117: no second authorization runtime
  anywhere in this package).
- **The M018 records** (this module) are LIFECYCLE-OPERATION
  EVIDENCE: the journaled rotation/revocation/emergency/propagation
  sequences with the before/after ADMITTED SETS fully recorded, the
  declared deterministic propagation rounds, and the inventory audit
  traces.  They ride credential REFERENCES and public metadata only
  (LOCK-119: structurally secret-free — no member of any public
  record type can carry secret bytes; secret material lives only
  behind the accepted ``CredentialStore`` interface, which this
  package never opens).

The central boundary (enforced throughout):

    LIFECYCLE OPERATION JOURNAL / PROPAGATION ROUNDS / AUDIT TRACE
        = OPERATIONAL EVIDENCE over the accepted credential
          authorities (references + public metadata only; the
          before/after admitted sets are recorded from the identity
          authority's own public reads at the operation instants)
        != CREDENTIAL AUTHORITY (identity/ stays the sole authority)
        != THE ADMISSION GATE (client/ + federation/ stay the sole
          authorization runtime; this domain drives them, never
          re-decides trust)

Determinism (LOCK-119): content-derived ids over canonical JSON
(namespaced, position-independent for the idempotency discipline);
injected RFC 3339 UTC instants only (no wall clock, no randomness,
no UUIDs, no network, no secrets); sorted and order-normalized
iteration; canonical-JSON round-trips with tamper-evident ids
re-verified at deserialization; PYTHONHASHSEED-safe.
"""

from __future__ import annotations

import contextlib
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from identity.convergence import (
    AUTHORIZATION_VERDICTS,
    CREDENTIAL_VERDICTS,
)
from identity.lifecycle import LifecycleState

from .errors import CredentialLifecycleError, CredentialLifecycleReason

__all__ = [
    # frozen vocabularies
    "OPERATION_KINDS",
    "EMERGENCY_STEP_KINDS",
    "INVENTORY_BREAK_KINDS",
    "ADMITTING_LIFECYCLE_VERDICTS",
    "ADMITTING_AUTHORIZATION_VERDICTS",
    "CREDENTIALS_PREFIX",
    "CREDENTIALS_ISSUER",
    "PROPAGATION_ISSUER",
    # typed records
    "EmergencyStep",
    "LifecycleOperationRecord",
    "PropagationPlan",
    "AdmissionProbe",
    "InventoryTrace",
    "InventoryAuditRecord",
    "LifecycleFold",
    # the pure kernels
    "derive_operation_id",
    "derive_probe_id",
    "admitted_set_from_records",
    "check_rotation_flip_is_atomic",
    "check_removal_is_atomic",
    "check_zero_coverage_gap",
    "plan_propagation",
    "round_deliveries",
    "consumer_observed_revocation",
    "record_from_mapping",
    "probe_from_mapping",
]


# ----------------------------------------------------------------------
# The consumed-boundary error wrap (exception isolation)
# ----------------------------------------------------------------------

_CONSUMED_CODE_MAP = {
    "secret-rejected": CredentialLifecycleReason.SECRET_REJECTED,
    "vocabulary": CredentialLifecycleReason.VOCABULARY,
    "temporal-invalid": CredentialLifecycleReason.TEMPORAL_INVALID,
    "invalid-input": CredentialLifecycleReason.INVALID_INPUT,
    "id-mismatch": CredentialLifecycleReason.ID_MISMATCH,
    "lifecycle-illegal": CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
}


def _wrap_consumed_error(label: str) -> Iterator[None]:
    """Exception isolation at the consumed-domain boundary: an
    ``IdentityError``/``IdentityConvergenceError``/``ConvergenceError``/
    ``ClientError``/``EvidenceError`` (typed errors carrying
    ``code``/``detail`` — or the client's ``reason``) surfaces as a
    typed :class:`CredentialLifecycleError` with its deterministic
    text preserved — never a foreign exception type, never raw
    exception text into stored state.  The consumed domains'
    LOCK-119 secret rejection maps onto this surface's own
    ``credential-secret-rejected``."""

    @contextlib.contextmanager
    def _ctx() -> Iterator[None]:
        try:
            yield
        except CredentialLifecycleError:
            raise
        except Exception as error:  # noqa: BLE001 - consumed typed errors
            code = str(
                getattr(error, "code", "")
                or getattr(error, "reason", "")
                or ""
            )
            mapped = _CONSUMED_CODE_MAP.get(
                code, CredentialLifecycleReason.COMPOSITION
            )
            detail = str(
                getattr(error, "detail", "") or error
            )
            raise CredentialLifecycleError(
                mapped,
                "%s was rejected by a consumed domain: %s"
                % (label, detail),
            ) from None

    return _ctx()


# ----------------------------------------------------------------------
# Frozen vocabularies (the consumed vocabularies cited by reference)
# ----------------------------------------------------------------------

#: The namespaced id prefix (content-derived ids only).
CREDENTIALS_PREFIX = "m018-credentials"

#: The default issuer recorded on lifecycle-operation provenance
#: (LOCK-118: the M018 surface asserts its own records; the identity
#: authority stays the sole credential authority).
CREDENTIALS_ISSUER = "credentials:lifecycle-drill"

#: The issuer recorded on records produced by the propagation drive.
PROPAGATION_ISSUER = "credentials:propagation-drive"

#: The M018-owned journaled operation kinds (the deterministic,
#: replayable lifecycle-operation vocabulary).  ``emergency-
#: revocation`` is a DISTINCT kind — the emergency path is never a
#: silent shortcut taken through ``revocation``:
#:
#: - ``rotation`` — one ATOMIC credential rotation: the accepted
#:   ``IdentityService.rotate`` (all-or-nothing StoreBatch) driven by
#:   reference, with the before/after admitted sets fully recorded and
#:   the flip journaled at the rotation instant;
#: - ``revocation`` — one ordinary (non-emergency) credential
#:   revocation through the accepted ``IdentityService.revoke``;
#: - ``emergency-revocation`` — the distinct typed EMERGENCY path:
#:   the identity-side revocation, the M014 authorization revocation
#:   and the accepted emergency stop on the admission gate, every
#:   step journaled with LOCK-106 evidence references;
#: - ``propagation-round`` — one deterministic revocation-propagation
#:   round (the declared fanout over the declared consumer order);
#: - ``inventory-audit`` — one completed fail-closed inventory audit
#:   (read-only: the authoritative admitted set is unchanged).
OPERATION_KINDS: Tuple[str, ...] = (
    "rotation",
    "revocation",
    "emergency-revocation",
    "propagation-round",
    "inventory-audit",
)

#: The frozen emergency-path step kinds (the distinct typed operation
#: carries exactly these steps, in this order — every step evidence-
#: visible via its LOCK-106 record references).
EMERGENCY_STEP_KINDS: Tuple[str, ...] = (
    "identity-revocation",
    "authorization-revocation",
    "admission-gate-stop",
)

#: The typed inventory break kinds (the fail-closed audit vocabulary —
#: an admitted credential without a complete lifecycle record chain
#: is a TYPED FAILURE carrying the specific break kind, never a
#: warning):
#:
#: - ``unknown-reference`` — an admitted reference with NO credential
#:   record in the identity store;
#: - ``status-mismatch`` — an admitted reference whose record status
#:   is not ACTIVE (the journal's admitted set disagrees with the
#:   identity authority — fail closed, never silently trusted);
#: - ``missing-activation`` — an ACTIVE record without an activation
#:   instant (an incomplete lifecycle chain);
#: - ``missing-supersession`` — a SUPERSEDED generation without a
#:   supersession instant;
#: - ``missing-revocation-info`` — a REVOKED record without revocation
#:   metadata;
#: - ``generation-gap`` — the (node, role) key-version chain is not a
#:   gapless run (a generation is missing from the chain);
#: - ``bookkeeping-missing`` — the M014 credential-lifecycle
#:   bookkeeping lacks the recorded activation an ACTIVE credential
#:   requires (the consumed M014 evaluation would fail closed).
INVENTORY_BREAK_KINDS: Tuple[str, ...] = (
    "unknown-reference",
    "status-mismatch",
    "missing-activation",
    "missing-supersession",
    "missing-revocation-info",
    "generation-gap",
    "bookkeeping-missing",
)

#: The lifecycle verdicts that ADMIT a credential (a strict subset of
#: the consumed M014 ``CREDENTIAL_VERDICTS`` — cited by reference,
#: import-time drift-guarded: every member must exist in the consumed
#: vocabulary or this module refuses to import).
ADMITTING_LIFECYCLE_VERDICTS: Tuple[str, ...] = ("ok", "rotation-due")

#: The authorization verdicts that ADMIT a node's principal
#: authorization (a strict subset of the consumed M014
#: ``AUTHORIZATION_VERDICTS`` — same by-reference discipline).
ADMITTING_AUTHORIZATION_VERDICTS: Tuple[str, ...] = ("authorized",)

for _verdict in ADMITTING_LIFECYCLE_VERDICTS:
    if _verdict not in CREDENTIAL_VERDICTS:  # pragma: no cover - drift guard
        raise ImportError(
            "credentials/model.py: the M014 CREDENTIAL_VERDICTS vocabulary no "
            "longer carries %r (consumed by reference — never redefined here)"
            % (_verdict,)
        )
for _verdict in ADMITTING_AUTHORIZATION_VERDICTS:
    if _verdict not in AUTHORIZATION_VERDICTS:  # pragma: no cover - drift guard
        raise ImportError(
            "credentials/model.py: the M014 AUTHORIZATION_VERDICTS vocabulary "
            "no longer carries %r (consumed by reference — never redefined here)"
            % (_verdict,)
        )

#: Secret-shaped markers (LOCK-119; the frozen defensive grammar —
#: identical to the accepted M014 convention).
_SECRET_MARKERS = tuple(sorted((
    "private_key", "secret_key", "password", "passwd",
    "client_secret", "credential_secret", "api_key",
)))


# ----------------------------------------------------------------------
# Internal helpers (deterministic, fail-closed)
# ----------------------------------------------------------------------


def _require_instant(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.TEMPORAL_INVALID,
            "%s must be a non-empty RFC 3339 UTC instant string" % label,
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.TEMPORAL_INVALID,
            "%s must be an RFC 3339 UTC instant (%s)" % (label, error),
        ) from error
    return value


def _require_reference(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    lowered = value.lower()
    for marker in _SECRET_MARKERS:
        if marker in lowered:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.SECRET_REJECTED,
                "%s is secret-shaped material; secrets never enter "
                "credential-lifecycle records (LOCK-119)" % label,
            )
    return value


def _require_reference_set(value: object, label: str) -> Tuple[str, ...]:
    """A sorted, duplicate-free tuple of non-secret reference strings
    (the canonical admitted-set shape)."""
    if not isinstance(value, (tuple, list, frozenset, set)):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "%s must be a sequence of reference strings" % label,
        )
    items: list = []
    for item in value:
        items.append(_require_reference(item, "%s member" % label))
    if len(set(items)) != len(items):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "%s carries duplicate reference(s)" % label,
        )
    return tuple(sorted(items))


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _content_id(namespace: str, material: Dict[str, Any]) -> str:
    try:
        return "%s:%s:sha256:%s" % (
            CREDENTIALS_PREFIX,
            namespace,
            _sha256_hex(canonical_json_bytes(material)),
        )
    except CanonicalizationError as error:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "record content is not canonicalizable (%s)" % error,
        ) from error


# ----------------------------------------------------------------------
# The journaled lifecycle operation record
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class EmergencyStep:
    """One step of the distinct typed emergency-revocation path
    (explicit, journaled, evidence-visible).  ``evidence_refs`` cite
    REAL LOCK-106 evidence records (consumed by reference from the
    accepted ``evidence/`` typing — the ids resolve inside the real
    evidence store the drill composed)."""

    step: str
    detail: str
    evidence_refs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.step not in EMERGENCY_STEP_KINDS:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.VOCABULARY,
                "emergency step %r is outside the frozen emergency-path "
                "vocabulary %s" % (self.step, EMERGENCY_STEP_KINDS),
            )
        _require_reference(self.detail, "emergency step detail")
        object.__setattr__(
            self, "evidence_refs",
            _require_reference_set(self.evidence_refs, "emergency step evidence_refs"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "detail": self.detail,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, data: object) -> "EmergencyStep":
        if not isinstance(data, Mapping):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "emergency step material must be a mapping",
            )
        return cls(
            step=str(data.get("step", "")),
            detail=str(data.get("detail", "")),
            evidence_refs=tuple(str(item) for item in data.get("evidence_refs", ())),
        )


@dataclass(frozen=True)
class LifecycleOperationRecord:
    """One journaled credential-lifecycle operation.

    The record is OPERATIONAL EVIDENCE over the accepted identity
    authority: ``before_admitted``/``after_admitted`` are the node's
    admitted credential-reference sets as read from the identity
    authority's own public records immediately BEFORE and immediately
    AFTER the operation (fully recorded, sorted, duplicate-free); the
    admitted-set transition between them is verified by the
    zero-coverage-gap kernel (an exact single flip for a rotation; an
    exact single removal for a revocation; NO change for a
    propagation round or an inventory audit).  ``operation_id`` is the
    POSITION-INDEPENDENT content identity (the idempotency key: a
    retried operation re-derives it and never double-applies); the
    journal position stays the separate ``sequence`` member validated
    by the fold (gapless, conflict-free, unique per identity).

    Kind-conditional members are validated (typed representation
    discipline): only a rotation carries ``replacement_ref``; only
    revocations carry ``reason``; only the emergency kind carries
    ``steps``; only a propagation round carries the round members.
    """

    operation_id: str
    kind: str
    sequence: int
    node_id: str
    recorded_at: str
    subject_ref: str
    before_admitted: Tuple[str, ...]
    after_admitted: Tuple[str, ...]
    replacement_ref: str = ""
    reason: str = ""
    steps: Tuple[EmergencyStep, ...] = ()
    propagates_operation: str = ""
    round_index: int = 0
    delivered_to: Tuple[str, ...] = ()
    pending_after: Tuple[str, ...] = ()
    converged: bool = False
    evidence_refs: Tuple[str, ...] = ()
    provenance: str = ""

    def __post_init__(self) -> None:
        if self.kind not in OPERATION_KINDS:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.VOCABULARY,
                "operation kind %r is outside the frozen M018 vocabulary %s"
                % (self.kind, OPERATION_KINDS),
            )
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "operation sequence must be an integer",
            )
        if self.sequence < 1:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "operation sequence must be >= 1 (gapless journal positions)",
            )
        _require_reference(self.node_id, "operation node_id")
        _require_instant(self.recorded_at, "operation recorded_at")
        object.__setattr__(
            self, "before_admitted",
            _require_reference_set(self.before_admitted, "before_admitted"),
        )
        object.__setattr__(
            self, "after_admitted",
            _require_reference_set(self.after_admitted, "after_admitted"),
        )
        if self.subject_ref:
            _require_reference(self.subject_ref, "operation subject_ref")
        if self.replacement_ref:
            _require_reference(self.replacement_ref, "operation replacement_ref")
        if self.reason:
            _require_reference(self.reason, "operation reason")
        if self.propagates_operation:
            _require_reference(
                self.propagates_operation, "operation propagates_operation"
            )
        _require_reference(self.provenance, "operation provenance")
        object.__setattr__(
            self, "evidence_refs",
            _require_reference_set(self.evidence_refs, "operation evidence_refs"),
        )
        if not isinstance(self.steps, tuple) or any(
            not isinstance(step, EmergencyStep) for step in self.steps
        ):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "operation steps must be EmergencyStep records",
            )
        object.__setattr__(self, "steps", tuple(self.steps))
        if isinstance(self.round_index, bool) or not isinstance(self.round_index, int):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "operation round_index must be an integer",
            )
        if self.round_index < 0:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "operation round_index must be >= 0",
            )
        object.__setattr__(
            self, "delivered_to",
            _require_reference_set(self.delivered_to, "operation delivered_to"),
        )
        object.__setattr__(
            self, "pending_after",
            _require_reference_set(self.pending_after, "operation pending_after"),
        )
        # -- kind-conditional member discipline (fail closed) ----------
        if self.kind == "rotation":
            if not self.subject_ref or not self.replacement_ref:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.INVALID_INPUT,
                    "a rotation record requires subject_ref (the superseded "
                    "generation) and replacement_ref (the new generation)",
                )
            if self.reason or self.steps or self.propagates_operation:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.VOCABULARY,
                    "a rotation record cannot carry revocation/emergency/"
                    "propagation members",
                )
            if self.round_index or self.delivered_to or self.pending_after:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.VOCABULARY,
                    "a rotation record cannot carry propagation-round members",
                )
        elif self.kind in ("revocation", "emergency-revocation"):
            if not self.subject_ref or not self.reason:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.INVALID_INPUT,
                    "a %s record requires subject_ref and reason" % self.kind,
                )
            if self.replacement_ref or self.propagates_operation:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.VOCABULARY,
                    "a %s record cannot carry rotation/propagation members"
                    % self.kind,
                )
            if self.round_index or self.delivered_to or self.pending_after:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.VOCABULARY,
                    "a %s record cannot carry propagation-round members"
                    % self.kind,
                )
            if self.kind == "revocation" and self.steps:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.VOCABULARY,
                    "only the DISTINCT emergency-revocation kind carries "
                    "emergency steps (the emergency path is never a silent "
                    "shortcut through ordinary revocation)",
                )
            if self.kind == "emergency-revocation":
                if tuple(step.step for step in self.steps) != EMERGENCY_STEP_KINDS:
                    raise CredentialLifecycleError(
                        CredentialLifecycleReason.VOCABULARY,
                        "the emergency-revocation record must carry exactly "
                        "the frozen emergency steps %s (in order, every step "
                        "present)" % (EMERGENCY_STEP_KINDS,),
                    )
        elif self.kind == "propagation-round":
            if not self.subject_ref or not self.propagates_operation:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.INVALID_INPUT,
                    "a propagation-round record requires subject_ref (the "
                    "revoked credential) and propagates_operation (the "
                    "revocation being propagated)",
                )
            if self.round_index < 1:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.INVALID_INPUT,
                    "a propagation-round record requires round_index >= 1",
                )
            if self.replacement_ref or self.reason or self.steps:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.VOCABULARY,
                    "a propagation-round record cannot carry rotation/"
                    "revocation/emergency members",
                )
        else:  # inventory-audit
            if self.subject_ref or self.replacement_ref or self.reason:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.VOCABULARY,
                    "an inventory-audit record is node-scoped (no "
                    "subject/replacement/reason members)",
                )
            if (
                self.steps
                or self.propagates_operation
                or self.round_index
                or self.delivered_to
                or self.pending_after
                or self.converged
            ):
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.VOCABULARY,
                    "an inventory-audit record cannot carry emergency/"
                    "propagation members",
                )
        # -- the zero-coverage-gap kernel (mechanical, at construction) --
        if self.kind == "rotation":
            check_rotation_flip_is_atomic(
                self.before_admitted, self.after_admitted,
                self.subject_ref, self.replacement_ref,
            )
        elif self.kind in ("revocation", "emergency-revocation"):
            check_removal_is_atomic(
                self.before_admitted, self.after_admitted, self.subject_ref
            )
        else:
            if self.before_admitted != self.after_admitted:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.ROTATION_NONATOMIC,
                    "a %s record must not change the authoritative admitted "
                    "set (%s -> %s: read-only operations never carry an "
                    "unrecorded transition)" % (self.kind, self.before_admitted,
                                                self.after_admitted),
                )
        # -- tamper-evident identity --------------------------------------
        expected = derive_operation_id(self._id_material())
        if not self.operation_id:
            object.__setattr__(self, "operation_id", expected)
        elif self.operation_id != expected:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.ID_MISMATCH,
                "operation id %r does not digest its content (tamper evidence)"
                % (self.operation_id,),
            )

    # -- content identity -------------------------------------------------

    def _id_material(self) -> Dict[str, Any]:
        material: Dict[str, Any] = {
            "kind": self.kind,
            "node_id": self.node_id,
            "recorded_at": self.recorded_at,
            "subject_ref": self.subject_ref,
            "before_admitted": list(self.before_admitted),
            "after_admitted": list(self.after_admitted),
            "replacement_ref": self.replacement_ref,
            "reason": self.reason,
            "propagates_operation": self.propagates_operation,
            "round_index": self.round_index,
            "delivered_to": list(self.delivered_to),
            "pending_after": list(self.pending_after),
            "converged": self.converged,
            "evidence_refs": list(self.evidence_refs),
            "provenance": self.provenance,
        }
        if self.steps:
            material["steps"] = [step.to_dict() for step in self.steps]
        return material

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"operation_id": self.operation_id, "sequence": self.sequence}
        out.update(self._id_material())
        return out

    @classmethod
    def from_dict(cls, data: object) -> "LifecycleOperationRecord":
        if not isinstance(data, Mapping):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "operation material must be a mapping",
            )
        steps = tuple(
            EmergencyStep.from_dict(item) for item in data.get("steps", ())
        )
        return cls(
            operation_id=str(data.get("operation_id", "")),
            kind=str(data.get("kind", "")),
            sequence=int(data.get("sequence", 0)),
            node_id=str(data.get("node_id", "")),
            recorded_at=str(data.get("recorded_at", "")),
            subject_ref=str(data.get("subject_ref", "")),
            before_admitted=tuple(
                str(item) for item in data.get("before_admitted", ())
            ),
            after_admitted=tuple(
                str(item) for item in data.get("after_admitted", ())
            ),
            replacement_ref=str(data.get("replacement_ref", "")),
            reason=str(data.get("reason", "")),
            steps=steps,
            propagates_operation=str(data.get("propagates_operation", "")),
            round_index=int(data.get("round_index", 0)),
            delivered_to=tuple(
                str(item) for item in data.get("delivered_to", ())
            ),
            pending_after=tuple(
                str(item) for item in data.get("pending_after", ())
            ),
            converged=bool(data.get("converged", False)),
            evidence_refs=tuple(
                str(item) for item in data.get("evidence_refs", ())
            ),
            provenance=str(data.get("provenance", "")),
        )


def derive_operation_id(material: Mapping[str, Any]) -> str:
    """The position-independent content identity of one lifecycle
    operation (the idempotency key — the journal position is a
    separate member validated by the fold)."""
    return _content_id("op", dict(material))


# ----------------------------------------------------------------------
# The zero-coverage-gap kernel (the core M018 atomicity discipline)
# ----------------------------------------------------------------------


def check_rotation_flip_is_atomic(
    before: Tuple[str, ...],
    after: Tuple[str, ...],
    superseded_ref: str,
    replacement_ref: str,
) -> None:
    """A rotation's admitted-set transition is EXACTLY ONE FLIP: the
    superseded generation is admitted before and not after; the
    replacement is not admitted before and is admitted after; the set
    is otherwise unchanged.  Any intermediate window (both admitted,
    or neither) is the coverage gap the charter forbids — fail closed
    (typed ``credential-rotation-nonatomic``)."""
    before_set = set(_require_reference_set(before, "before_admitted"))
    after_set = set(_require_reference_set(after, "after_admitted"))
    _require_reference(superseded_ref, "superseded_ref")
    _require_reference(replacement_ref, "replacement_ref")
    if superseded_ref == replacement_ref:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "a rotation cannot replace a credential with itself (%r)"
            % (superseded_ref,),
        )
    if superseded_ref not in before_set:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "the rotation of %r is not admitted before the flip (the "
            "before/after sets are inconsistent — never a fabricated "
            "rotation)" % (superseded_ref,),
        )
    if superseded_ref in after_set:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "the superseded credential %r is STILL ADMITTED after the "
            "rotation instant (a coverage window: no operation window may "
            "admit a superseded credential — fail closed)" % (superseded_ref,),
        )
    if replacement_ref in before_set:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "the replacement credential %r is admitted BEFORE the flip "
            "(both generations admitted — a coverage window; fail closed)"
            % (replacement_ref,),
        )
    if replacement_ref not in after_set:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "the replacement credential %r is NOT admitted after the flip "
            "(neither generation admitted — a coverage gap; fail closed)"
            % (replacement_ref,),
        )
    expected = (before_set - {superseded_ref}) | {replacement_ref}
    if after_set != expected:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "the rotation changed more than the single flip (%s -> %s; "
            "expected exactly %s)" % (sorted(before_set), sorted(after_set),
                                      sorted(expected)),
        )


def check_removal_is_atomic(
    before: Tuple[str, ...],
    after: Tuple[str, ...],
    revoked_ref: str,
) -> None:
    """A revocation's admitted-set transition is EXACTLY ONE REMOVAL:
    the revoked credential was admitted before, is not admitted
    after, and nothing else changed.  Anything else fails closed
    (typed ``credential-rotation-nonatomic`` — the same
    zero-coverage-gap kernel class)."""
    before_set = set(_require_reference_set(before, "before_admitted"))
    after_set = set(_require_reference_set(after, "after_admitted"))
    _require_reference(revoked_ref, "revoked_ref")
    if revoked_ref not in before_set:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "the revoked credential %r is not admitted before the "
            "revocation (the before/after sets are inconsistent — never a "
            "fabricated revocation)" % (revoked_ref,),
        )
    if revoked_ref in after_set:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "the revoked credential %r is STILL ADMITTED after the "
            "revocation instant (a coverage window: no operation window "
            "may admit a revoked credential — fail closed)" % (revoked_ref,),
        )
    expected = before_set - {revoked_ref}
    if after_set != expected:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "the revocation changed more than the single removal (%s -> %s; "
            "expected exactly %s)" % (sorted(before_set), sorted(after_set),
                                      sorted(expected)),
        )


def check_zero_coverage_gap(
    fold: "LifecycleFold", credential_ref: str
) -> None:
    """The explicit zero-coverage-gap verification over the FOLDED
    journal timeline: a credential's admission ends at EXACTLY ONE
    journaled flip, and no journaled instant at or after that flip
    admits it.  The fold's continuity + atomicity kernels already
    make the window mechanically impossible; this check makes the
    invariant explicit and quotable (the battery probes the admitted
    set at every journaled instant)."""
    _require_reference(credential_ref, "credential_ref")
    flips = [
        (index, record)
        for index, record in enumerate(fold.records)
        if (
            (record.kind == "rotation" and record.subject_ref == credential_ref)
            or (
                record.kind in ("revocation", "emergency-revocation")
                and record.subject_ref == credential_ref
            )
        )
    ]
    if not flips:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
            "credential %r never leaves the admitted set on this journal "
            "(no journaled flip — the zero-coverage-gap verification "
            "requires one)" % (credential_ref,),
        )
    if len(flips) > 1:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "credential %r leaves the admitted set at %d journaled flips "
            "(the admitted set must flip EXACTLY once per credential)"
            % (credential_ref, len(flips)),
        )
    flip_index, flip_record = flips[0]
    for index, admitted in enumerate(fold.admitted_timeline):
        if index >= flip_index and credential_ref in admitted:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.ROTATION_NONATOMIC,
                "the journaled admitted set at operation %d (at or after "
                "the flip of %r at %s) still admits the credential — a "
                "coverage window (fail closed)"
                % (index + 1, credential_ref, flip_record.recorded_at),
            )
    if credential_ref not in flip_record.before_admitted:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "the flip record for %r does not record the credential as "
            "admitted before the flip (the before set is the evidence)"
            % (credential_ref,),
        )


# ----------------------------------------------------------------------
# The admitted set (derived from the identity authority's own records)
# ----------------------------------------------------------------------


def admitted_set_from_records(records, node_id_text: str) -> Tuple[str, ...]:
    """The node's admitted credential-reference set as read from the
    identity authority's own public records (the WORK-004 status
    truth — ACTIVE records only; sorted, duplicate-free).  This
    domain never re-decides admission: the identity authority's own
    record status IS the admitted-set truth at the read instant."""
    _require_reference(node_id_text, "node_id")
    from identity.credentials import CredentialRecord  # by reference

    admitted: list = []
    for record in records:
        if not isinstance(record, CredentialRecord):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.COMPOSITION,
                "admitted_set_from_records requires identity "
                "CredentialRecord objects (got %s — the identity "
                "authority's own records, consumed by reference)"
                % type(record).__name__,
            )
        if record.node_id.text != node_id_text:
            continue
        if record.status is LifecycleState.ACTIVE:
            admitted.append(record.reference.reference_id)
    return tuple(sorted(set(admitted)))


# ----------------------------------------------------------------------
# The declared deterministic propagation (rounds with a round-count bound)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class PropagationPlan:
    """The DECLARED revocation-propagation plan: the ordered consumer
    set, the per-round fanout, and the convergence bound as a ROUND
    COUNT (never a wall-clock bound).  The round sequence is a pure
    function of (consumers, fanout): round r delivers to the r-th
    declared fanout slice in the declared (sorted) consumer order —
    same inputs -> identical rounds."""

    consumers: Tuple[str, ...]
    fanout_per_round: int
    max_rounds: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "consumers",
            _require_reference_set(self.consumers, "plan consumers"),
        )
        if not self.consumers:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "a propagation plan requires at least one declared consumer",
            )
        for label, value in (
            ("fanout_per_round", self.fanout_per_round),
            ("max_rounds", self.max_rounds),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.INVALID_INPUT,
                    "propagation plan %s must be an int (a ROUND COUNT — "
                    "never a wall-clock bound)" % label,
                )
            if value < 1:
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.INVALID_INPUT,
                    "propagation plan %s must be >= 1" % label,
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consumers": list(self.consumers),
            "fanout_per_round": self.fanout_per_round,
            "max_rounds": self.max_rounds,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PropagationPlan":
        if not isinstance(data, Mapping):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "propagation plan material must be a mapping",
            )
        return cls(
            consumers=tuple(str(item) for item in data.get("consumers", ())),
            fanout_per_round=int(data.get("fanout_per_round", 0)),
            max_rounds=int(data.get("max_rounds", 0)),
        )


def plan_propagation(
    consumers, fanout_per_round: int, max_rounds: int
) -> PropagationPlan:
    """Construct the declared propagation plan (deterministic shape
    validation; the convergence bound is the declared ROUND COUNT)."""
    return PropagationPlan(
        consumers=tuple(consumers),
        fanout_per_round=fanout_per_round,
        max_rounds=max_rounds,
    )


def round_deliveries(plan: PropagationPlan) -> Tuple[Tuple[str, ...], ...]:
    """The deterministic round delivery sequence: round r (1-based)
    delivers to the r-th fanout slice of the declared consumer order.
    A pure function of the plan — same inputs -> identical rounds."""
    if not isinstance(plan, PropagationPlan):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "round_deliveries requires a PropagationPlan",
        )
    rounds: list = []
    index = 0
    while index < len(plan.consumers):
        rounds.append(
            tuple(plan.consumers[index:index + plan.fanout_per_round])
        )
        index += plan.fanout_per_round
    return tuple(rounds)


def consumer_observed_revocation(
    rounds, consumer: str
) -> bool:
    """True iff the declared consumer received the propagated
    revocation within the given round sequence (the replayable
    consumer-observation model)."""
    _require_reference(consumer, "consumer")
    for record in rounds:
        delivered = getattr(record, "delivered_to", ())
        if consumer in delivered:
            return True
    return False


# ----------------------------------------------------------------------
# The composed admission probe (the by-reference gate verdict)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AdmissionProbe:
    """One composed admission-gate verdict for a credential at an
    injected instant — the three CONSUMED verdicts recorded verbatim
    (never re-decided here):

    - ``lifecycle_verdict`` — the M014 credential-lifecycle verdict
      (consumed from ``identity.convergence`` — one of the frozen
      ``CREDENTIAL_VERDICTS``);
    - ``authorization_verdict`` — the M014 principal-authorization
      verdict (consumed from ``identity.convergence`` — one of the
      frozen ``AUTHORIZATION_VERDICTS``);
    - ``operational_state`` — the accepted converged admission gate's
      session state at the probe (``active`` or the typed rejection
      class recorded from the consumed ``federation`` runtime).

    ``admitted`` is TRUE iff all three consumed verdicts are
    admitting; ``rejection`` names the first rejecting gate's verdict
    (empty when admitted).  LOCK-117: no second authorization runtime
    — this record is DATA about the accepted surfaces' own decisions.
    """

    probe_id: str
    credential_ref: str
    node_id: str
    at_instant: str
    lifecycle_verdict: str
    authorization_verdict: str
    operational_state: str
    admitted: bool
    rejection: str

    def __post_init__(self) -> None:
        _require_reference(self.credential_ref, "probe credential_ref")
        _require_reference(self.node_id, "probe node_id")
        _require_instant(self.at_instant, "probe at_instant")
        if self.lifecycle_verdict not in CREDENTIAL_VERDICTS:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.VOCABULARY,
                "probe lifecycle_verdict %r is outside the consumed M014 "
                "CREDENTIAL_VERDICTS vocabulary (never re-decided here)"
                % (self.lifecycle_verdict,),
            )
        if self.authorization_verdict not in AUTHORIZATION_VERDICTS:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.VOCABULARY,
                "probe authorization_verdict %r is outside the consumed "
                "M014 AUTHORIZATION_VERDICTS vocabulary (never re-decided "
                "here)" % (self.authorization_verdict,),
            )
        _require_reference(
            self.operational_state, "probe operational_state"
        )
        if not isinstance(self.admitted, bool):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "probe admitted must be a bool",
            )
        computed = (
            self.lifecycle_verdict in ADMITTING_LIFECYCLE_VERDICTS
            and self.authorization_verdict in ADMITTING_AUTHORIZATION_VERDICTS
            and self.operational_state == "active"
        )
        if self.admitted != computed:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "probe admitted=%r disagrees with the consumed verdicts "
                "(lifecycle=%r authorization=%r operational=%r — the "
                "composed verdict is mechanical, never caller-supplied)"
                % (self.admitted, self.lifecycle_verdict,
                   self.authorization_verdict, self.operational_state),
            )
        expected_rejection = ""
        if not computed:
            if self.lifecycle_verdict not in ADMITTING_LIFECYCLE_VERDICTS:
                expected_rejection = "lifecycle:%s" % self.lifecycle_verdict
            elif self.authorization_verdict not in ADMITTING_AUTHORIZATION_VERDICTS:
                expected_rejection = "authorization:%s" % self.authorization_verdict
            else:
                expected_rejection = "admission-gate:%s" % self.operational_state
        if self.rejection != expected_rejection:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "probe rejection %r does not name the first rejecting gate "
                "(expected %r — deterministic, never caller-supplied)"
                % (self.rejection, expected_rejection),
            )
        expected = _content_id("probe", {
            "credential_ref": self.credential_ref,
            "node_id": self.node_id,
            "at_instant": self.at_instant,
            "lifecycle_verdict": self.lifecycle_verdict,
            "authorization_verdict": self.authorization_verdict,
            "operational_state": self.operational_state,
        })
        if not self.probe_id:
            object.__setattr__(self, "probe_id", expected)
        elif self.probe_id != expected:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.ID_MISMATCH,
                "probe id %r does not digest its content (tamper evidence)"
                % (self.probe_id,),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "credential_ref": self.credential_ref,
            "node_id": self.node_id,
            "at_instant": self.at_instant,
            "lifecycle_verdict": self.lifecycle_verdict,
            "authorization_verdict": self.authorization_verdict,
            "operational_state": self.operational_state,
            "admitted": self.admitted,
            "rejection": self.rejection,
        }

    @classmethod
    def from_dict(cls, data: object) -> "AdmissionProbe":
        if not isinstance(data, Mapping):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "probe material must be a mapping",
            )
        return cls(
            probe_id=str(data.get("probe_id", "")),
            credential_ref=str(data.get("credential_ref", "")),
            node_id=str(data.get("node_id", "")),
            at_instant=str(data.get("at_instant", "")),
            lifecycle_verdict=str(data.get("lifecycle_verdict", "")),
            authorization_verdict=str(data.get("authorization_verdict", "")),
            operational_state=str(data.get("operational_state", "")),
            admitted=bool(data.get("admitted", False)),
            rejection=str(data.get("rejection", "")),
        )


def derive_probe_id(material: Mapping[str, Any]) -> str:
    return _content_id("probe", dict(material))


# ----------------------------------------------------------------------
# The inventory audit records
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class InventoryTrace:
    """The per-credential lifecycle trace of one inventory audit: the
    admitted credential's reference, its identity record's status,
    its key version, its activation instant, and the references of
    the lifecycle evidence (the journaled operations that produced
    its state).  A PURE READ (never a mutation)."""

    credential_ref: str
    status: str
    key_version: int
    activated_at: str
    operation_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_reference(self.credential_ref, "trace credential_ref")
        if self.status not in tuple(state.value for state in LifecycleState):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.VOCABULARY,
                "trace status %r is outside the WORK-004 lifecycle "
                "vocabulary (consumed by reference)" % (self.status,),
            )
        if isinstance(self.key_version, bool) or not isinstance(
            self.key_version, int
        ):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "trace key_version must be an integer",
            )
        if self.key_version < 1:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "trace key_version must be >= 1",
            )
        if self.activated_at:
            _require_instant(self.activated_at, "trace activated_at")
        object.__setattr__(
            self, "operation_refs",
            _require_reference_set(self.operation_refs, "trace operation_refs"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "credential_ref": self.credential_ref,
            "status": self.status,
            "key_version": self.key_version,
            "activated_at": self.activated_at,
            "operation_refs": list(self.operation_refs),
        }

    @classmethod
    def from_dict(cls, data: object) -> "InventoryTrace":
        if not isinstance(data, Mapping):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "trace material must be a mapping",
            )
        return cls(
            credential_ref=str(data.get("credential_ref", "")),
            status=str(data.get("status", "")),
            key_version=int(data.get("key_version", 0)),
            activated_at=str(data.get("activated_at", "")),
            operation_refs=tuple(
                str(item) for item in data.get("operation_refs", ())
            ),
        )


@dataclass(frozen=True)
class InventoryAuditRecord:
    """One completed fail-closed inventory audit (read-only evidence):
    every admitted credential traced to a valid lifecycle record.  A
    broken chain NEVER produces this record — the audit raises the
    typed ``credential-inventory-incomplete`` failure citing the
    break kind (never a warning)."""

    audit_id: str
    node_id: str
    audited_at: str
    admitted_count: int
    traces: Tuple[InventoryTrace, ...]

    def __post_init__(self) -> None:
        _require_reference(self.node_id, "audit node_id")
        _require_instant(self.audited_at, "audit audited_at")
        if isinstance(self.admitted_count, bool) or not isinstance(
            self.admitted_count, int
        ):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "audit admitted_count must be an integer",
            )
        if self.admitted_count < 0:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "audit admitted_count must be >= 0",
            )
        if not isinstance(self.traces, tuple) or any(
            not isinstance(trace, InventoryTrace) for trace in self.traces
        ):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "audit traces must be InventoryTrace records",
            )
        object.__setattr__(self, "traces", tuple(self.traces))
        if len(self.traces) != self.admitted_count:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "audit admitted_count (%d) disagrees with the trace count "
                "(%d) — every admitted credential carries exactly one trace"
                % (self.admitted_count, len(self.traces)),
            )
        expected = _content_id("audit", {
            "node_id": self.node_id,
            "audited_at": self.audited_at,
            "traces": [trace.to_dict() for trace in self.traces],
        })
        if not self.audit_id:
            object.__setattr__(self, "audit_id", expected)
        elif self.audit_id != expected:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.ID_MISMATCH,
                "audit id %r does not digest its content (tamper evidence)"
                % (self.audit_id,),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "node_id": self.node_id,
            "audited_at": self.audited_at,
            "admitted_count": self.admitted_count,
            "traces": [trace.to_dict() for trace in self.traces],
        }

    @classmethod
    def from_dict(cls, data: object) -> "InventoryAuditRecord":
        if not isinstance(data, Mapping):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "audit material must be a mapping",
            )
        traces = tuple(
            InventoryTrace.from_dict(item) for item in data.get("traces", ())
        )
        return cls(
            audit_id=str(data.get("audit_id", "")),
            node_id=str(data.get("node_id", "")),
            audited_at=str(data.get("audited_at", "")),
            admitted_count=int(data.get("admitted_count", 0)),
            traces=traces,
        )


# ----------------------------------------------------------------------
# The journal fold (the replay result)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class LifecycleFold:
    """The deterministic replay result of one lifecycle operation
    journal: the records in journal order and the ADMITTED-SET
    TIMELINE (the authoritative admitted set after each operation —
    construction-is-recovery; the fold re-derives it purely from the
    journaled records)."""

    node_id: str
    records: Tuple[LifecycleOperationRecord, ...]
    admitted_timeline: Tuple[Tuple[str, ...], ...]
    initial_admitted: Tuple[str, ...]
    digest: str

    def admitted_set_at(self, at_instant: str) -> Tuple[str, ...]:
        """The journaled admitted set at an injected instant: the
        after-set of the LAST operation recorded at or before the
        instant (fail closed for an instant preceding the first
        journaled operation — the pre-history is never fabricated)."""
        _require_instant(at_instant, "at_instant")
        if not self.records:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
                "the journal carries no operations — there is no journaled "
                "admitted-set truth yet (never fabricated)",
            )
        if at_instant < self.records[0].recorded_at:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
                "instant %s precedes the first journaled operation at %s "
                "(the pre-history admitted set is never fabricated — fail "
                "closed)" % (at_instant, self.records[0].recorded_at),
            )
        admitted = self.initial_admitted
        for record in self.records:
            if record.recorded_at <= at_instant:
                admitted = record.after_admitted
            else:
                break
        return admitted

    def current_admitted(self) -> Tuple[str, ...]:
        if not self.records:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
                "the journal carries no operations (no current admitted set)",
            )
        return self.records[-1].after_admitted


def record_from_mapping(data: object) -> LifecycleOperationRecord:
    """Fail-closed wire construction of one operation record (the
    derived identity is re-verified inside the constructor)."""
    return LifecycleOperationRecord.from_dict(data)


def probe_from_mapping(data: object) -> AdmissionProbe:
    """Fail-closed wire construction of one admission probe."""
    return AdmissionProbe.from_dict(data)
