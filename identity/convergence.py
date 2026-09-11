"""M014 identity convergence — authorization and credential-lifecycle
production hardening (R7-CORE-001, DEC-0101).

The identity package's M014 harvest onto the Architecture 1.1
authority (the migration matrix: "Identity / Trust: RETAIN +
REFACTOR -> ADCOS identity/authority"): the WORK-004 node-identity
and credential machinery stays THE identity authority (NodeID
derivation, credential records, lifecycle states — consumed by
reference, never duplicated); this module adds the converged
production-hardening surfaces the R7 charter's M014 scope names:

- **authorization** — :class:`PrincipalAuthorization`: the durable
  binding of a canonical ADCOS NodeID to a REAL M002 contract
  principal (the ``contracts.Principal`` vocabulary cited by
  reference; the contract citation digests the real contract's OWN
  canonical bytes — LOCK-101/LOCK-118).  The typed
  :func:`check_principal_authorization` gate fails closed on node
  mismatch, contract mismatch, window violations and revocation —
  possessing a valid identity is NOT trust and NOT authorization
  (LOCK-022 discipline preserved; the authorization is an explicit,
  revocable, windowed record).
- **evidence** — :func:`authorization_attestation`: the closed-loop
  seam lifting one principal authorization into the REAL M005 typed
  evidence space (an immutable ``controller-verified`` attestation
  record — LOCK-106/LOCK-118).
- **revocation** — :class:`AuthorizationRevocation` plus the
  append-only idempotent :class:`AuthorizationRegistry` (sorted
  iteration, content digests, history preserved — revoked
  authorizations stay visible with their typed reason).
- **credential lifecycle** — :class:`CredentialLifecyclePolicy` /
  :class:`CredentialLifecycleState` /
  :func:`evaluate_credential_lifecycle`: the deterministic
  rotation-deadline discipline over INJECTED instants (rotation due /
  overdue / expired / revoked / too-many-active verdicts — typed,
  fail-closed), composing the WORK-004 lifecycle vocabulary by
  reference.

Determinism (LOCK-119): content-derived ids over canonical JSON;
injected RFC 3339 UTC instants only (no wall clock, no randomness,
no UUIDs, no network); sorted iteration; typed errors with stable
codes; secret-shaped material is rejected at every construction
boundary (the WORK-004 secret-isolation discipline).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from contracts import PRINCIPAL_KINDS
from evidence import AttestationEvidence

from .lifecycle import LifecycleState
from .node_id import NodeIdError, parse_node_id

#: The namespaced id prefix (content-derived ids only).
IDENTITY_CONVERGENCE_PREFIX = "m014-identity"

#: The typed authorization verdicts (the frozen check vocabulary).
AUTHORIZATION_VERDICTS: Tuple[str, ...] = (
    "authorized",
    "node-mismatch",
    "contract-mismatch",
    "not-yet-valid",
    "expired",
    "revoked",
)

#: The typed credential-lifecycle verdicts.
CREDENTIAL_VERDICTS: Tuple[str, ...] = (
    "ok",
    "rotation-due",
    "rotation-overdue",
    "expired",
    "revoked",
    "not-active",
    "too-many-active",
)

#: Secret-shaped markers (LOCK-119; the frozen defensive grammar).
_SECRET_MARKERS = tuple(sorted((
    "private_key", "secret_key", "password", "passwd",
    "client_secret", "credential_secret", "api_key",
)))


class IdentityConvergenceReasonCode:
    """The frozen typed reason vocabulary (stable codes)."""

    INVALID_INPUT = "invalid-input"
    VOCABULARY = "vocabulary"
    TEMPORAL_INVALID = "temporal-invalid"
    SECRET_REJECTED = "secret-rejected"
    NOT_FOUND = "not-found"
    ID_MISMATCH = "id-mismatch"
    LIFECYCLE_ILLEGAL = "lifecycle-illegal"
    EVIDENCE_REJECTED = "evidence-rejected"
    TOO_MANY_ACTIVE = "too-many-active"


class IdentityConvergenceError(Exception):
    """The typed fail-closed error (stable code + bounded detail)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = str(code)
        self.detail = str(detail)

    @property
    def reason(self) -> str:
        return self.code


