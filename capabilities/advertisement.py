"""The provider-domain capability advertisement seam (M003 refactor).

Migration classification (``spec/migration/classification-matrix.md``):
"Capability registry: RETAIN + REFACTOR → Offer/capability exchange".
This module is the REFACTOR half: the accepted WORK-005 capability
statement/negotiation semantics are RETAINED untouched; this seam
projects a VERIFIED, currently-usable statement into the typed entry
material the Architecture 1.1 offer exchange (``offers/``, M003)
consumes as capability advertisement grounding.

What this seam is:

- ``advertisement_entry`` — one statement projected into an
  ``AdvertisementEntry``: the capability id, the statement's schema
  version, the content digest over the statement's canonical bytes
  (the ``capabilities/serialization`` machinery — no second
  serialization system), and the classification the registry produced
  (carried verbatim as DATA — classification authority stays HERE,
  in the capability registry; the offers domain never classifies).
- ``advertisement_entries`` — the deterministic batch projection at
  an injected instant: only statements that are currently ACTIVE
  (``validity.evaluate_status``) are advertised; the output is sorted
  by the data model (capability_id, schema_version, provider_identity)
  — stable under input reordering and repeat runs.

What this seam is NOT:

- it is not a trust, authorization, or availability judgment (the
  statement boundary is unchanged: a statement is a CLAIM);
- it is not a second vocabulary authority (classification flows from
  the registry through the accepted ``classify_capability_id``; no
  identifier is enumerated in code);
- it does not sign, verify, or re-sign anything (statement signing/
  verification stays the WORK-005/WORK-004 surface; callers verify
  statements BEFORE projecting them — the digest binds the projected
  entry to the exact statement bytes).

Determinism: the evaluation instant is injected (no wall clock); the
digest is the canonical-JSON sha256; iteration is sorted; duplicate
statement digests fail closed (an ambiguous advertisement is worse
than none).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .classification import classify_capability_id
from .model import CapabilityStatement
from .serialization import statement_to_bytes
from .validity import StatementStatus, evaluate_status

import hashlib

class AdvertisementError(ValueError):
    """Raised when an advertisement projection violates its contract
    (fail closed). ``code`` is a stable machine-readable reason."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


class AdvertisementEntry:
    """One capability advertisement entry: a verified statement
    projected into the typed entry material the offers domain (M003)
    consumes as grounding.

    Constructed through ``advertisement_entry`` (single) or
    ``advertisement_entries`` (batch) — the record itself is a plain
    immutable value once built."""

    __slots__ = (
        "capability_id",
        "schema_version",
        "provider_identity",
        "statement_digest",
        "classification",
    )

    def __init__(
        self,
        *,
        capability_id: str,
        schema_version: str,
        provider_identity: str,
        statement_digest: str,
        classification: str,
    ) -> None:
        if not isinstance(capability_id, str) or not capability_id:
            raise AdvertisementError(
                "capability-id", "capability_id must be a non-empty string"
            )
        if not isinstance(schema_version, str) or not schema_version:
            raise AdvertisementError(
                "schema-version", "schema_version must be a non-empty string"
            )
        if not isinstance(provider_identity, str) or not provider_identity:
            raise AdvertisementError(
                "provider-identity", "provider_identity must be a non-empty string"
            )
        if not isinstance(statement_digest, str) or not statement_digest.startswith(
            "sha256:"
        ):
            raise AdvertisementError(
                "statement-digest",
                "statement_digest must be a sha256 content digest",
            )
        if not isinstance(classification, str) or not classification:
            raise AdvertisementError(
                "classification", "classification must be a non-empty string"
            )
        self.capability_id = capability_id
        self.schema_version = schema_version
        self.provider_identity = provider_identity
        self.statement_digest = statement_digest
        self.classification = classification

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "schema_version": self.schema_version,
            "provider_identity": self.provider_identity,
            "statement_digest": self.statement_digest,
            "classification": self.classification,
        }

    def sort_key(self) -> Tuple[str, str, str]:
        """The deterministic data-model ordering key (capability_id,
        schema_version, provider_identity)."""
        return (self.capability_id, self.schema_version, self.provider_identity)

    def __repr__(self) -> str:
        return (
            "AdvertisementEntry(capability_id=%r, schema_version=%r, "
            "classification=%s)"
            % (self.capability_id, self.schema_version, self.classification)
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AdvertisementEntry):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __hash__(self) -> int:
        return hash(
            (
                self.capability_id,
                self.schema_version,
                self.provider_identity,
                self.statement_digest,
                self.classification,
            )
        )


