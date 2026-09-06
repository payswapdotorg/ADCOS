"""ADCOS provider onboarding domain model (WORK-057).

The WORK-057 integration layer over the existing authorities. The
onboarding lifecycle

    registration -> operator/domain identity binding -> scoped
    credential issuance -> adapter declaration/certification ->
    capability/resource declaration -> service/commercial profile
    binding -> eligibility/policy evaluation -> federation proposal
    -> explicit acceptance -> active federated membership ->
    suspension/revocation/offboarding

is a DETERMINISTIC, AUDITABLE FOLD over an append-only command
journal. The fold composes the existing authorities; it never
duplicates them.

Authority boundaries (the layering contract):

- **Federation stays WORK-015.** The onboarding layer drives
  ``FederationStore`` through its public API only (domains,
  relationships, grants, events). No federation vocabulary value is
  added; onboarding data rides as opaque references.
- **Identity stays WORK-004.** Operator identity is a canonical
  NodeID held by validated reference; the application id is a
  content-derived fingerprint, not a second NodeID grammar.
- **Policy stays WORK-010 / eligibility stays WORK-045.** The
  eligibility gate CONSUMES tamper-evident decisions (an explicit
  policy ALLOW matching declared references; an eligible
  connectivity-domain decision record). Onboarding never evaluates
  policy and never confers eligibility.
- **Capabilities stay WORK-005 / resources stay WORK-008.**
  Declarations are claims with provenance, validity, and expiry,
  carried as references; they never become reachability truth.
- **Adapter declarations stay WORK-016.** Certification evidence
  (``adapters.certification``) is consumed as data; provider
  implementations stay behind the adapter boundary.
- **Version compatibility stays WORK-029.** Mixed-version admission
  delegates to ``upgrade.compatibility.negotiate_protocol_profile``;
  incompatible peers fail closed, never silently reinterpreted.
- **No settlement authority.** Commercial/service bindings are
  opaque references only (P7 discipline).

Onboarding can NEVER create connectivity, session, path, route,
transport, usage, payment, or settlement state: structurally, the
layer writes only its own journal and composes the federation store
plus injected read-only records.

Determinism: content-derived ids over canonical JSON (empty at
construction means "derive it"; a supplied non-empty id MUST match
-- tamper evidence at construction AND deserialization); injected
RFC 3339 UTC instants only; no wall-clock, no randomness, no UUIDs,
no network; sorted iteration everywhere (PYTHONHASHSEED-safe);
secrets never stored or journaled (LOCK-023-style guards).
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Mapping, Tuple

from identity.node_id import NodeIdError, parse_node_id
from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

# ----------------------------------------------------------------------
# Error and reason vocabulary (onboarding-local; adding a value is a
# deliberate vocabulary change on this WORK-057 surface)
# ----------------------------------------------------------------------


class OnboardingError(ValueError):
    """Fail-closed onboarding error with a stable machine-readable
    ``code`` and deterministic ``detail`` (secret material is never
    echoed)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class OnboardingReason:
    # lifecycle successes (one per accepted command kind)
    REGISTERED = "registered"
    IDENTITY_BOUND = "identity-bound"
    CREDENTIAL_ISSUED = "credential-issued"
    CREDENTIAL_REVOKED = "credential-revoked"
    ADAPTER_CERTIFIED = "adapter-certified"
    ADAPTER_REJECTED = "adapter-rejected"
    DECLARED = "declared"
    DECLARATION_WITHDRAWN = "declaration-withdrawn"
    PROFILE_BOUND = "profile-bound"
    ELIGIBILITY_GRANTED = "eligibility-granted"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    MEMBERSHIP_ACTIVE = "membership-active"
    MEMBERSHIP_SUSPENDED = "membership-suspended"
    MEMBERSHIP_RESUMED = "membership-resumed"
    REVOKED = "revoked"
    OFFBOARDED = "offboarded"
    PROPOSAL_CANCELLED = "proposal-cancelled"
    DUPLICATE = "duplicate"

    # fail-closed codes
    INVALID_INPUT = "invalid-input"
    UNKNOWN_APPLICATION = "unknown-application"
    APPLICATION_TERMINAL = "application-terminal"
    INVALID_TRANSITION = "invalid-transition"
    PRECONDITION_UNMET = "precondition-unmet"
    KEY_PROOF_INVALID = "key-proof-invalid"
    CREDENTIAL_INVALID = "credential-invalid"
    CREDENTIAL_REVOKED_CODE = "credential-revoked"
    CREDENTIAL_EXPIRED = "credential-expired"
    CREDENTIAL_SCOPE = "credential-scope"
    SEQUENCE_CONFLICT = "sequence-conflict"
    SEQUENCE_GAP = "sequence-gap"
    REPLAY_STALE = "replay-stale"
    JOURNAL_TAMPER = "journal-tamper"
    DECLARATION_INVALID = "declaration-invalid"
    PROFILE_INVALID = "profile-invalid"
    POLICY_DENIED = "policy-denied"
    POLICY_TAMPERED = "policy-tampered"
    ELIGIBILITY_DENIED = "eligibility-denied"
    ELIGIBILITY_INVALID = "eligibility-invalid"
    VERSION_INCOMPATIBLE = "version-incompatible"
    PEER_UNREGISTERED = "peer-unregistered"
    PEER_IDENTITY_MISMATCH = "peer-identity-mismatch"
    DOMAIN_ERROR = "domain-error"
    RELATIONSHIP_ERROR = "relationship-error"
    SECRET_MATERIAL = "secret-material"
    ACCESS_TECHNOLOGY_LEAKAGE = "access-technology-leakage"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.REGISTERED,
            cls.IDENTITY_BOUND,
            cls.CREDENTIAL_ISSUED,
            cls.CREDENTIAL_REVOKED,
            cls.ADAPTER_CERTIFIED,
            cls.ADAPTER_REJECTED,
            cls.DECLARED,
            cls.DECLARATION_WITHDRAWN,
            cls.PROFILE_BOUND,
            cls.ELIGIBILITY_GRANTED,
            cls.PROPOSED,
            cls.ACCEPTED,
            cls.MEMBERSHIP_ACTIVE,
            cls.MEMBERSHIP_SUSPENDED,
            cls.MEMBERSHIP_RESUMED,
            cls.REVOKED,
            cls.OFFBOARDED,
            cls.PROPOSAL_CANCELLED,
            cls.DUPLICATE,
            cls.INVALID_INPUT,
            cls.UNKNOWN_APPLICATION,
            cls.APPLICATION_TERMINAL,
            cls.INVALID_TRANSITION,
            cls.PRECONDITION_UNMET,
            cls.KEY_PROOF_INVALID,
            cls.CREDENTIAL_INVALID,
            cls.CREDENTIAL_REVOKED_CODE,
            cls.CREDENTIAL_EXPIRED,
            cls.CREDENTIAL_SCOPE,
            cls.SEQUENCE_CONFLICT,
            cls.SEQUENCE_GAP,
            cls.REPLAY_STALE,
            cls.JOURNAL_TAMPER,
            cls.DECLARATION_INVALID,
            cls.PROFILE_INVALID,
            cls.POLICY_DENIED,
            cls.POLICY_TAMPERED,
            cls.ELIGIBILITY_DENIED,
            cls.ELIGIBILITY_INVALID,
            cls.VERSION_INCOMPATIBLE,
            cls.PEER_UNREGISTERED,
            cls.PEER_IDENTITY_MISMATCH,
            cls.DOMAIN_ERROR,
            cls.RELATIONSHIP_ERROR,
            cls.SECRET_MATERIAL,
            cls.ACCESS_TECHNOLOGY_LEAKAGE,
        )