def _require_instant(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.TEMPORAL_INVALID,
            "%s must be a non-empty RFC 3339 UTC instant string" % label,
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.TEMPORAL_INVALID,
            "%s must be an RFC 3339 UTC instant (%s)" % (label, error),
        ) from error
    return value


def _require_reference(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    lowered = value.lower()
    for marker in _SECRET_MARKERS:
        if marker in lowered:
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.SECRET_REJECTED,
                "%s is secret-shaped material; secrets never enter "
                "authorization metadata (LOCK-119)" % label,
            )
    return value


def _require_node_id(value: object, label: str) -> str:
    """A canonical ADCOS NodeID text (the WORK-004 grammar — parsed
    through the real machinery, never re-implemented)."""
    text = _require_reference(value, label)
    try:
        parse_node_id(text)
    except NodeIdError as error:
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.INVALID_INPUT,
            "%s must be a canonical ADCOS NodeID (%s)" % (label, error),
        ) from error
    return text


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# The principal authorization binding (the M002 citation by reference)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrincipalAuthorization:
    """The durable NodeID -> contract-principal authorization binding.

    The record cites a REAL M002 ``ConnectivityContract`` (its own id
    plus the SHA-256 digest of its OWN canonical bytes — computed at
    construction from the real contract, never caller-supplied) and
    the contract principal's frozen kind/ref vocabulary.  The binding
    is windowed, revocable and typed; possessing a valid NodeID is
    never authorization by itself (LOCK-022 discipline).
    """

    authorization_id: str
    node_id: str
    principal_kind: str
    principal_ref: str
    contract_id: str
    contract_digest: str
    valid_from: str
    valid_until: str

    def __post_init__(self) -> None:
        for label, value in (
            ("authorization_id", self.authorization_id),
            ("principal_kind", self.principal_kind),
            ("principal_ref", self.principal_ref),
            ("contract_id", self.contract_id),
            ("contract_digest", self.contract_digest),
        ):
            if not isinstance(value, str) or not value:
                raise IdentityConvergenceError(
                    IdentityConvergenceReasonCode.INVALID_INPUT,
                    "authorization %s must be a non-empty string" % label,
                )
        if self.principal_kind not in PRINCIPAL_KINDS:
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.VOCABULARY,
                "principal kind %r is outside the frozen M002 "
                "PRINCIPAL_KINDS vocabulary (cited by reference)"
                % self.principal_kind,
            )
        _require_node_id(self.node_id, "authorization node_id")
        _require_reference(self.principal_ref, "authorization principal_ref")
        _require_reference(self.contract_id, "authorization contract_id")
        _require_instant(self.valid_from, "authorization valid_from")
        _require_instant(self.valid_until, "authorization valid_until")
        if not self.valid_until > self.valid_from:
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.TEMPORAL_INVALID,
                "authorization validity must be non-empty (valid_until "
                "%s must be strictly after valid_from %s)"
                % (self.valid_until, self.valid_from),
            )
        expected = "%s:authz:sha256:%s" % (
            IDENTITY_CONVERGENCE_PREFIX,
            _sha256_hex(canonical_json_bytes({
                "node_id": self.node_id,
                "principal_kind": self.principal_kind,
                "principal_ref": self.principal_ref,
                "contract_id": self.contract_id,
                "contract_digest": self.contract_digest,
                "valid_from": self.valid_from,
                "valid_until": self.valid_until,
            })),
        )
        if self.authorization_id != expected:
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.ID_MISMATCH,
                "authorization id %r does not digest its content" % (
                    self.authorization_id,
                ),
            )

    def to_dict(self) -> Dict[str, str]:
        return {
            "authorization_id": self.authorization_id,
            "node_id": self.node_id,
            "principal_kind": self.principal_kind,
            "principal_ref": self.principal_ref,
            "contract_id": self.contract_id,
            "contract_digest": self.contract_digest,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PrincipalAuthorization":
        if not isinstance(data, dict):
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.INVALID_INPUT,
                "authorization material must be a mapping",
            )
        return cls(
            authorization_id=str(data.get("authorization_id", "")),
            node_id=str(data.get("node_id", "")),
            principal_kind=str(data.get("principal_kind", "")),
            principal_ref=str(data.get("principal_ref", "")),
            contract_id=str(data.get("contract_id", "")),
            contract_digest=str(data.get("contract_digest", "")),
            valid_from=str(data.get("valid_from", "")),
            valid_until=str(data.get("valid_until", "")),
        )