def _statement_digest(statement: CapabilityStatement) -> str:
    """The content digest over the statement's canonical bytes (the
    WORK-003 canonicalization through the accepted serialization
    machinery — no second serialization system)."""
    return "sha256:" + hashlib.sha256(statement_to_bytes(statement)).hexdigest()


def advertisement_entry(statement: CapabilityStatement) -> AdvertisementEntry:
    """Project ONE verified statement into an advertisement entry.

    The caller is responsible for statement verification (WORK-005
    signing/verification surface) — this seam only projects. The
    classification is produced by the registry authority
    (``classify_capability_id``), never enumerated here."""
    if not isinstance(statement, CapabilityStatement):
        raise AdvertisementError(
            "statement",
            "advertisement projection requires a CapabilityStatement "
            "(found %s)" % type(statement).__name__,
        )
    return AdvertisementEntry(
        capability_id=statement.capability_id,
        schema_version=statement.schema_version,
        provider_identity=statement.provider_identity,
        statement_digest=_statement_digest(statement),
        classification=classify_capability_id(statement.capability_id),
    )


def advertisement_entries(
    statements: Iterable[CapabilityStatement],
    *,
    now: datetime,
) -> Tuple[AdvertisementEntry, ...]:
    """Project the batch of currently-usable statements at the injected
    instant (deterministic).

    Only statements whose evaluated status is ACTIVE at ``now`` are
    advertised (withdrawn and expired statements never advertise —
    historical statements remain queryable through the statement
    surface for audit, exactly as before). Malformed temporal material
    fails closed (``evaluate_status`` discipline). The output is sorted
    by the data model (capability_id, schema_version,
    provider_identity, then digest) — stable under input reordering
    and repeat runs. Duplicate digests fail closed: an ambiguous
    advertisement is worse than none."""
    if not isinstance(now, datetime):
        raise AdvertisementError("now", "the evaluation instant must be a datetime")
    if now.tzinfo is None:
        raise AdvertisementError(
            "now", "the evaluation instant must be timezone-aware"
        )
    entries: List[AdvertisementEntry] = []
    seen_keys: dict = {}
    seen_digests: dict = {}
    materialized = list(statements)
    for statement in materialized:
        if not isinstance(statement, CapabilityStatement):
            raise AdvertisementError(
                "statement",
                "advertisement projection requires CapabilityStatement "
                "records (found %s)" % type(statement).__name__,
            )
        status = evaluate_status(
            valid_from=statement.valid_from,
            expires_at=statement.expires_at,
            withdrawn_at=statement.withdrawn_at,
            now=now,
        )
        if status != StatementStatus.ACTIVE:
            continue  # not currently usable: never advertised
        entry = advertisement_entry(statement)
        key = (
            entry.capability_id,
            entry.schema_version,
            entry.provider_identity,
        )
        prior = seen_keys.get(key)
        if prior is not None and prior.statement_digest != entry.statement_digest:
            raise AdvertisementError(
                "ambiguous-statement",
                "two ACTIVE statements for %s/%s/%s with different content — "
                "the advertisement is ambiguous, failing closed"
                % key,
            )
        digest_owner = seen_digests.get(entry.statement_digest)
        if digest_owner is not None and digest_owner != key:
            raise AdvertisementError(
                "ambiguous-digest",
                "statement digest %s claimed by two different capability "
                "statements — failing closed" % entry.statement_digest[:24],
            )
        seen_keys[key] = entry
        seen_digests[entry.statement_digest] = key
        entries.append(entry)
    # deterministic order: the data-model tie-break chain, digest last
    entries.sort(key=lambda e: e.sort_key() + (e.statement_digest,))
    # deduplicate exact repeats (same key + same digest): idempotent
    deduplicated: List[AdvertisementEntry] = []
    for entry in entries:
        if deduplicated and deduplicated[-1].to_dict() == entry.to_dict():
            continue
        deduplicated.append(entry)
    return tuple(deduplicated)


def entries_to_dicts(entries: Sequence[AdvertisementEntry]) -> List[Dict[str, Any]]:
    """Serialize entries deterministically (sorted by the data model)."""
    ordered = sorted(entries, key=lambda e: e.sort_key())
    return [entry.to_dict() for entry in ordered]