# ----------------------------------------------------------------------
# Application lifecycle (frozen table)
# ----------------------------------------------------------------------


class OnboardingState:
    """Provider onboarding application lifecycle (the required
    WORK-057 lifecycle, one state per completed stage)."""

    REGISTERED = "registered"
    IDENTITY_BOUND = "identity-bound"
    CREDENTIALS_ISSUED = "credentials-issued"
    ADAPTERS_CERTIFIED = "adapters-certified"
    DECLARED = "declared"
    PROFILE_BOUND = "profile-bound"
    ELIGIBILITY_GRANTED = "eligibility-granted"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"  # terminal
    OFFBOARDED = "offboarded"  # terminal
    CANCELLED = "cancelled"  # terminal

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.REGISTERED,
            cls.IDENTITY_BOUND,
            cls.CREDENTIALS_ISSUED,
            cls.ADAPTERS_CERTIFIED,
            cls.DECLARED,
            cls.PROFILE_BOUND,
            cls.ELIGIBILITY_GRANTED,
            cls.PROPOSED,
            cls.ACCEPTED,
            cls.ACTIVE,
            cls.SUSPENDED,
            cls.REVOKED,
            cls.OFFBOARDED,
            cls.CANCELLED,
        )


ONBOARDING_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    OnboardingState.REGISTERED: frozenset({OnboardingState.IDENTITY_BOUND, OnboardingState.REVOKED}),
    OnboardingState.IDENTITY_BOUND: frozenset(
        {OnboardingState.CREDENTIALS_ISSUED, OnboardingState.REVOKED}
    ),
    OnboardingState.CREDENTIALS_ISSUED: frozenset(
        {OnboardingState.ADAPTERS_CERTIFIED, OnboardingState.REVOKED}
    ),
    OnboardingState.ADAPTERS_CERTIFIED: frozenset(
        {OnboardingState.DECLARED, OnboardingState.REVOKED}
    ),
    OnboardingState.DECLARED: frozenset({OnboardingState.PROFILE_BOUND, OnboardingState.REVOKED}),
    OnboardingState.PROFILE_BOUND: frozenset(
        {OnboardingState.ELIGIBILITY_GRANTED, OnboardingState.REVOKED}
    ),
    OnboardingState.ELIGIBILITY_GRANTED: frozenset(
        {OnboardingState.PROPOSED, OnboardingState.REVOKED}
    ),
    OnboardingState.PROPOSED: frozenset(
        {OnboardingState.ACCEPTED, OnboardingState.REVOKED, OnboardingState.CANCELLED}
    ),
    OnboardingState.ACCEPTED: frozenset({OnboardingState.ACTIVE, OnboardingState.REVOKED}),
    OnboardingState.ACTIVE: frozenset(
        {OnboardingState.SUSPENDED, OnboardingState.REVOKED, OnboardingState.OFFBOARDED}
    ),
    OnboardingState.SUSPENDED: frozenset(
        {OnboardingState.ACTIVE, OnboardingState.REVOKED, OnboardingState.OFFBOARDED}
    ),
    OnboardingState.REVOKED: frozenset(),
    OnboardingState.OFFBOARDED: frozenset(),
    OnboardingState.CANCELLED: frozenset(),
}

#: states from which the application is still live (non-terminal)
ONBOARDING_LIVE_STATES = frozenset(
    state for state, targets in ONBOARDING_TRANSITIONS.items() if targets
)


def onboarding_transition_is_legal(previous: str, new: str) -> bool:
    return new in ONBOARDING_TRANSITIONS.get(previous, frozenset())


# ----------------------------------------------------------------------
# Command vocabulary (frozen) and credential scope vocabulary
# ----------------------------------------------------------------------