def build_principal_authorization(
    *,
    node_id: str,
    principal_kind: str,
    principal_ref: str,
    contract: Any,
    valid_from: str,
    valid_until: str,
) -> PrincipalAuthorization:
    """Construct the authorization binding against a REAL M002
    contract (the canonical citation — the digest is the contract's
    OWN canonical bytes; LOCK-101)."""
    contract_id = getattr(contract, "contract_id", None)
    canonical = getattr(contract, "canonical_bytes", None)
    if not isinstance(contract_id, str) or not contract_id:
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.INVALID_INPUT,
            "build_principal_authorization requires a real "
            "ConnectivityContract (contract_id missing)",
        )
    if not callable(canonical):
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.INVALID_INPUT,
            "build_principal_authorization requires the contract's "
            "canonical_bytes surface",
        )
    digest = _sha256_hex(canonical())
    authorization_id = "%s:authz:sha256:%s" % (
        IDENTITY_CONVERGENCE_PREFIX,
        _sha256_hex(canonical_json_bytes({
            "node_id": node_id,
            "principal_kind": principal_kind,
            "principal_ref": principal_ref,
            "contract_id": contract_id,
            "contract_digest": digest,
            "valid_from": valid_from,
            "valid_until": valid_until,
        })),
    )
    return PrincipalAuthorization(
        authorization_id=authorization_id,
        node_id=node_id,
        principal_kind=principal_kind,
        principal_ref=principal_ref,
        contract_id=contract_id,
        contract_digest=digest,
        valid_from=valid_from,
        valid_until=valid_until,
    )


def check_principal_authorization(
    authorization: PrincipalAuthorization,
    *,
    node_id: str,
    contract_id: str,
    at_instant: str,
    revoked: bool = False,
) -> str:
    """The typed authorization gate (fail-closed verdicts from the
    frozen vocabulary; never an exception for a plain denial)."""
    if not isinstance(authorization, PrincipalAuthorization):
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.INVALID_INPUT,
            "check_principal_authorization requires a "
            "PrincipalAuthorization",
        )
    _require_node_id(node_id, "gate node_id")
    _require_reference(contract_id, "gate contract_id")
    _require_instant(at_instant, "gate at_instant")
    if revoked:
        return "revoked"
    if node_id != authorization.node_id:
        return "node-mismatch"
    if contract_id != authorization.contract_id:
        return "contract-mismatch"
    if at_instant < authorization.valid_from:
        return "not-yet-valid"
    if at_instant > authorization.valid_until:
        return "expired"
    return "authorized"


# ---------------------------------------------------------------------------
# The authorization revocation + registry (the revocation hardening)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthorizationRevocation:
    """One explicit authorization revocation (append-only; the typed
    reason and instant; history preserved)."""

    revocation_id: str
    authorization_id: str
    reason: str
    revoked_at: str

    def __post_init__(self) -> None:
        for label, value in (
            ("revocation_id", self.revocation_id),
            ("authorization_id", self.authorization_id),
            ("reason", self.reason),
            ("revoked_at", self.revoked_at),
        ):
            if not isinstance(value, str) or not value:
                raise IdentityConvergenceError(
                    IdentityConvergenceReasonCode.INVALID_INPUT,
                    "revocation %s must be a non-empty string" % label,
                )
        _require_reference(self.reason, "revocation reason")
        _require_instant(self.revoked_at, "revocation revoked_at")
        expected = "%s:revoke:sha256:%s" % (
            IDENTITY_CONVERGENCE_PREFIX,
            _sha256_hex(canonical_json_bytes({
                "authorization_id": self.authorization_id,
                "reason": self.reason,
                "revoked_at": self.revoked_at,
            })),
        )
        if self.revocation_id != expected:
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.ID_MISMATCH,
                "revocation id %r does not digest its content" % (
                    self.revocation_id,
                ),
            )

    def to_dict(self) -> Dict[str, str]:
        return {
            "revocation_id": self.revocation_id,
            "authorization_id": self.authorization_id,
            "reason": self.reason,
            "revoked_at": self.revoked_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "AuthorizationRevocation":
        if not isinstance(data, dict):
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.INVALID_INPUT,
                "revocation material must be a mapping",
            )
        return cls(
            revocation_id=str(data.get("revocation_id", "")),
            authorization_id=str(data.get("authorization_id", "")),
            reason=str(data.get("reason", "")),
            revoked_at=str(data.get("revoked_at", "")),
        )


