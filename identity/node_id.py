"""Stable, access-independent NodeID (spec/architecture.md section 6.2; LOCK-005).

NodeID is a durable identity reference with exactly one canonical text
representation:

    adcos:node:<profile_id>:<64 lowercase hex chars>

The digest is computed by the profile's declared derivation rule. The
only derivation rule registered at WORK-004 is ``sha256-domain-v1``:

    SHA-256(domain_separation || 0x00 || profile_id UTF-8 || 0x00 ||
            identity public key bytes)

where the identity public key is the STABLE identity-role public
material. Rotating operational keys never participate in derivation, so
key rotation and revocation never change a node's NodeID. The profile id
is embedded in the representation so cryptographic/profile choices are
explicit metadata rather than hidden implementation convention, and
future derivation profiles can be introduced without rewriting
identity-consuming code (NodeID consumers treat it as an opaque string).

NodeID is non-secret and may safely appear in ordinary protocol and
topology messages. It is NOT: public key bytes, a certificate blob, a
private key, SIM/IMSI, a modem identifier, a MAC address, a vendor
account id, or a trust decision.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Mapping, Optional

#: Domain separation source of truth: the derivation rule declared in the
#: identity-profile registry. Loaded via identity.profiles.
CANONICAL_PREFIX = "adcos:node"

_HEX_DIGITS = re.compile(r"[0-9a-f]")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
# Structural shape independent of the registry grammar (the profile
# segment must be at least two dotted lowercase segments).
_PROFILE_SEGMENT_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_NODE_ID_RE = re.compile(
    r"^adcos:node:((?:[a-z0-9][a-z0-9-]*\.)+[a-z0-9][a-z0-9-]*):([0-9a-f]{64})$"
)

# Kept for introspection/tests: hex charset check helper.


def _is_canonical_hex(value: str) -> bool:
    return bool(_DIGEST_RE.fullmatch(value)) and all(_HEX_DIGITS.match(c) for c in value)


class NodeIdError(ValueError):
    """Raised when a NodeID is malformed or derivation input is invalid."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class NodeID:
    """A stable node identity reference in canonical form."""

    profile_id: str
    digest_hex: str

    def __post_init__(self) -> None:
        if _NODE_ID_RE.fullmatch(self.text) is None:
            raise NodeIdError(
                "node-id",
                "canonical form violation for profile=%r digest=%r"
                % (self.profile_id, self.digest_hex),
            )

    @property
    def text(self) -> str:
        return "%s:%s:%s" % (CANONICAL_PREFIX, self.profile_id, self.digest_hex)

    def __str__(self) -> str:  # canonical text representation
        return self.text

    def __repr__(self) -> str:  # keeps secrets structurally impossible
        return "NodeID(%r)" % self.text


def derive_node_id(
    profile_id: str,
    identity_public_key: bytes,
    derivation_rule: str,
    domain_separation: str,
) -> NodeID:
    """Derive a NodeID from stable identity public material.

    ``derivation_rule`` and ``domain_separation`` come from the
    identity-profile registry (identity.profiles), keeping the
    construction data-driven. Only the ``sha256-domain-v1`` construction
    is implemented; callers dispatch on the declared rule via
    ``identity.profiles``.
    """
    if derivation_rule != "sha256-domain-v1":
        raise NodeIdError(
            "derivation",
            "unsupported derivation rule %r (registered rules are declared in "
            "spec/schemas/registries/identity-profile-registry.json)" % derivation_rule,
        )
    if not isinstance(identity_public_key, (bytes, bytearray)) or not identity_public_key:
        raise NodeIdError(
            "identity-key", "identity public key must be non-empty bytes"
        )
    if not isinstance(profile_id, str) or not profile_id:
        raise NodeIdError("profile", "profile_id must be a non-empty string")
    separator = b"\x00"
    digest = hashlib.sha256(
        domain_separation.encode("utf-8")
        + separator
        + profile_id.encode("utf-8")
        + separator
        + bytes(identity_public_key)
    ).hexdigest()
    return NodeID(profile_id=profile_id, digest_hex=digest)


def parse_node_id(value: object) -> NodeID:
    """Parse the canonical NodeID text form, failing closed.

    Non-canonical representations (uppercase hex, wrong prefix, wrong
    digest length, malformed profile segment, non-string input) are
    rejected — there is exactly one canonical representation and it
    round-trips without ambiguity.
    """
    if not isinstance(value, str):
        raise NodeIdError("node-id", "NodeID must be a string (found %s)" % type(value).__name__)
    match = _NODE_ID_RE.fullmatch(value)
    if match is None:
        raise NodeIdError(
            "node-id",
            "%r is not the canonical form 'adcos:node:<profile_id>:<64 lowercase hex>'"
            % (value[:96] + ("…" if len(value) > 96 else "")),
        )
    return NodeID(profile_id=match.group(1), digest_hex=match.group(2))