class OnboardingCommandKind:
    REGISTER_APPLICATION = "register-application"
    BIND_IDENTITY = "bind-identity"
    ISSUE_CREDENTIAL = "issue-credential"
    REVOKE_CREDENTIAL = "revoke-credential"
    CERTIFY_ADAPTER = "certify-adapter"
    DECLARE_CAPABILITY = "declare-capability"
    DECLARE_RESOURCE = "declare-resource"
    WITHDRAW_DECLARATION = "withdraw-declaration"
    BIND_COMMERCIAL_PROFILE = "bind-commercial-profile"
    EVALUATE_ELIGIBILITY = "evaluate-eligibility"
    PROPOSE_FEDERATION = "propose-federation"
    ACCEPT_FEDERATION = "accept-federation"
    ACTIVATE_MEMBERSHIP = "activate-membership"
    SUSPEND_MEMBERSHIP = "suspend-membership"
    RESUME_MEMBERSHIP = "resume-membership"
    CANCEL_PROPOSAL = "cancel-proposal"
    REVOKE_APPLICATION = "revoke-application"
    OFFBOARD_APPLICATION = "offboard-application"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.REGISTER_APPLICATION,
            cls.BIND_IDENTITY,
            cls.ISSUE_CREDENTIAL,
            cls.REVOKE_CREDENTIAL,
            cls.CERTIFY_ADAPTER,
            cls.DECLARE_CAPABILITY,
            cls.DECLARE_RESOURCE,
            cls.WITHDRAW_DECLARATION,
            cls.BIND_COMMERCIAL_PROFILE,
            cls.EVALUATE_ELIGIBILITY,
            cls.PROPOSE_FEDERATION,
            cls.ACCEPT_FEDERATION,
            cls.ACTIVATE_MEMBERSHIP,
            cls.SUSPEND_MEMBERSHIP,
            cls.RESUME_MEMBERSHIP,
            cls.CANCEL_PROPOSAL,
            cls.REVOKE_APPLICATION,
            cls.OFFBOARD_APPLICATION,
        )


class OnboardingCredentialScope:
    """Least-authority onboarding credential scopes (frozen five).
    No scope implies another; there is no superuser scope."""

    PROFILE_DECLARE = "onboarding.profile.declare"
    ADAPTER_CERTIFY = "onboarding.adapter.certify"
    CREDENTIAL_ISSUE = "onboarding.credential.issue"
    FEDERATION_PROPOSE = "onboarding.federation.propose"
    FEDERATION_MANAGE = "onboarding.federation.manage"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.PROFILE_DECLARE,
            cls.ADAPTER_CERTIFY,
            cls.CREDENTIAL_ISSUE,
            cls.FEDERATION_PROPOSE,
            cls.FEDERATION_MANAGE,
        )


#: required credential scope per command kind (register-application
#: is an identity claim and needs no credential; bind-identity and the
#: bootstrap credential issuance authenticate with the operator key
#: proof instead -- proof of possession, never a stored secret).
COMMAND_REQUIRED_SCOPE: Dict[str, str] = {
    OnboardingCommandKind.ISSUE_CREDENTIAL: OnboardingCredentialScope.CREDENTIAL_ISSUE,
    OnboardingCommandKind.REVOKE_CREDENTIAL: OnboardingCredentialScope.CREDENTIAL_ISSUE,
    OnboardingCommandKind.CERTIFY_ADAPTER: OnboardingCredentialScope.ADAPTER_CERTIFY,
    OnboardingCommandKind.DECLARE_CAPABILITY: OnboardingCredentialScope.PROFILE_DECLARE,
    OnboardingCommandKind.DECLARE_RESOURCE: OnboardingCredentialScope.PROFILE_DECLARE,
    OnboardingCommandKind.WITHDRAW_DECLARATION: OnboardingCredentialScope.PROFILE_DECLARE,
    OnboardingCommandKind.BIND_COMMERCIAL_PROFILE: OnboardingCredentialScope.PROFILE_DECLARE,
    OnboardingCommandKind.EVALUATE_ELIGIBILITY: OnboardingCredentialScope.FEDERATION_PROPOSE,
    OnboardingCommandKind.PROPOSE_FEDERATION: OnboardingCredentialScope.FEDERATION_PROPOSE,
    OnboardingCommandKind.ACCEPT_FEDERATION: OnboardingCredentialScope.FEDERATION_MANAGE,
    OnboardingCommandKind.ACTIVATE_MEMBERSHIP: OnboardingCredentialScope.FEDERATION_MANAGE,
    OnboardingCommandKind.SUSPEND_MEMBERSHIP: OnboardingCredentialScope.FEDERATION_MANAGE,
    OnboardingCommandKind.RESUME_MEMBERSHIP: OnboardingCredentialScope.FEDERATION_MANAGE,
    OnboardingCommandKind.CANCEL_PROPOSAL: OnboardingCredentialScope.FEDERATION_MANAGE,
    OnboardingCommandKind.REVOKE_APPLICATION: OnboardingCredentialScope.FEDERATION_MANAGE,
    OnboardingCommandKind.OFFBOARD_APPLICATION: OnboardingCredentialScope.FEDERATION_MANAGE,
}

#: commands that accept the operator key proof in place of a scoped
#: credential (bootstrap authentication: proof of possession of the
#: operator identity key material; the material itself is never
#: stored or journaled, only its proof digest).
COMMAND_ACCEPTS_KEY_PROOF = frozenset(
    {
        OnboardingCommandKind.BIND_IDENTITY,
        OnboardingCommandKind.ISSUE_CREDENTIAL,
    }
)


# ----------------------------------------------------------------------
# Leakage guards (repo-convention local copies)
# ----------------------------------------------------------------------

_SECRET_HINTS = (
    "private_key",
    "secret_key",
    "priv_key",
    "password",
    "token",
    "credential_secret",
    "subscriber_secret",
    "modem_secret",
)

_FORBIDDEN_TOKENS = (
    "5g",
    "6g",
    "nr",
    "lte",
    "wifi",
    "wi-fi",
    "3g",
    "4g",
    "cellular",
    "satellite",
    "mesh",
    "fiber",
    "ethernet",
    "vendor",
    "ran",
    "cn",
    "bearer",
    "apn",
    "imsi",
    "imei",
    "ssid",
    "n3iwf",
    "quic",
    "tls",
    "chipset",
)

_FORBIDDEN_PATTERNS = tuple(
    re.compile(r"(?:^|[^a-z0-9])%s(?:$|[^a-z0-9])" % re.escape(token))
    for token in _FORBIDDEN_TOKENS
)


def _reject_secret_material(document: object, label: str) -> None:
    if isinstance(document, Mapping):
        for key, value in document.items():
            key_text = key if isinstance(key, str) else str(key)
            if any(hint in key_text.lower() for hint in _SECRET_HINTS):
                raise OnboardingError(
                    OnboardingReason.SECRET_MATERIAL,
                    "%s: mapping key %r looks like secret material" % (label, key_text),
                )
            _reject_secret_material(value, label)
    elif isinstance(document, (list, tuple)):
        for item in document:
            _reject_secret_material(item, label)