def authorization_revocation(
    *, authorization_id: str, reason: str, revoked_at: str
) -> AuthorizationRevocation:
    """Construct one authorization revocation (content-derived id)."""
    return AuthorizationRevocation(
        revocation_id="%s:revoke:sha256:%s" % (
            IDENTITY_CONVERGENCE_PREFIX,
            _sha256_hex(canonical_json_bytes({
                "authorization_id": authorization_id,
                "reason": reason,
                "revoked_at": revoked_at,
            })),
        ),
        authorization_id=authorization_id,
        reason=reason,
        revoked_at=revoked_at,
    )


class AuthorizationRegistry:
    """The append-only, idempotent principal-authorization registry
    (deterministic sorted iteration; revocations never delete; the
    canonical digest is byte-stable across runs and hash seeds)."""

    def __init__(self) -> None:
        self._authorizations: Dict[str, PrincipalAuthorization] = {}
        self._revocations: Dict[str, AuthorizationRevocation] = {}

    def register(
        self, authorization: PrincipalAuthorization
    ) -> PrincipalAuthorization:
        """Idempotent register: the identical record replays as a
        no-op; a DIFFERENT record under the same id fails closed; a
        revoked authorization is never re-registered."""
        if not isinstance(authorization, PrincipalAuthorization):
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.INVALID_INPUT,
                "register requires a PrincipalAuthorization",
            )
        existing = self._authorizations.get(authorization.authorization_id)
        if existing is not None:
            if existing.to_dict() != authorization.to_dict():
                raise IdentityConvergenceError(
                    IdentityConvergenceReasonCode.ID_MISMATCH,
                    "authorization id %r already exists with different "
                    "content" % authorization.authorization_id,
                )
            return existing
        if authorization.authorization_id in self._revocations:
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.LIFECYCLE_ILLEGAL,
                "authorization %r is revoked; revoked authorizations are "
                "never re-registered" % authorization.authorization_id,
            )
        self._authorizations[authorization.authorization_id] = authorization
        return authorization

    def revoke(
        self, revocation: AuthorizationRevocation
    ) -> AuthorizationRevocation:
        """Idempotent revocation (the authorization must exist; the
        identical revocation replays as a no-op)."""
        if not isinstance(revocation, AuthorizationRevocation):
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.INVALID_INPUT,
                "revoke requires an AuthorizationRevocation",
            )
        if revocation.authorization_id not in self._authorizations:
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.NOT_FOUND,
                "revocation cites unknown authorization %r"
                % revocation.authorization_id,
            )
        existing = self._revocations.get(revocation.authorization_id)
        if existing is not None:
            if existing.to_dict() != revocation.to_dict():
                raise IdentityConvergenceError(
                    IdentityConvergenceReasonCode.LIFECYCLE_ILLEGAL,
                    "authorization %r is already revoked with a different "
                    "revocation record" % revocation.authorization_id,
                )
            return existing
        self._revocations[revocation.authorization_id] = revocation
        return revocation

    def authorizations(self) -> Tuple[PrincipalAuthorization, ...]:
        return tuple(
            self._authorizations[key]
            for key in sorted(self._authorizations)
        )

    def authorization(
        self, authorization_id: str
    ) -> PrincipalAuthorization:
        record = self._authorizations.get(authorization_id)
        if record is None:
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.NOT_FOUND,
                "unknown authorization %r" % authorization_id,
            )
        return record

    def is_revoked(self, authorization_id: str) -> bool:
        return authorization_id in self._revocations

    def revocation(
        self, authorization_id: str
    ) -> AuthorizationRevocation:
        record = self._revocations.get(authorization_id)
        if record is None:
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.NOT_FOUND,
                "authorization %r is not revoked" % authorization_id,
            )
        return record

    def check(
        self,
        authorization_id: str,
        *,
        node_id: str,
        contract_id: str,
        at_instant: str,
    ) -> str:
        """The registry-backed typed gate (revocation observed
        first)."""
        record = self.authorization(authorization_id)
        return check_principal_authorization(
            record,
            node_id=node_id,
            contract_id=contract_id,
            at_instant=at_instant,
            revoked=self.is_revoked(authorization_id),
        )

    def digest(self) -> str:
        return _sha256_hex(canonical_json_bytes({
            "authorizations": [
                record.to_dict() for record in self.authorizations()
            ],
            "revocations": [
                self._revocations[key].to_dict()
                for key in sorted(self._revocations)
            ],
        }))

    def to_dict(self) -> Dict[str, object]:
        return {
            "authorizations": [
                record.to_dict() for record in self.authorizations()
            ],
            "revocations": [
                self._revocations[key].to_dict()
                for key in sorted(self._revocations)
            ],
        }

    @classmethod
    def from_dict(cls, data: object) -> "AuthorizationRegistry":
        if not isinstance(data, dict):
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.INVALID_INPUT,
                "registry material must be a mapping",
            )
        registry = cls()
        for item in data.get("authorizations", ()):
            registry.register(PrincipalAuthorization.from_dict(item))
        for item in data.get("revocations", ()):
            registry.revoke(AuthorizationRevocation.from_dict(item))
        return registry


