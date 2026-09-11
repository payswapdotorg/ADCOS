"""M014 upgrade convergence — the converged-domain compatibility
surface (R7-CORE-001, DEC-0101).

The upgrade family's M014 harvest onto the Architecture 1.1
authority (the migration matrix: the compatibility-orchestration
family stays a COMPATIBILITY layer, never an authority): the WORK-029
protocol-profile negotiation and staged-upgrade ladder stay the
package's own frozen surface (consumed by reference from
:mod:`upgrade.compatibility` / :mod:`upgrade.model`); this module
adds the production-hardening surface the R7 charter's M014 scope
names — **compatibility across the CONVERGED 1.1 domain set**:

- :data:`CONVERGED_DOMAIN_SET` — the frozen Architecture 1.1 domain
  labels (the accepted child authorities plus the five M014
  production-federation domains), carried as DATA only;
- :class:`DomainVersion` — one converged domain's implementation
  version point (``MAJOR.MINOR``; the frozen additive-evolution
  grammar — each side speaks every minor up to its head);
- :func:`classify_domain_compatibility` — the deterministic
  mixed-version coexistence verdict per domain pair: ``compatible``
  (same major, the peer does not exceed the local additive head),
  ``additive-gap`` (same major, the peer carries NEWER additive
  minors the local side does not speak — disclosed, never silent),
  ``major-mismatch`` (NO fallback to a lower common major, no
  clamping — the family's frozen fail-closed discipline), and
  ``unknown-domain`` (a domain outside the frozen set fails closed);
- :func:`capability_compatibility` — the capability-id consultation
  through the REAL accepted capability registry (the M003-harvested
  ``capabilities.classify_capability_id`` authority — KNOWN /
  UNKNOWN_BUT_WELL_FORMED / INVALID, never re-declared here);
- :func:`negotiate_converged_compatibility` — the full deterministic
  report over two peers' converged-domain version sets (sorted
  domain iteration; byte-stable digest; the protocol profile
  delegation stays :mod:`upgrade.compatibility`'s own surface).

Boundaries (frozen): no peer authorization is answered here (trust
is the identity/federation boundary's business); no contract, offer,
plan, settlement or evidence semantics are interpreted here (the
domain labels are compatibility DATA — LOCK-101/117); the four
governance version kinds stay structurally distinct
(:class:`upgrade.model.VersionKind`); the Protocol Version line
stays the single source of truth consumed through
:mod:`protocol.versioning`.

Determinism (LOCK-119): canonical-JSON digests; injected instants
only; sorted iteration; typed fail-closed errors with stable codes;
no file access (the family is read-only over the frozen artifacts).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from protocol.canonicalization import canonical_json_bytes

from capabilities import classify_capability_id

from .errors import UpgradeError, UpgradeReasonCode

#: The namespaced digest prefix (content-derived only).
CONVERGENCE_PREFIX = "m014-upgrade"

#: The frozen Architecture 1.1 converged-domain set (the accepted
#: child authorities + the M014 production-federation domains —
#: compatibility DATA labels only; each domain's semantics stay its
#: own authority's business, never interpreted here).
CONVERGED_DOMAIN_SET: Tuple[str, ...] = (
    "adapters",
    "assurance",
    "client",
    "commercial",
    "contracts",
    "evidence",
    "executionplans",
    "federation",
    "identity",
    "offers",
    "replan",
    "scale",
    "upgrade",
)

#: The frozen domain-compatibility verdict vocabulary.
DOMAIN_COMPATIBILITY_VERDICTS: Tuple[str, ...] = (
    "compatible",
    "additive-gap",
    "major-mismatch",
    "unknown-domain",
    "local-missing",
    "peer-missing",
)

_SECRET_MARKERS = tuple(sorted((
    "private_key", "secret_key", "password", "passwd",
    "client_secret", "credential_secret", "api_key",
)))


def _require_domain(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s must be a non-empty domain label" % label,
        )
    if value not in CONVERGED_DOMAIN_SET:
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s %r is outside the frozen converged domain set (fail "
            "closed)" % (label, value),
        )
    lowered = value.lower()
    for marker in _SECRET_MARKERS:
        if marker in lowered:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "%s is secret-shaped material; secrets never enter "
                "compatibility metadata (LOCK-119)" % label,
            )
    return value


@dataclass(frozen=True)
class DomainVersion:
    """One converged domain's implementation version point (the
    ``MAJOR.MINOR`` additive-evolution grammar; integer arithmetic
    only; the kind is the Implementation Version line — the frozen
    four-kind taxonomy is never collapsed)."""

    domain: str
    major: int
    minor: int

    def __post_init__(self) -> None:
        _require_domain(self.domain, "domain version domain")
        for label, value in (("major", self.major), ("minor", self.minor)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "domain version %s must be an int" % label,
                )
            if value < 0:
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "domain version %s must be >= 0" % label,
                )

    def to_dict(self) -> Dict[str, object]:
        return {"domain": self.domain, "major": self.major, "minor": self.minor}

    @classmethod
    def from_dict(cls, data: object) -> "DomainVersion":
        if not isinstance(data, dict):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "domain version material must be a mapping",
            )
        return cls(
            domain=str(data.get("domain", "")),
            major=int(data.get("major", -1)),
            minor=int(data.get("minor", -1)),
        )


@dataclass(frozen=True)
class DomainCompatibilityVerdict:
    """One typed per-domain coexistence verdict."""

    domain: str
    verdict: str
    local_major: int
    local_minor: int
    peer_major: int
    peer_minor: int
    detail: str = ""

    def __post_init__(self) -> None:
        _require_domain(self.domain, "verdict domain")
        if self.verdict not in DOMAIN_COMPATIBILITY_VERDICTS:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "verdict %r is outside the frozen domain-compatibility "
                "vocabulary" % self.verdict,
            )

    def to_dict(self) -> Dict[str, object]:
        return {
            "domain": self.domain,
            "verdict": self.verdict,
            "local_major": self.local_major,
            "local_minor": self.local_minor,
            "peer_major": self.peer_major,
            "peer_minor": self.peer_minor,
            "detail": self.detail,
        }


def classify_domain_compatibility(
    local: DomainVersion, peer: DomainVersion
) -> DomainCompatibilityVerdict:
    """The deterministic mixed-version coexistence verdict for ONE
    converged domain (the family's frozen fail-closed discipline:
    incompatible majors have NO fallback, no clamping, no best-effort
    guess; additive minors are disclosed, never silently ignored)."""
    if not isinstance(local, DomainVersion) or not isinstance(
        peer, DomainVersion
    ):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "classify_domain_compatibility requires two DomainVersion "
            "records",
        )
    if local.domain != peer.domain:
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "domain mismatch: %r vs %r (one verdict per domain)" % (
                local.domain, peer.domain,
            ),
        )
    if local.major != peer.major:
        return DomainCompatibilityVerdict(
            domain=local.domain,
            verdict="major-mismatch",
            local_major=local.major,
            local_minor=local.minor,
            peer_major=peer.major,
            peer_minor=peer.minor,
            detail="majors differ (%d vs %d): there is NO fallback to a "
                   "lower common major (fail closed)"
                   % (local.major, peer.major),
        )
    if peer.minor > local.minor:
        return DomainCompatibilityVerdict(
            domain=local.domain,
            verdict="additive-gap",
            local_major=local.major,
            local_minor=local.minor,
            peer_major=peer.major,
            peer_minor=peer.minor,
            detail="the peer carries additive minors %d..%d the local "
                   "side does not speak (disclosed; interoperate on the "
                   "shared minor %d)" % (
                       local.minor + 1, peer.minor, local.minor,
                   ),
        )
    return DomainCompatibilityVerdict(
        domain=local.domain,
        verdict="compatible",
        local_major=local.major,
        local_minor=local.minor,
        peer_major=peer.major,
        peer_minor=peer.minor,
        detail="the shared major %d with the peer minor %d at or below "
               "the local additive head %d" % (
                   local.major, peer.minor, local.minor,
               ),
    )


def capability_compatibility(capability_id: object) -> str:
    """The capability-id consultation through the REAL accepted
    capability registry (the M003-harvested classification authority —
    KNOWN / UNKNOWN_BUT_WELL_FORMED / INVALID, never re-declared
    here; a compatibility statement is never truth, availability,
    authorization or trust)."""
    if not isinstance(capability_id, str) or not capability_id:
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "capability_compatibility requires a non-empty capability id",
        )
    lowered = capability_id.lower()
    for marker in _SECRET_MARKERS:
        if marker in lowered:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "capability id is secret-shaped material (LOCK-119)",
            )
    return classify_capability_id(capability_id)


@dataclass(frozen=True)
class ConvergedCompatibilityReport:
    """The deterministic full report over two peers' converged-domain
    version sets (sorted domain iteration; the protocol profile
    negotiation itself stays :mod:`upgrade.compatibility`'s own
    surface — this report classifies the DOMAIN lines only)."""

    local_id: str
    peer_id: str
    verdicts: Tuple[DomainCompatibilityVerdict, ...]

    def __post_init__(self) -> None:
        for label, value in (("local_id", self.local_id), ("peer_id", self.peer_id)):
            if not isinstance(value, str) or not value:
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "report %s must be a non-empty string" % label,
                )
        if not isinstance(self.verdicts, tuple) or any(
            not isinstance(item, DomainCompatibilityVerdict)
            for item in self.verdicts
        ):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "report verdicts must be a tuple of "
                "DomainCompatibilityVerdict records",
            )

    def digest(self) -> str:
        """The canonical report digest (byte-stable across runs and
        hash seeds)."""
        return hashlib.sha256(canonical_json_bytes({
            "local_id": self.local_id,
            "peer_id": self.peer_id,
            "verdicts": [verdict.to_dict() for verdict in self.verdicts],
        })).hexdigest()

    def by_domain(self) -> Dict[str, DomainCompatibilityVerdict]:
        return {verdict.domain: verdict for verdict in self.verdicts}

    def compatible(self) -> bool:
        """True iff NO domain pair fails closed (major mismatches and
        unknown domains refuse; additive gaps are disclosed but
        interoperate)."""
        return all(
            verdict.verdict in ("compatible", "additive-gap")
            for verdict in self.verdicts
        )


def negotiate_converged_compatibility(
    *,
    local_id: str,
    peer_id: str,
    local_versions: Sequence[DomainVersion],
    peer_versions: Sequence[DomainVersion],
) -> ConvergedCompatibilityReport:
    """The deterministic converged-domain compatibility negotiation.

    Both sides' version sets are consulted by SORTED domain label
    (input order never matters); a domain present on one side only
    fails closed (``local-missing``/``peer-missing`` — a converged
    peer that does not carry a frozen domain is incompatible on that
    line, never silently skipped); a domain outside the frozen set
    fails closed typed (``unknown-domain``)."""
    if not isinstance(local_versions, (list, tuple)) or not isinstance(
        peer_versions, (list, tuple)
    ):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "negotiate_converged_compatibility requires version "
            "sequences",
        )
    local_map: Dict[str, DomainVersion] = {}
    for version in local_versions:
        if not isinstance(version, DomainVersion):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "local version entries must be DomainVersion records",
            )
        if version.domain in local_map:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "duplicate local domain version for %r" % version.domain,
            )
        local_map[version.domain] = version
    peer_map: Dict[str, DomainVersion] = {}
    for version in peer_versions:
        if not isinstance(version, DomainVersion):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "peer version entries must be DomainVersion records",
            )
        if version.domain in peer_map:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "duplicate peer domain version for %r" % version.domain,
            )
        peer_map[version.domain] = version
    verdicts: Tuple[DomainCompatibilityVerdict, ...]
    records = []
    for domain in sorted(set(local_map) | set(peer_map)):
        local = local_map.get(domain)
        peer = peer_map.get(domain)
        if local is None:
            records.append(DomainCompatibilityVerdict(
                domain=domain,
                verdict="local-missing",
                local_major=-1,
                local_minor=-1,
                peer_major=peer.major,
                peer_minor=peer.minor,
                detail="the local peer does not carry the frozen domain "
                       "(fail closed; never silently skipped)",
            ))
            continue
        if peer is None:
            records.append(DomainCompatibilityVerdict(
                domain=domain,
                verdict="peer-missing",
                local_major=local.major,
                local_minor=local.minor,
                peer_major=-1,
                peer_minor=-1,
                detail="the remote peer does not carry the frozen domain "
                       "(fail closed; never silently skipped)",
            ))
            continue
        records.append(classify_domain_compatibility(local, peer))
    verdicts = tuple(records)
    return ConvergedCompatibilityReport(
        local_id=local_id,
        peer_id=peer_id,
        verdicts=verdicts,
    )


__all__ = [
    # the frozen vocabularies
    "CONVERGENCE_PREFIX",
    "CONVERGED_DOMAIN_SET",
    "DOMAIN_COMPATIBILITY_VERDICTS",
    # the typed version records
    "DomainVersion",
    "DomainCompatibilityVerdict",
    "ConvergedCompatibilityReport",
    # the deterministic compatibility surfaces
    "classify_domain_compatibility",
    "capability_compatibility",
    "negotiate_converged_compatibility",
]