def _reject_forbidden_tokens(value: str, label: str) -> None:
    lowered = value.lower()
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(lowered) is not None:
            raise OnboardingError(
                OnboardingReason.ACCESS_TECHNOLOGY_LEAKAGE,
                "%s: forbidden access-technology/vendor token in free text" % label,
            )


def validate_free_text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise OnboardingError(OnboardingReason.INVALID_INPUT, "%s must be a string" % label)
    if not value:
        raise OnboardingError(OnboardingReason.INVALID_INPUT, "%s must be non-empty" % label)
    if len(value) > 256:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT, "%s exceeds 256 characters" % label
        )
    _reject_forbidden_tokens(value, label)
    return value


def validate_instant(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT, "%s must be a non-empty string" % label
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise OnboardingError(OnboardingReason.INVALID_INPUT, "%s: %s" % (label, error)) from None
    return value


def validate_string_refs(refs: object, label: str) -> Tuple[str, ...]:
    if not isinstance(refs, tuple):
        raise OnboardingError(OnboardingReason.INVALID_INPUT, "%s must be a tuple" % label)
    seen = set()
    for item in refs:
        if not isinstance(item, str) or not item:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "%s entries must be non-empty strings" % label
            )
        if len(item) > 256:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "%s entries exceed 256 characters" % label
            )
        seen.add(item)
    return tuple(sorted(seen))


def validate_policy_references(references: object, label: str) -> Tuple[Tuple[str, int], ...]:
    if not isinstance(references, tuple):
        raise OnboardingError(OnboardingReason.INVALID_INPUT, "%s must be a tuple" % label)
    seen = set()
    for item in references:
        if not isinstance(item, tuple) or len(item) != 2:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "%s entries must be (set_id, version) pairs" % label,
            )
        set_id, version = item
        if not isinstance(set_id, str) or not set_id:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "%s set ids must be non-empty strings" % label
            )
        _reject_forbidden_tokens(set_id, "%s set id" % label)
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "%s versions must be integers >= 1" % label
            )
        seen.add((set_id, version))
    return tuple(sorted(seen))


def validate_node_id_reference(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT, "%s must be a non-empty string" % label
        )
    try:
        canonical = parse_node_id(value).text
    except NodeIdError as error:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT, "%s must be a canonical NodeID: %s" % (label, error)
        ) from None
    if canonical != value:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT, "%s must be the canonical NodeID text form" % label
        )
    return canonical


def _validate_identity_public_key(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise OnboardingError(OnboardingReason.INVALID_INPUT, "%s must be a string" % label)
    lowered = value.lower()
    if lowered != value:
        raise OnboardingError(OnboardingReason.INVALID_INPUT, "%s must be lowercase" % label)
    if len(value) < 2 or len(value) % 2 != 0:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT, "%s must be even-length hex (>= 2 chars)" % label
        )
    try:
        int(value, 16)
    except ValueError:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT, "%s must be hexadecimal" % label
        ) from None
    return value


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except CanonicalizationError as error:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_fingerprint(document: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(document, "identity document")).hexdigest()


# ----------------------------------------------------------------------
# Credential secret derivation (developer API house style: derived
# never stored -- the journal holds only the digest)
# ----------------------------------------------------------------------

_ONBOARDING_SECRET_PREFIX = "onbsec_"
_ONBOARDING_ID_NAMESPACE = "adc-os-provider-onboarding"


def derive_onboarding_credential_secret(
    issuance_key: bytes, application_id: str, scope: str, sequence: int
) -> str:
    """Deterministically derive one onboarding credential secret.

    The secret is derived from (issuance key, application, scope,
    sequence) exactly like the WORK-046 credential discipline: it is
    returned to the operator ONCE at issuance and never stored --
    only ``secret_digest`` is persisted. Identical inputs always
    derive the identical secret (determinism requirement).
    """
    if not isinstance(issuance_key, (bytes, bytearray)) or not issuance_key:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT, "issuance key must be non-empty bytes"
        )
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT, "credential sequence must be an integer >= 1"
        )
    message = canonical_json_bytes(
        {
            "namespace": _ONBOARDING_ID_NAMESPACE,
            "application_id": application_id,
            "scope": scope,
            "sequence": sequence,
        }
    )
    return _ONBOARDING_SECRET_PREFIX + hmac.new(
        bytes(issuance_key), message, hashlib.sha256
    ).hexdigest()


def secret_digest(secret: str) -> str:
    """Digest stored/journaled in place of a credential secret."""
    if not isinstance(secret, str) or not secret:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT, "secret must be a non-empty string"
        )
    return "sha256:" + hashlib.sha256(secret.encode("utf-8")).hexdigest()


def derive_key_proof_digest(key_material: bytes, application_id: str) -> str:
    """Proof-of-possession digest for the operator identity key
    material (the material itself is NEVER stored or journaled)."""
    if not isinstance(key_material, (bytes, bytearray)) or not key_material:
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT, "key material must be non-empty bytes"
        )
    proof = hmac.new(bytes(key_material), application_id.encode("utf-8"), hashlib.sha256)
    return "sha256:" + hashlib.sha256(proof.hexdigest().encode("ascii")).hexdigest()


# ----------------------------------------------------------------------
# ProviderApplication (the fold's per-application projection record)
# ----------------------------------------------------------------------


def derive_application_id(
    operator_reference: str,
    identity_public_key: str,
    operator_node_id: str,
    provider_id: str,
    protocol_major: int,
    protocol_max_minor: int,
) -> str:
    """Content-derived application identity over explicit identity
    material only (the WORK-007 house style -- NOT a second NodeID
    grammar). Display name, lifecycle, and references are admin
    metadata and are not part of identity."""
    document = {
        "application_kind": "adcos:provider-onboarding-application",
        "namespace": _ONBOARDING_ID_NAMESPACE,
        "operator_reference": operator_reference,
        "identity_public_key": identity_public_key,
        "operator_node_id": operator_node_id,
        "provider_id": provider_id,
        "protocol_major": int(protocol_major),
        "protocol_max_minor": int(protocol_max_minor),
    }
    _reject_secret_material(document, "application identity document")
    return _derive_fingerprint(document)