# ---------------------------------------------------------------------------
# The closed-loop seam (the M005 typed evidence lift)
# ---------------------------------------------------------------------------


def authorization_attestation(
    authorization: PrincipalAuthorization,
    *,
    producer: str,
    valid_until: str,
) -> AttestationEvidence:
    """Lift one principal authorization into the REAL M005 typed
    evidence space (an immutable ``controller-verified`` attestation
    — the closed-loop convergence; LOCK-106/LOCK-118).  ``valid_until``
    is an injected validity instant strictly after the authorization's
    ``valid_from``."""
    if not isinstance(authorization, PrincipalAuthorization):
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.INVALID_INPUT,
            "authorization_attestation requires a PrincipalAuthorization",
        )
    _require_reference(producer, "attestation producer")
    _require_instant(valid_until, "attestation valid_until")
    try:
        return AttestationEvidence(
            subject_ref=authorization.node_id,
            contract_ref=authorization.contract_id,
            instant=authorization.valid_from,
            producer=producer,
            attestation_kind="controller-verified",
            attested_value=1,
            valid_until=valid_until,
            source_refs=(authorization.authorization_id,),
        )
    except Exception as error:  # consumed-domain isolation
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.EVIDENCE_REJECTED,
            "the authorization attestation was rejected by the evidence "
            "domain (%s: %s)"
            % (getattr(error, "reason", "evidence-error"), error),
        ) from error


