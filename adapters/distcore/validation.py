"""ADCOS distributed-core adapter input validators (WORK-024).

Pure, stdlib-only validators for the distributed-core domain value
types.  No vendor SDK, no Open5GS/N3IWF daemon API, no UPF element
management, no cryptographic material.  The validators check SHAPES
only (generic IP-gateway and 5G UPF reference shapes as DATA); they
never decode, decrypt, or store credentials (LOCK-023: credential slot
NAMES only, never material).

Standards leverage (LOCK-018, mirroring the W017/W018/W019/W021/W022/
W023 discipline): the validators use the Python standard library ``re``
module for shape checking -- the stdlib is a standard implementation,
not a reinvention.  3GPP TS 23.501 (UPF/N6/PDU-session reference
shapes) and TS 23.548 (edge/local UPF placement) appear as DATA with
citations in docstrings; no invented gateway or crypto primitive
exists in this module.

The W024 identity invariant is enforced here
(:func:`assert_ref_session_separation`):

    ADCOS session_id != breakout gateway identity != ordinary path
    identity (the WORK-011 path fingerprint, consumed as DATA) !=
    breakout identity != allocation identity != external gateway
    identifier

The technology refs (``distcore:gateway:<hex>`` /
``distcore:breakout:<hex>`` / ``distcore:binding:<hex>`` /
``distcore:decision:<hex>`` / ``distcore:alloc:<hex>``) are OPAQUE
handles minted over canonical content; the underlying gateway element,
UPF N4/N6 state, vendor daemon, and N3IWF identity material is NEVER
modeled (adapter-side opaque).

NOTE (selftest audit): this module is the enforcement-vocabulary file
-- its forbidden-token list exists to REJECT secret-like text.  The
WORK-024 selftest's credential scan excludes this file from its own
scan (the tokens appear here as rejection vocabulary, never as data),
mirroring how the WORK-019/021/022/023 selftests treat their
validators.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from .errors import DistCoreError, DistCoreReasonCode

#: Opaque technology-ref grammar (WORK-024): ``distcore:<kind>:<32
#: lowercase hex>``, kind in {gateway, breakout, binding, decision,
#: alloc}.  The hex is the leading 128 bits of a SHA-256 digest over
#: canonical content (mirrors the fivegc/wifi/backhaul/mesh ref
#: convention).  Structurally disjoint from the WORK-012 session_id
#: (``sha256:<64 hex>``), the WORK-011 path fingerprint
#: (``sha256:<64 hex>``), and the WORK-004 NodeID (``adcos:node:...``)
#: by construction.
_OPAQUE_REF_KINDS: Tuple[str, ...] = (
    "gateway", "breakout", "binding", "decision", "alloc",
)
_OPAQUE_REF_PATTERN = re.compile(
    r"^distcore:(gateway|breakout|binding|decision|alloc):[0-9a-f]{32}$"
)

#: WORK-011 path-reference grammar (consumed as DATA).  A routing path
#: id is a content-derived ``sha256:<64 hex>`` fingerprint (WORK-011
#: ``routing.model.derive_path_id``); the distributed core CONSUMES it
#: as the breakout path's existing reference and never re-scores or
#: re-selects paths (no second routing authority -- the local-first
#: composition chooses among REGISTERED ordinary Paths by policy DATA,
#: never by re-derivation).
_PATH_REF_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

#: WORK-012 session-id grammar (the SACRED identity, consumed as
#: DATA).  The distributed core never mints, reinterprets, or replaces
#: a session_id; it is carried verbatim from the WORK-012 authority.
_SESSION_REF_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

#: WORK-004 NodeID grammar (consumed as opaque DATA).  The distributed
#: core never creates node identities; gateway/endpoint node ids are
#: WORK-004 material carried as DATA across the seam.
_NODE_ID_PATTERN = re.compile(
    r"^adcos:node:((?:[a-z0-9][a-z0-9-]*\.)+[a-z0-9][a-z0-9-]*):([0-9a-f]{64})$"
)

#: Gateway name (1..64 printable ASCII, no control characters).
_GATEWAY_NAME_PATTERN = re.compile(r"^[\x21-\x7e][\x20-\x7e]{0,63}$")

#: External gateway identifier (the integration seam).  1..128
#: printable ASCII.  MUST NOT match any ADCOS identifier grammar
#: (NodeID / path fingerprint / family ref prefixes) so an external
#: identifier can never collapse onto a core identity axis --
#: external identifiers are DATA, never identity.
_EXTERNAL_ID_PATTERN = re.compile(r"^[\x21-\x7e][\x20-\x7e]{0,127}$")
_EXTERNAL_ID_FORBIDDEN_PREFIXES: Tuple[str, ...] = (
    "adcos:",
    "distcore:",
    "sha256:",
    "mesh:",
    "backhaul:",
    "wifi:",
    "fivegc:",
    "transport:",
)

#: Policy locality label grammar (the WORK-010 locality vocabulary
#: carried as DATA -- e.g. a ``village-A`` locality label).  1..64
#: printable ASCII; never parsed for identity semantics.
_LOCALITY_LABEL_PATTERN = re.compile(r"^[\x21-\x7e][\x20-\x7e]{0,63}$")

#: Breakout-mode classification -- frozen vocabulary (the policy
#: determination consumed as DATA).  ``local`` keeps traffic local via
#: a local breakout gateway (the frozen
#: ``capability.core.local-breakout`` registry id classifies the same
#: concept); ``remote`` breaks out via a remote gateway/provider
#: behind the WORK-019/021/022 seams.  The distributed core RECORDS
#: the mode policy determined; it never invents one (no second policy
#: authority).
_BREAKOUT_MODE_VALUES: Tuple[str, ...] = ("local", "remote")

#: Gateway role classification -- frozen vocabulary (registry DATA,
#: never core branching).  ``ip-gateway`` (the WORK-018 generic IP
#: gateway seam), ``upf`` (the WORK-019 5G UPF seam), ``wifi-gateway``
#: (the WORK-021 non-3GPP seam), ``backhaul-gateway`` (the WORK-022
#: backhaul seam).  A gateway is a ROLE, not an identity: the same
#: node may host several gateway roles, and no core state machine
#: branches on these labels.
_GATEWAY_ROLE_VALUES: Tuple[str, ...] = (
    "ip-gateway", "upf", "wifi-gateway", "backhaul-gateway",
)

#: Evidence source-class vocabulary (DATA mirroring the WORK-007
#: SourceClass and the WORK-023 mesh HopEvidence classes):
#: ``direct-observation`` for gateway claims the serving node itself
#: observed; ``remote-claim`` for claims an upstream node REPORTED and
#: this boundary merely carries.  A remote-claim gateway NEVER
#: silently becomes direct-observed (provenance is preserved, never
#: upgraded).
_EVIDENCE_SOURCE_VALUES: Tuple[str, ...] = (
    "direct-observation", "remote-claim",
)

#: LOCK-023 -- credential-like text rejection vocabulary.  The token
#: list covers gateway/UPF management credentials (management-plane
#: community strings and shared secrets, UPF N4 shared keys, gateway
#: admin passphrases, N3IWF IPsec/IKE material).  A string carrying
#: any of these fragments is rejected so an implementation cannot
#: smuggle secret material through names, labels, or refs.  Matching
#: runs against the lowered text AND a separator-normalized form
#: (hyphen/underscore/dot/space collapsed to ``-``), so both
#: ``shared_secret`` and ``shared-secret`` spellings are caught.
_CREDENTIAL_LIKE_FORBIDDEN: Tuple[str, ...] = (
    "private_key", "secret_key", "password", "passphrase", "token",
    "api_key", "shared_secret", "community_string", "psk",
    "pre_shared_key", "preshared", "sim_pin", "session_key",
    "n4_key", "upf_key", "protection_key", "gateway_password",
    "ike_secret", "ipsec_key", "snmp_community", "mgmt_secret",
)

_SEPARATOR_RUN = re.compile(r"[-_.\s]+")

#: RFC 3339 UTC instant shape (WORK-003 grammar, shape check only).
_INSTANT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"
)


def _normalized(text: str) -> str:
    return _SEPARATOR_RUN.sub("-", text.lower())


def validate_opaque_ref(value: str, expected_kind: Optional[str] = None) -> str:
    """Validate an opaque distributed-core technology ref.

    Grammar: ``distcore:(gateway|breakout|binding|decision|alloc):
    [0-9a-f]{32}`` (hex lowercase, 32 digits).  When ``expected_kind``
    is given, the ref's kind segment must match it (a gateway
    candidate carries a ``gateway`` ref, a breakout binding a
    ``breakout`` ref, an allocation an ``alloc`` ref).  Raises
    :class:`DistCoreError` for any other shape.  The ref is an OPAQUE
    handle: the underlying gateway element, UPF N4/N6, vendor daemon,
    or N3IWF identity material is NEVER carried in it.
    """
    if not isinstance(value, str) or not value:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "opaque ref must be a non-empty string",
        )
    match = _OPAQUE_REF_PATTERN.fullmatch(value)
    if match is None:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "opaque ref must match "
            "distcore:(gateway|breakout|binding|decision|alloc):"
            "<32 lowercase hex>",
        )
    if expected_kind is not None:
        if expected_kind not in _OPAQUE_REF_KINDS:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "expected_kind must be one of %s"
                % (list(_OPAQUE_REF_KINDS),),
            )
        if match.group(1) != expected_kind:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "opaque ref %s must be of kind %r" % (value, expected_kind),
            )
    return value


def validate_path_ref(value: str) -> str:
    """Validate a WORK-011 path reference (opaque DATA).

    Grammar: ``sha256:[0-9a-f]{64}`` (the ordinary path fingerprint
    minted by ``routing.model.derive_path_id``).  The distributed core
    never re-derives or re-scores paths.
    """
    if not isinstance(value, str) or not value:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "path ref must be a non-empty string",
        )
    if _PATH_REF_PATTERN.fullmatch(value) is None:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "path ref must match sha256:<64 lowercase hex> (the "
            "ordinary WORK-011 path fingerprint)",
        )
    return value


def validate_session_ref(value: str) -> str:
    """Validate a WORK-012 session id (the SACRED identity, DATA).

    Grammar: ``sha256:[0-9a-f]{64}``.  The distributed core never
    mints, reinterprets, or replaces a session_id -- it is stored
    EXACTLY as the WORK-012 authority issued it.
    """
    if not isinstance(value, str) or not value:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "session id must be a non-empty string",
        )
    if _SESSION_REF_PATTERN.fullmatch(value) is None:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "session id must match sha256:<64 lowercase hex> (the "
            "WORK-012 content-derived session identity)",
        )
    return value


def validate_node_id(value: str) -> str:
    """Validate a WORK-004 NodeID (opaque DATA)."""
    if not isinstance(value, str) or not value:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "node id must be a non-empty string",
        )
    if _NODE_ID_PATTERN.fullmatch(value) is None:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "node id must match adcos:node:<profile>:<64 lowercase hex>",
        )
    return value


def validate_gateway_name(value: str) -> str:
    """Validate a gateway name (1..64 printable ASCII)."""
    if not isinstance(value, str) or not value:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "gateway name must be a non-empty string",
        )
    if _GATEWAY_NAME_PATTERN.fullmatch(value) is None:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "gateway name must be 1..64 printable ASCII characters",
        )
    reject_credential_like_text(value, label="gateway name")
    return value


def validate_external_gateway_id(value: str) -> str:
    """Validate an external gateway identifier (integration seam DATA).

    1..128 printable ASCII, and MUST NOT match any ADCOS identifier
    grammar (NodeID / path / session / family ref prefixes) so an
    external identifier can never collapse onto a core identity axis:
    external identifiers are DATA, never identity.
    """
    if not isinstance(value, str) or not value:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "external gateway id must be a non-empty string",
        )
    if _EXTERNAL_ID_PATTERN.fullmatch(value) is None:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "external gateway id must be 1..128 printable ASCII "
            "characters",
        )
    for prefix in _EXTERNAL_ID_FORBIDDEN_PREFIXES:
        if value.startswith(prefix):
            raise DistCoreError(
                DistCoreReasonCode.ACCESS_SESSION_COLLAPSE,
                "external gateway id %r must not start with %r "
                "(external identifiers are DATA, never identity)"
                % (value, prefix),
            )
    reject_credential_like_text(value, label="external gateway id")
    return value


def validate_locality_label(value: str) -> str:
    """Validate a policy locality label (WORK-010 vocabulary as DATA).

    1..64 printable ASCII.  Locality labels are the WORK-010 policy
    vocabulary the composition root supplies (e.g. from
    ``PolicyContext.locality_labels``); the distributed core records
    them as provenance and never interprets their semantics.
    """
    if not isinstance(value, str) or not value:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "locality label must be a non-empty string",
        )
    if _LOCALITY_LABEL_PATTERN.fullmatch(value) is None:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "locality label must be 1..64 printable ASCII characters",
        )
    reject_credential_like_text(value, label="locality label")
    return value


def validate_breakout_mode(value: str) -> str:
    """Validate a breakout mode (the policy determination, as DATA)."""
    if not isinstance(value, str) or value not in _BREAKOUT_MODE_VALUES:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "breakout mode %r must be one of %s (policy determines "
            "local vs remote breakout; the distributed core records "
            "the determination, never invents one)"
            % (value, list(_BREAKOUT_MODE_VALUES)),
        )
    return value


def validate_gateway_role(value: str) -> str:
    """Validate a gateway role classification (registry DATA)."""
    if not isinstance(value, str) or value not in _GATEWAY_ROLE_VALUES:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "gateway role %r must be one of %s (a gateway is a ROLE, "
            "not an identity; registry DATA, never core branching)"
            % (value, list(_GATEWAY_ROLE_VALUES)),
        )
    return value


def validate_evidence_source(value: str) -> str:
    """Validate an evidence source class (provenance DATA)."""
    if not isinstance(value, str) or value not in _EVIDENCE_SOURCE_VALUES:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "evidence source class %r must be one of %s (the "
            "WORK-007-mirroring provenance vocabulary, carried as DATA)"
            % (value, list(_EVIDENCE_SOURCE_VALUES)),
        )
    return value


def validate_claim_digest(value: str) -> str:
    """Validate a gateway claim digest (64 lowercase hex)."""
    if not isinstance(value, str) or not value:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "claim digest must be a non-empty string",
        )
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "claim digest must be 64 lowercase hex characters "
            "(SHA-256 over the canonical gateway claim content)",
        )
    return value


def validate_policy_decision_id(value: str) -> str:
    """Validate a WORK-010 policy decision id (64 lowercase hex)."""
    if not isinstance(value, str) or not value:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "policy decision id must be a non-empty string",
        )
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "policy decision id must be 64 lowercase hex characters "
            "(the WORK-010 content-derived decision fingerprint)",
        )
    return value


def assert_ref_session_separation(ref: str, session_id: str) -> None:
    """Assert the W024 identity invariant: a distributed-core ref must
    never embed WORK-012 session material (and vice versa).

    Both directions are checked over >=16-hex fragments (the collision
    threshold): a ``distcore:*`` ref carrying a 16+ hex fragment of the
    session_id (or a session_id carrying a fragment of a ref) is an
    identity collapse and fails closed with
    ``ACCESS_SESSION_COLLAPSE``.
    """
    if not isinstance(ref, str) or not isinstance(session_id, str):
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "ref and session id must be strings",
        )
    hex_run = re.compile(r"[0-9a-f]{16,}")
    for fragment in hex_run.findall(session_id):
        if fragment in ref:
            raise DistCoreError(
                DistCoreReasonCode.ACCESS_SESSION_COLLAPSE,
                "distributed-core ref embeds WORK-012 session "
                "material (identity collapse); the session_id is "
                "SACRED and never appears in adapter-side refs",
            )
    for fragment in hex_run.findall(ref):
        if fragment in session_id:
            raise DistCoreError(
                DistCoreReasonCode.ACCESS_SESSION_COLLAPSE,
                "session id embeds distributed-core ref material "
                "(identity collapse); breakout identity is mutable "
                "adapter-side state, never session identity",
            )


def reject_credential_like_text(text: str, *, label: str = "text") -> None:
    """Reject credential-like text (LOCK-023).

    Matches against the lowered text and a separator-normalized form
    (with the TOKENS normalized identically), so ``shared_secret``,
    ``shared-secret``, ``shared.secret`` and ``shared secret`` are
    all caught.
    """
    if not isinstance(text, str):
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "%s must be a string" % label,
        )
    lowered = text.lower()
    normalized = _normalized(text)
    for token in _CREDENTIAL_LIKE_FORBIDDEN:
        token_normalized = _normalized(token)
        if token in lowered or token_normalized in normalized:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "%s carries credential-like fragment %r (LOCK-023: "
                "secret material never crosses the seam)"
                % (label, token),
            )


def validate_credential_slot_name(value: str) -> str:
    """Validate a credential slot NAME (LOCK-023: names only, never
    material).

    Grammar: 1..64 printable ASCII; credential-LIKE text is rejected
    (the slot name must not itself be secret-shaped).
    """
    if not isinstance(value, str) or not value:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "credential slot name must be a non-empty string",
        )
    if _GATEWAY_NAME_PATTERN.fullmatch(value) is None:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "credential slot name must be 1..64 printable ASCII "
            "characters",
        )
    reject_credential_like_text(value, label="credential slot name")
    return value


def validate_instant(value: str, *, label: str = "instant") -> str:
    """Validate an RFC 3339 UTC instant string (WORK-003 grammar,
    shape check only -- no wall clock exists anywhere in this layer)."""
    if not isinstance(value, str) or not value:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    if _INSTANT_PATTERN.fullmatch(value) is None:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "%s must match the RFC 3339 UTC grammar "
            "YYYY-MM-DDTHH:MM:SS(.ffffff)?Z" % label,
        )
    return value


def validate_capacity_bps(value: int) -> int:
    """Validate a gateway/admission capacity in bits/second (WORK-008
    base units; 0 is ADMITTED and contributes NO allocatable capacity
    -- the WORK-022 zero/unknown port-speed fail-closed lesson)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "capacity must be an integer (bits/second)",
        )
    if value < 0 or value > 2 ** 40:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "capacity must be within 0..2^40 bits/second (0 admits the "
            "gateway but contributes NO allocatable capacity)",
        )
    return value


__all__ = [
    "validate_opaque_ref",
    "validate_path_ref",
    "validate_session_ref",
    "validate_node_id",
    "validate_gateway_name",
    "validate_external_gateway_id",
    "validate_locality_label",
    "validate_breakout_mode",
    "validate_gateway_role",
    "validate_evidence_source",
    "validate_claim_digest",
    "validate_policy_decision_id",
    "assert_ref_session_separation",
    "reject_credential_like_text",
    "validate_credential_slot_name",
    "validate_instant",
    "validate_capacity_bps",
]