@dataclass(frozen=True)
class ProviderApplication:
    """One provider onboarding application projection.

    ``key_proof_digest`` is the stored proof-of-possession digest for
    the operator identity key material (the material itself never
    enters the repository, the journal, or this record's
    serialization). ``domain_id``/``relationship_id``/``membership``
    are references to the OWNING authorities (federation), recorded
    after the corresponding commands are accepted.
    """

    application_id: str
    operator_reference: str
    identity_public_key: str
    operator_node_id: str
    provider_id: str
    display_name: str
    protocol_major: int
    protocol_max_minor: int
    key_proof_digest: str
    policy_references: Tuple[Tuple[str, int], ...]
    common_profile_major: int
    common_profile_minor: int
    created_at: str
    lifecycle_state: str
    domain_id: str = ""
    relationship_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.application_id, str):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "application_id must be a string"
            )
        expected = derive_application_id(
            self.operator_reference,
            self.identity_public_key,
            self.operator_node_id,
            self.provider_id,
            self.protocol_major,
            self.protocol_max_minor,
        )
        if self.application_id == "":
            object.__setattr__(self, "application_id", expected)
        elif self.application_id != expected:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "application id %r does not match the content-derived identity %r"
                % (self.application_id, expected),
            )
        validate_free_text(self.operator_reference, "operator_reference")
        _validate_identity_public_key(self.identity_public_key, "identity_public_key")
        validate_node_id_reference(self.operator_node_id, "operator_node_id")
        validate_free_text(self.provider_id, "provider_id")
        validate_free_text(self.display_name, "display_name")
        for label, value in (
            ("protocol_major", self.protocol_major),
            ("protocol_max_minor", self.protocol_max_minor),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT, "%s must be an integer >= 0" % label
                )
        if not isinstance(self.key_proof_digest, str) or not self.key_proof_digest.startswith(
            "sha256:"
        ):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "key_proof_digest must be a sha256: digest (never the key material)",
            )
        object.__setattr__(
            self,
            "policy_references",
            validate_policy_references(self.policy_references, "policy_references"),
        )
        validate_instant(self.created_at, "created_at")
        if self.lifecycle_state not in OnboardingState.values():
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "lifecycle state %r is not an onboarding state" % (self.lifecycle_state,),
            )
        for label, value in (("domain_id", self.domain_id), ("relationship_id", self.relationship_id)):
            if not isinstance(value, str):
                raise OnboardingError(OnboardingReason.INVALID_INPUT, "%s must be a string" % label)
            if value:
                if not value.startswith("sha256:"):
                    raise OnboardingError(
                        OnboardingReason.INVALID_INPUT,
                        "%s must be an opaque sha256: federation reference" % label,
                    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "application_id": self.application_id,
            "operator_reference": self.operator_reference,
            "identity_public_key": self.identity_public_key,
            "operator_node_id": self.operator_node_id,
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "protocol": {
                "major": self.protocol_major,
                "max_minor": self.protocol_max_minor,
            },
            "key_proof_digest": self.key_proof_digest,
            "policy_references": [
                {"set_id": set_id, "version": version}
                for set_id, version in self.policy_references
            ],
            "common_profile": {
                "major": self.common_profile_major,
                "minor": self.common_profile_minor,
            },
            "created_at": self.created_at,
            "lifecycle_state": self.lifecycle_state,
            "domain_id": self.domain_id,
            "relationship_id": self.relationship_id,
        }

    @classmethod
    def from_mapping(cls, data: object) -> "ProviderApplication":
        if not isinstance(data, Mapping):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "application record must be a mapping"
            )
        _reject_secret_material(dict(data), "application record")
        protocol = data.get("protocol", {})
        common = data.get("common_profile", {})
        policy_references = tuple(
            (item["set_id"], item["version"]) for item in data.get("policy_references", ())
        )
        return cls(
            application_id=data.get("application_id", ""),
            operator_reference=data["operator_reference"],
            identity_public_key=data["identity_public_key"],
            operator_node_id=data["operator_node_id"],
            provider_id=data["provider_id"],
            display_name=data.get("display_name", ""),
            protocol_major=int(protocol["major"]),
            protocol_max_minor=int(protocol["max_minor"]),
            key_proof_digest=data["key_proof_digest"],
            policy_references=policy_references,
            common_profile_major=int(common.get("major", 0)),
            common_profile_minor=int(common.get("minor", 0)),
            created_at=data["created_at"],
            lifecycle_state=data["lifecycle_state"],
            domain_id=data.get("domain_id", ""),
            relationship_id=data.get("relationship_id", ""),
        )