# ---------------------------------------------------------------------------
# The credential-lifecycle hardening (rotation discipline)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CredentialLifecyclePolicy:
    """The deterministic credential rotation policy: every ACTIVE
    credential must rotate within ``rotation_deadline_seconds`` of its
    activation; the grace window bounds the overdue tolerance; at
    most ``max_active_credentials`` ACTIVE credentials may exist per
    node (integer arithmetic; injected instants only)."""

    rotation_deadline_seconds: int
    grace_seconds: int
    max_active_credentials: int

    def __post_init__(self) -> None:
        for label, value in (
            ("rotation_deadline_seconds", self.rotation_deadline_seconds),
            ("grace_seconds", self.grace_seconds),
            ("max_active_credentials", self.max_active_credentials),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise IdentityConvergenceError(
                    IdentityConvergenceReasonCode.INVALID_INPUT,
                    "credential policy %s must be an int" % label,
                )
            if value < 1:
                raise IdentityConvergenceError(
                    IdentityConvergenceReasonCode.INVALID_INPUT,
                    "credential policy %s must be >= 1" % label,
                )


@dataclass
class CredentialLifecycleState:
    """The deterministic per-credential lifecycle bookkeeping over
    injected instants (activation instants per credential reference;
    sorted iteration)."""

    _activated_at: Dict[str, str] = field(default_factory=dict)
    _statuses: Dict[str, str] = field(default_factory=dict)

    def activation(self, credential_ref: str) -> Optional[str]:
        return self._activated_at.get(credential_ref)

    def status(self, credential_ref: str) -> str:
        return self._statuses.get(
            credential_ref, str(LifecycleState.PROVISIONED.value)
        )

    def references(self) -> Tuple[str, ...]:
        return tuple(sorted(set(self._activated_at) | set(self._statuses)))

    def record_activation(
        self, credential_ref: str, activated_at: str, status: str
    ) -> None:
        """Record one activation observation (the WORK-004 lifecycle
        vocabulary; deterministic overwrite-free append: a recorded
        activation is immutable)."""
        _require_reference(credential_ref, "credential reference")
        _require_instant(activated_at, "activation instant")
        if status not in tuple(state.value for state in LifecycleState):
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.VOCABULARY,
                "credential status %r is outside the WORK-004 lifecycle "
                "vocabulary (cited by reference)" % status,
            )
        if credential_ref in self._activated_at:
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.LIFECYCLE_ILLEGAL,
                "credential %r already has a recorded activation "
                "(append-only bookkeeping)" % credential_ref,
            )
        self._activated_at[credential_ref] = activated_at
        self._statuses[credential_ref] = status

    def record_status(self, credential_ref: str, status: str) -> None:
        """Record one status observation (rotation/expiry/revocation
        transitions; append-only)."""
        _require_reference(credential_ref, "credential reference")
        if status not in tuple(state.value for state in LifecycleState):
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.VOCABULARY,
                "credential status %r is outside the WORK-004 lifecycle "
                "vocabulary (cited by reference)" % status,
            )
        self._statuses[credential_ref] = status

    def to_dict(self) -> Dict[str, Dict[str, str]]:
        return {
            ref: {
                "activated_at": self._activated_at.get(ref, ""),
                "status": self.status(ref),
            }
            for ref in self.references()
        }

    @classmethod
    def from_dict(cls, data: object) -> "CredentialLifecycleState":
        if not isinstance(data, dict):
            raise IdentityConvergenceError(
                IdentityConvergenceReasonCode.INVALID_INPUT,
                "credential lifecycle material must be a mapping",
            )
        state = cls()
        for ref, entry in sorted(data.items()):
            if not isinstance(entry, dict):
                raise IdentityConvergenceError(
                    IdentityConvergenceReasonCode.INVALID_INPUT,
                    "credential lifecycle entry must be a mapping",
                )
            activated_at = str(entry.get("activated_at", ""))
            status = str(entry.get("status", ""))
            if activated_at:
                state.record_activation(ref, activated_at, status)
            else:
                state.record_status(ref, status)
        return state


@dataclass(frozen=True)
class CredentialVerdict:
    """One typed credential-lifecycle verdict."""

    credential_ref: str
    verdict: str
    detail: str


def evaluate_credential_lifecycle(
    policy: CredentialLifecyclePolicy,
    state: CredentialLifecycleState,
    credential_ref: str,
    at_instant: str,
) -> CredentialVerdict:
    """The deterministic rotation-deadline gate over INJECTED instants.

    Verdicts (the frozen vocabulary): ``ok``; ``rotation-due`` (the
    deadline passed but the grace window holds); ``rotation-overdue``
    (past grace — the credential must not be relied on);
    ``expired``/``revoked`` (the terminal WORK-004 states, observed
    verbatim); ``not-active`` (provisioned/rotating/superseded — only
    an ACTIVE credential is usable); ``too-many-active`` (the policy
    bound would be exceeded — checked by the caller's register path
    through :func:`active_credential_count`).  Fail-closed on
    malformed input (typed errors)."""
    if not isinstance(policy, CredentialLifecyclePolicy):
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.INVALID_INPUT,
            "evaluate_credential_lifecycle requires a "
            "CredentialLifecyclePolicy",
        )
    if not isinstance(state, CredentialLifecycleState):
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.INVALID_INPUT,
            "evaluate_credential_lifecycle requires a "
            "CredentialLifecycleState",
        )
    _require_reference(credential_ref, "credential reference")
    _require_instant(at_instant, "evaluation instant")
    status = state.status(credential_ref)
    if status == str(LifecycleState.REVOKED.value):
        return CredentialVerdict(credential_ref, "revoked", "")
    if status == str(LifecycleState.EXPIRED.value):
        return CredentialVerdict(credential_ref, "expired", "")
    if status != str(LifecycleState.ACTIVE.value):
        return CredentialVerdict(
            credential_ref, "not-active",
            "the credential status is %r (only an ACTIVE credential is "
            "usable; fail closed)" % status,
        )
    activated_at = state.activation(credential_ref)
    if activated_at is None:
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.LIFECYCLE_ILLEGAL,
            "credential %r is ACTIVE without a recorded activation "
            "(inconsistent bookkeeping; fail closed)" % credential_ref,
        )
    activated = parse_instant(activated_at)
    observed = parse_instant(at_instant)
    elapsed = int((observed - activated).total_seconds())
    if elapsed <= policy.rotation_deadline_seconds:
        return CredentialVerdict(credential_ref, "ok", "")
    if elapsed <= policy.rotation_deadline_seconds + policy.grace_seconds:
        return CredentialVerdict(
            credential_ref, "rotation-due",
            "rotation is due (%d seconds elapsed of the %d deadline)"
            % (elapsed, policy.rotation_deadline_seconds),
        )
    return CredentialVerdict(
        credential_ref, "rotation-overdue",
        "rotation is %d seconds past the deadline (grace %d exceeded)"
        % (elapsed - policy.rotation_deadline_seconds, policy.grace_seconds),
    )


def active_credential_count(state: CredentialLifecycleState) -> int:
    """The deterministic ACTIVE count (the policy bound's input)."""
    if not isinstance(state, CredentialLifecycleState):
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.INVALID_INPUT,
            "active_credential_count requires a CredentialLifecycleState",
        )
    return sum(
        1
        for ref in state.references()
        if state.status(ref) == str(LifecycleState.ACTIVE.value)
    )


def enforce_active_credential_bound(
    policy: CredentialLifecyclePolicy,
    state: CredentialLifecycleState,
) -> None:
    """Fail closed when the policy's ACTIVE bound is exceeded (typed
    ``too-many-active``)."""
    count = active_credential_count(state)
    if count > policy.max_active_credentials:
        raise IdentityConvergenceError(
            IdentityConvergenceReasonCode.TOO_MANY_ACTIVE,
            "%d ACTIVE credentials exceed the policy bound %d"
            % (count, policy.max_active_credentials),
        )


__all__ = [
    # vocabularies
    "IDENTITY_CONVERGENCE_PREFIX",
    "AUTHORIZATION_VERDICTS",
    "CREDENTIAL_VERDICTS",
    # typed errors
    "IdentityConvergenceError",
    "IdentityConvergenceReasonCode",
    # the principal authorization binding (M002 by reference)
    "PrincipalAuthorization",
    "build_principal_authorization",
    "check_principal_authorization",
    # the revocation hardening
    "AuthorizationRevocation",
    "authorization_revocation",
    "AuthorizationRegistry",
    # the closed-loop seam (M005 by reference)
    "authorization_attestation",
    # the credential-lifecycle hardening
    "CredentialLifecyclePolicy",
    "CredentialLifecycleState",
    "CredentialVerdict",
    "evaluate_credential_lifecycle",
    "active_credential_count",
    "enforce_active_credential_bound",
]