# ----------------------------------------------------------------------
# OnboardingCredential
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class OnboardingCredential:
    """One scoped least-authority onboarding credential.

    The secret is NEVER a field of this record: only its digest is
    stored (the secret is handed to the operator exactly once, at
    issuance). Expiry is evaluated at each authorization instant --
    it is not a lifecycle state.
    """

    credential_reference: str
    application_id: str
    scope: str
    sequence: int
    status: str
    valid_from: str
    valid_until: str
    issued_at: str
    revoked_at: str
    secret_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.credential_reference, str):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "credential_reference must be a string"
            )
        expected = self._derive_reference()
        if self.credential_reference == "":
            object.__setattr__(self, "credential_reference", expected)
        elif self.credential_reference != expected:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "credential reference %r does not match the content-derived identity %r"
                % (self.credential_reference, expected),
            )
        if self.scope not in OnboardingCredentialScope.values():
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "credential scope %r is unknown" % (self.scope,)
            )
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "credential sequence must be an integer >= 1"
            )
        if self.status not in ("active", "revoked"):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "credential status %r is unknown" % (self.status,)
            )
        if self.status == "revoked" and not self.revoked_at:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "a revoked credential must carry revoked_at"
            )
        if self.status == "active" and self.revoked_at:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "an active credential cannot carry revoked_at"
            )
        for label, value in (
            ("valid_from", self.valid_from),
            ("valid_until", self.valid_until),
            ("issued_at", self.issued_at),
        ):
            validate_instant(value, label)
        if self.revoked_at:
            validate_instant(self.revoked_at, "revoked_at")
        if self.valid_until < self.valid_from:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "valid_until must not precede valid_from"
            )
        if not isinstance(self.secret_digest, str) or not self.secret_digest.startswith("sha256:"):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "secret_digest must be a sha256: digest (the secret itself is never stored)",
            )

    def _content_document(self) -> Dict[str, Any]:
        return {
            "credential_kind": "adcos:provider-onboarding-credential",
            "application_id": self.application_id,
            "scope": self.scope,
            "sequence": self.sequence,
            "secret_digest": self.secret_digest,
        }

    def _derive_reference(self) -> str:
        return _derive_fingerprint(self._content_document())

    def is_active_at(self, evaluation_instant: str) -> bool:
        """Status + evaluated validity window at an injected instant
        (inclusive at both ends)."""
        instant = validate_instant(evaluation_instant, "evaluation_instant")
        if self.status != "active":
            return False
        return self.valid_from <= instant <= self.valid_until

    def public_dict(self) -> Dict[str, Any]:
        """The secret-free public form (the ONLY serialized form)."""
        document = {
            "credential_reference": self.credential_reference,
            "application_id": self.application_id,
            "scope": self.scope,
            "sequence": self.sequence,
            "status": self.status,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "issued_at": self.issued_at,
            "secret_digest": self.secret_digest,
        }
        if self.revoked_at:
            document["revoked_at"] = self.revoked_at
        return document

    @classmethod
    def from_mapping(cls, data: object) -> "OnboardingCredential":
        if not isinstance(data, Mapping):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "credential record must be a mapping"
            )
        _reject_secret_material(dict(data), "credential record")
        return cls(
            credential_reference=data.get("credential_reference", ""),
            application_id=data["application_id"],
            scope=data["scope"],
            sequence=int(data["sequence"]),
            status=data["status"],
            valid_from=data["valid_from"],
            valid_until=data["valid_until"],
            issued_at=data["issued_at"],
            revoked_at=data.get("revoked_at", ""),
            secret_digest=data["secret_digest"],
        )


# ----------------------------------------------------------------------
# OnboardingDeclaration (capability/resource claims with provenance)
# ----------------------------------------------------------------------


class DeclarationKind:
    CAPABILITY = "capability"
    RESOURCE = "resource"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.CAPABILITY, cls.RESOURCE)


@dataclass(frozen=True)
class OnboardingDeclaration:
    """One provider capability/resource declaration (a CLAIM with
    provenance, validity, and expiry -- never reachability truth;
    the owning authorities remain WORK-005/WORK-008)."""

    declaration_id: str
    application_id: str
    declaration_kind: str
    subject_reference: str
    subject_owner_node_id: str
    provenance: str
    source_reference: str
    evidence_refs: Tuple[str, ...]
    declared_at: str
    sequence: int
    valid_from: str
    expires_at: str
    withdrawn_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.declaration_id, str):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "declaration_id must be a string"
            )
        expected = self._derive_declaration_id()
        if self.declaration_id == "":
            object.__setattr__(self, "declaration_id", expected)
        elif self.declaration_id != expected:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "declaration id %r does not match the content-derived identity %r"
                % (self.declaration_id, expected),
            )
        if self.declaration_kind not in DeclarationKind.values():
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "declaration kind %r is unknown" % (self.declaration_kind,),
            )
        validate_free_text(self.subject_reference, "subject_reference")
        validate_node_id_reference(self.subject_owner_node_id, "subject_owner_node_id")
        validate_free_text(self.provenance, "provenance")
        validate_free_text(self.source_reference, "source_reference")
        object.__setattr__(
            self, "evidence_refs", validate_string_refs(self.evidence_refs, "evidence_refs")
        )
        if not self.evidence_refs:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "a declaration without evidence references is a bare claim, not a declaration",
            )
        validate_instant(self.declared_at, "declared_at")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "declaration sequence must be an integer >= 1"
            )
        validate_instant(self.valid_from, "valid_from")
        validate_instant(self.expires_at, "expires_at")
        if self.expires_at < self.valid_from:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "expires_at must not precede valid_from"
            )
        if self.withdrawn_at:
            validate_instant(self.withdrawn_at, "withdrawn_at")

    def _content_document(self) -> Dict[str, Any]:
        return {
            "declaration_kind": "adcos:provider-onboarding-declaration",
            "application_id": self.application_id,
            "declaration_kind_value": self.declaration_kind,
            "subject_reference": self.subject_reference,
            "subject_owner_node_id": self.subject_owner_node_id,
            "provenance": self.provenance,
            "source_reference": self.source_reference,
            "evidence_refs": list(self.evidence_refs),
            "declared_at": self.declared_at,
            "sequence": self.sequence,
        }

    def _derive_declaration_id(self) -> str:
        return _derive_fingerprint(self._content_document())

    def is_withdrawn(self) -> bool:
        return bool(self.withdrawn_at)

    def is_live_at(self, evaluation_instant: str) -> bool:
        """Live = not withdrawn and inside the evaluated validity
        window (inclusive) at an injected instant."""
        instant = validate_instant(evaluation_instant, "evaluation_instant")
        if self.withdrawn_at:
            return False
        return self.valid_from <= instant <= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        document = {
            "declaration_id": self.declaration_id,
            "application_id": self.application_id,
            "declaration_kind": self.declaration_kind,
            "subject_reference": self.subject_reference,
            "subject_owner_node_id": self.subject_owner_node_id,
            "provenance": self.provenance,
            "source_reference": self.source_reference,
            "evidence_refs": list(self.evidence_refs),
            "declared_at": self.declared_at,
            "sequence": self.sequence,
            "validity": {
                "valid_from": self.valid_from,
                "expires_at": self.expires_at,
            },
        }
        if self.withdrawn_at:
            document["validity"]["withdrawn_at"] = self.withdrawn_at
        return document

    @classmethod
    def from_mapping(cls, data: object) -> "OnboardingDeclaration":
        if not isinstance(data, Mapping):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "declaration record must be a mapping"
            )
        _reject_secret_material(dict(data), "declaration record")
        validity = data.get("validity", {})
        return cls(
            declaration_id=data.get("declaration_id", ""),
            application_id=data["application_id"],
            declaration_kind=data["declaration_kind"],
            subject_reference=data["subject_reference"],
            subject_owner_node_id=data["subject_owner_node_id"],
            provenance=data["provenance"],
            source_reference=data["source_reference"],
            evidence_refs=tuple(data.get("evidence_refs", ())),
            declared_at=data["declared_at"],
            sequence=int(data["sequence"]),
            valid_from=validity["valid_from"],
            expires_at=validity["expires_at"],
            withdrawn_at=validity.get("withdrawn_at", ""),
        )


# ----------------------------------------------------------------------
# OnboardingProfileBinding (commercial references only)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class OnboardingProfileBinding:
    """One service/commercial profile binding -- opaque REFERENCES to
    the existing commercial authorities. Settlement stays a typed
    opaque reference: no billing, pricing, token, payment, or
    settlement code path exists anywhere in this package."""

    binding_id: str
    application_id: str
    service_profile_ref: str
    commercial_policy_ref: str
    settlement_reference: str
    evidence_refs: Tuple[str, ...]
    bound_at: str
    sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.binding_id, str):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "binding_id must be a string"
            )
        expected = self._derive_binding_id()
        if self.binding_id == "":
            object.__setattr__(self, "binding_id", expected)
        elif self.binding_id != expected:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "binding id %r does not match the content-derived identity %r"
                % (self.binding_id, expected),
            )
        validate_free_text(self.service_profile_ref, "service_profile_ref")
        if not self.service_profile_ref.startswith("adcos:"):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "service_profile_ref must be an adcos: opaque reference",
            )
        validate_free_text(self.commercial_policy_ref, "commercial_policy_ref")
        if not self.commercial_policy_ref.startswith("adcos:"):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "commercial_policy_ref must be an adcos: opaque reference",
            )
        if not isinstance(self.settlement_reference, str) or not self.settlement_reference:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "settlement_reference must be a non-empty opaque reference",
            )
        if not self.settlement_reference.startswith("adcos:settlement:"):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "settlement_reference must be an adcos:settlement: opaque typed reference",
            )
        object.__setattr__(
            self, "evidence_refs", validate_string_refs(self.evidence_refs, "evidence_refs")
        )
        if not self.evidence_refs:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "a profile binding without evidence references is not auditable",
            )
        validate_instant(self.bound_at, "bound_at")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "binding sequence must be an integer >= 1"
            )

    def _content_document(self) -> Dict[str, Any]:
        return {
            "binding_kind": "adcos:provider-onboarding-profile-binding",
            "application_id": self.application_id,
            "service_profile_ref": self.service_profile_ref,
            "commercial_policy_ref": self.commercial_policy_ref,
            "settlement_reference": self.settlement_reference,
            "evidence_refs": list(self.evidence_refs),
            "bound_at": self.bound_at,
            "sequence": self.sequence,
        }

    def _derive_binding_id(self) -> str:
        return _derive_fingerprint(self._content_document())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "application_id": self.application_id,
            "service_profile_ref": self.service_profile_ref,
            "commercial_policy_ref": self.commercial_policy_ref,
            "settlement_reference": {
                "reference": self.settlement_reference,
                "opaque": True,
            },
            "evidence_refs": list(self.evidence_refs),
            "bound_at": self.bound_at,
            "sequence": self.sequence,
        }

    @classmethod
    def from_mapping(cls, data: object) -> "OnboardingProfileBinding":
        if not isinstance(data, Mapping):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "profile binding record must be a mapping"
            )
        _reject_secret_material(dict(data), "profile binding record")
        settlement = data.get("settlement_reference", "")
        if isinstance(settlement, Mapping):
            settlement = settlement.get("reference", "")
        return cls(
            binding_id=data.get("binding_id", ""),
            application_id=data["application_id"],
            service_profile_ref=data["service_profile_ref"],
            commercial_policy_ref=data["commercial_policy_ref"],
            settlement_reference=settlement,
            evidence_refs=tuple(data.get("evidence_refs", ())),
            bound_at=data["bound_at"],
            sequence=int(data["sequence"]),
        )


# ----------------------------------------------------------------------
# OnboardingCommandRecord (the append-only journal record)
# ----------------------------------------------------------------------

#: statuses a journaled command can carry. A duplicate attempt is
#: detected by its content-derived id and NEVER journaled (idempotent
#: replay is stateless by definition); only material outcomes -- accepted
#: effects and deterministic rejections -- are append-only records.
COMMAND_STATUS_APPENDED = "appended"
COMMAND_STATUS_REJECTED = "rejected"
COMMAND_STATUSES = (COMMAND_STATUS_APPENDED, COMMAND_STATUS_REJECTED)


def _normalize_payload_value(value: object) -> object:
    """Recursively normalize a payload value to the JSON-safe form
    (tuples become lists; canonical JSON rejects floats)."""
    if isinstance(value, tuple):
        return [_normalize_payload_value(item) for item in value]
    if isinstance(value, list):
        return [_normalize_payload_value(item) for item in value]
    if isinstance(value, Mapping):
        return {key: _normalize_payload_value(item) for key, item in value.items()}
    if isinstance(value, bool) or isinstance(value, int) or isinstance(value, str):
        return value
    if value is None:
        return None
    raise OnboardingError(
        OnboardingReason.INVALID_INPUT,
        "payload values must be strings, integers, booleans, lists, mappings, or None "
        "(got %r)" % (type(value).__name__,),
    )


def derive_command_id(
    application_id: str,
    command_kind: str,
    command_key: str,
    issued_at: str,
    effective_at: str,
    actor: str,
    credential_reference: str,
    payload: Tuple[Tuple[str, Any], ...],
) -> str:
    """Content-derived command identity over the logical command
    content (kind, key, instants, actor, credential reference,
    payload) -- deliberately WITHOUT the journal-assigned sequence,
    so an operator retry of the same logical command derives the same
    id and is detected as an idempotent duplicate regardless of how
    many records the journal already holds."""
    document = {
        "command_kind": "adcos:provider-onboarding-command",
        "application_id": application_id,
        "command_kind_value": command_kind,
        "command_key": command_key,
        "issued_at": issued_at,
        "effective_at": effective_at,
        "actor": actor,
        "credential_reference": credential_reference,
        "payload": {key: value for key, value in payload},
    }
    _reject_secret_material(document, "command identity document")
    return _derive_fingerprint(document)


@dataclass(frozen=True)
class OnboardingCommandRecord:
    """One journaled onboarding command with its deterministic outcome.

    ``command_key`` is the operator-supplied idempotency key (one
    logical command per key per application). ``sequence`` is the
    journal-assigned per-application slot (0 means "assign at
    append"). The payload is JSON-safe and carries ONLY references
    and public data: secrets, key material, and decision objects are
    never journaled (their digests/references -- or, for the policy
    and eligibility gates, their fully public decision documents --
    are). ``status``/``reason_code`` are fold-derived: on recovery
    the fold recomputes them and a mismatch is ``journal-tamper``
    (fail closed; the only trusted-as-journaled outcomes are the
    secret-dependent authentication rejections, which cannot be
    re-derived without the secrets -- by design).
    """

    command_id: str
    application_id: str
    command_kind: str
    command_key: str
    sequence: int
    issued_at: str
    effective_at: str
    actor: str
    credential_reference: str
    payload: Tuple[Tuple[str, Any], ...]
    status: str
    reason_code: str
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.command_id, str):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "command_id must be a string"
            )
        if self.command_kind not in OnboardingCommandKind.values():
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "command kind %r is not an onboarding command" % (self.command_kind,),
            )
        validate_free_text(self.command_key, "command_key")
        if len(self.command_key) > 128:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "command_key exceeds 128 characters"
            )
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "command sequence must be a non-negative integer (0 = journal-assigned)",
            )
        validate_node_id_reference(self.actor, "actor")
        validate_instant(self.issued_at, "issued_at")
        validate_instant(self.effective_at, "effective_at")
        if self.credential_reference and not self.credential_reference.startswith("sha256:"):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "credential_reference must be an opaque sha256: reference (the secret is "
                "never journaled)",
            )
        if not isinstance(self.payload, tuple):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "payload must be a tuple of (key, value) pairs"
            )
        normalized = []
        for pair in self.payload:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT,
                    "payload entries must be (key, value) pairs",
                )
            key, value = pair
            if not isinstance(key, str) or not key:
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT, "payload keys must be non-empty strings"
                )
            normalized.append((key, _normalize_payload_value(value)))
        object.__setattr__(self, "payload", tuple(sorted(normalized, key=lambda item: item[0])))
        _reject_secret_material(
            {key: value for key, value in self.payload}, "command payload"
        )
        for key, value in self.payload:
            if isinstance(value, str):
                _reject_forbidden_tokens(value, "payload member %r" % (key,))
        if self.status not in COMMAND_STATUSES:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "command status %r is unknown" % (self.status,)
            )
        if self.reason_code not in OnboardingReason.values():
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "command reason code %r is not an onboarding reason" % (self.reason_code,),
            )
        validate_free_text(self.detail, "detail")
        expected = derive_command_id(
            self.application_id,
            self.command_kind,
            self.command_key,
            self.issued_at,
            self.effective_at,
            self.actor,
            self.credential_reference,
            self.payload,
        )
        if self.command_id == "":
            object.__setattr__(self, "command_id", expected)
        elif self.command_id != expected:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "command id %r does not match the content-derived identity %r"
                % (self.command_id, expected),
            )

    def content_document(self) -> Dict[str, Any]:
        return {
            "command_kind": "adcos:provider-onboarding-command",
            "application_id": self.application_id,
            "command_kind_value": self.command_kind,
            "command_key": self.command_key,
            "issued_at": self.issued_at,
            "effective_at": self.effective_at,
            "actor": self.actor,
            "credential_reference": self.credential_reference,
            "payload": {key: value for key, value in self.payload},
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "application_id": self.application_id,
            "command_kind": self.command_kind,
            "command_key": self.command_key,
            "sequence": self.sequence,
            "issued_at": self.issued_at,
            "effective_at": self.effective_at,
            "actor": self.actor,
            "credential_reference": self.credential_reference,
            "payload": {key: value for key, value in self.payload},
            "status": self.status,
            "reason_code": self.reason_code,
            "detail": self.detail,
        }

    @classmethod
    def from_mapping(cls, data: object) -> "OnboardingCommandRecord":
        if not isinstance(data, Mapping):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "command record must be a mapping"
            )
        _reject_secret_material(dict(data), "command record")
        payload = data.get("payload", {})
        if isinstance(payload, Mapping):
            payload_pairs = tuple(sorted(payload.items(), key=lambda item: item[0]))
        else:
            payload_pairs = tuple((item[0], item[1]) for item in payload)
        sequence = int(data["sequence"])
        if sequence < 1:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "a materialized journal record must carry its assigned sequence (>= 1)",
            )
        return cls(
            command_id=data.get("command_id", ""),
            application_id=data["application_id"],
            command_kind=data["command_kind"],
            command_key=data["command_key"],
            sequence=sequence,
            issued_at=data["issued_at"],
            effective_at=data["effective_at"],
            actor=data["actor"],
            credential_reference=data.get("credential_reference", ""),
            payload=payload_pairs,
            status=data["status"],
            reason_code=data["reason_code"],
            detail=data["detail"],
        )


__all__ = [
    "COMMAND_REQUIRED_SCOPE",
    "COMMAND_ACCEPTS_KEY_PROOF",
    "COMMAND_STATUS_APPENDED",
    "COMMAND_STATUS_REJECTED",
    "COMMAND_STATUSES",
    "ONBOARDING_LIVE_STATES",
    "ONBOARDING_TRANSITIONS",
    "DeclarationKind",
    "ProviderApplication",
    "OnboardingCommandKind",
    "OnboardingCommandRecord",
    "OnboardingCredential",
    "OnboardingCredentialScope",
    "OnboardingDeclaration",
    "OnboardingError",
    "OnboardingProfileBinding",
    "OnboardingReason",
    "OnboardingState",
    "derive_application_id",
    "derive_command_id",
    "derive_key_proof_digest",
    "derive_onboarding_credential_secret",
    "onboarding_transition_is_legal",
    "secret_digest",
    "validate_free_text",
    "validate_instant",
    "validate_node_id_reference",
    "validate_policy_references",
    "validate_string_refs",
]
