"""The M010 attributable evidence ledger (frozen flow step 8).

Usage and assurance evidence must remain attributable to THE
contract.  This module is the harness's typed, fail-closed
attribution surface:

- **Evidence typing (LOCK-106).**  Usage observations and assurance
  evaluations are DISTINCT evidence kinds — a usage record is never
  an assurance record, and neither is a claim, a commitment, or an
  attestation.
- **Attribution is structural (LOCK-117/LOCK-118).**  Every entry
  carries the canonical contract id, the recorded instant, the
  issuer, and decision references.  The ledger is BOUND to the real
  ``ContractStore`` (read-only public projection) and FAILS CLOSED:
  an entry whose contract does not exist in the canonical fold is
  rejected; an unbound ledger rejects every write.
- **Data, never authority.**  The ledger never mutates a contract,
  never confers eligibility, and never promotes an observation into
  an attestation.  Canonical JSON round-trips are exact.

Determinism (LOCK-119): entries are content-ordered; iteration is
sorted (kind, recorded_at, token); no wall clock, no randomness, no
network, no secrets — tokens are grammar-checked, secret-shaped
values are rejected at construction time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from contracts import ContractError, ContractStore

from .application import REASON_NOT_BOUND, REASON_VOCABULARY, ShareNetError

# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------

#: The frozen evidence-kind vocabulary (LOCK-106: distinct evidence
#: types — usage observations and assurance evaluations; never
#: claims, commitments, or attestations).
EVIDENCE_KINDS: Tuple[str, ...] = (
    "usage-observation",
    "assurance-evaluation",
)

#: The ledger issuer identities (the seams that produce evidence;
#: each entry's provenance is part of its attribution).
EVIDENCE_ISSUERS: Tuple[str, ...] = (
    "m009-seam:usage-observation",
    "m005-seam:assurance-observation",
)

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")
_SECRET_VALUE_PATTERN = re.compile(
    r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$"
)
_SECRET_NAME_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)


def _require_evidence_token(value: object, label: str) -> str:
    if not isinstance(value, str) or _TOKEN_PATTERN.fullmatch(value) is None:
        raise ShareNetError(
            REASON_VOCABULARY,
            "%s must match the reference token grammar "
            "(^[A-Za-z0-9._:+/-]{1,128}$)" % label,
        )
    if _SECRET_VALUE_PATTERN.match(value):
        raise ShareNetError(
            REASON_VOCABULARY,
            "%s is secret-shaped (LOCK-119: secrets never enter "
            "evidence material)" % label,
        )
    return value


def _check_scalar_payload(payload: Mapping[str, Any], label: str) -> Dict[str, Any]:
    """Evidence payloads are scalar DATA only (deterministic, no
    nested structures; secret-shaped members rejected)."""
    if not isinstance(payload, Mapping):
        raise ShareNetError(
            REASON_VOCABULARY, "%s must be a mapping of scalars" % label
        )
    checked: Dict[str, Any] = {}
    for name in sorted(payload):
        if not isinstance(name, str) or not name:
            raise ShareNetError(
                REASON_VOCABULARY,
                "%s member names must be non-empty strings" % label,
            )
        if _SECRET_NAME_PATTERN.search(name):
            raise ShareNetError(
                REASON_VOCABULARY,
                "%s member %r is secret-named (LOCK-119)" % (label, name),
            )
        value = payload[name]
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ShareNetError(
                REASON_VOCABULARY,
                "%s member %r must be a scalar (found %s)"
                % (label, name, type(value).__name__),
            )
        if isinstance(value, str) and _SECRET_VALUE_PATTERN.match(value):
            raise ShareNetError(
                REASON_VOCABULARY,
                "%s member %r is secret-shaped (LOCK-119)" % (label, name),
            )
        checked[name] = value
    return checked


# ----------------------------------------------------------------------
# The evidence entry
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceEntry:
    """One attributable evidence record (LOCK-106 typed, LOCK-118
    provenance-carrying, LOCK-119 secret-free)."""

    kind: str
    contract_id: str
    recorded_at: str
    token: str
    issuer: str
    decision_refs: Tuple[str, ...]
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.kind not in EVIDENCE_KINDS:
            raise ShareNetError(
                REASON_VOCABULARY,
                "evidence kind %r is outside the frozen vocabulary %s"
                % (self.kind, list(EVIDENCE_KINDS)),
            )
        if not isinstance(self.contract_id, str) or not self.contract_id:
            raise ShareNetError(
                REASON_VOCABULARY,
                "evidence contract_id must be the canonical contract identity",
            )
        if not isinstance(self.recorded_at, str) or not self.recorded_at:
            raise ShareNetError(
                REASON_VOCABULARY,
                "evidence recorded_at must be an injected RFC 3339 UTC instant",
            )
        _require_evidence_token(self.token, "evidence.token")
        if not isinstance(self.issuer, str) or not self.issuer:
            raise ShareNetError(
                REASON_VOCABULARY, "evidence issuer must be a non-empty string"
            )
        refs = tuple(self.decision_refs)
        for ref in refs:
            _require_evidence_token(ref, "evidence.decision_refs entry")
        object.__setattr__(self, "decision_refs", refs)
        object.__setattr__(
            self, "payload", _check_scalar_payload(self.payload, "evidence.payload")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "contract_id": self.contract_id,
            "recorded_at": self.recorded_at,
            "token": self.token,
            "issuer": self.issuer,
            "decision_refs": list(self.decision_refs),
            "payload": dict(self.payload),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "EvidenceEntry":
        if not isinstance(data, Mapping):
            raise ShareNetError(
                REASON_VOCABULARY, "evidence entry must be a mapping"
            )
        return EvidenceEntry(
            kind=data.get("kind"),
            contract_id=data.get("contract_id"),
            recorded_at=data.get("recorded_at"),
            token=data.get("token"),
            issuer=data.get("issuer"),
            decision_refs=tuple(data.get("decision_refs") or ()),
            payload=dict(data.get("payload") or {}),
        )

    def canonical_key(self) -> Tuple[str, str, str]:
        """The deterministic sort key (kind, recorded_at, token)."""
        return (self.kind, self.recorded_at, self.token)


# ----------------------------------------------------------------------
# The attributable ledger
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Attribution:
    """The attribution record for one contract (step 8's proof
    artifact): every evidence entry attributable to THE contract,
    with the per-kind counts and the canonical state at
    attribution time."""

    contract_id: str
    contract_state: str
    usage_entries: Tuple[EvidenceEntry, ...]
    assurance_entries: Tuple[EvidenceEntry, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_state": self.contract_state,
            "usage_count": len(self.usage_entries),
            "assurance_count": len(self.assurance_entries),
            "usage_tokens": [entry.token for entry in self.usage_entries],
            "assurance_tokens": [entry.token for entry in self.assurance_entries],
        }


class EvidenceLedger:
    """The fail-closed attributable evidence ledger.

    Constructed BOUND to the real canonical ``ContractStore`` (the
    read-only public projection): every write verifies the entry's
    contract exists in the canonical fold BEFORE the entry is
    accepted.  An unbound ledger fails closed on every write; an
    unknown contract id fails closed; the ledger never mutates the
    canonical state.
    """

    def __init__(self, *, contracts: ContractStore) -> None:
        if not isinstance(contracts, ContractStore):
            raise ShareNetError(
                REASON_NOT_BOUND,
                "EvidenceLedger must be bound to a real ContractStore (the "
                "accepted M002 canonical authority) — attribution is "
                "verified against the canonical fold, never assumed",
            )
        self._contracts = contracts
        self._entries: List[EvidenceEntry] = []

    # -- writes (fail-closed attribution) ----------------------------

    def record(self, entry: EvidenceEntry) -> EvidenceEntry:
        """Record one evidence entry, verifying attribution against
        the canonical fold first (fail-closed)."""
        self._require_known_contract(entry.contract_id)
        self._entries.append(entry)
        return entry

    # -- reads (deterministic, sorted) --------------------------------

    def entries(self) -> Tuple[EvidenceEntry, ...]:
        """All entries, sorted by (kind, recorded_at, token)."""
        return tuple(sorted(self._entries, key=lambda item: item.canonical_key()))

    def for_contract(self, contract_id: str) -> Tuple[EvidenceEntry, ...]:
        """All entries attributable to one contract (sorted)."""
        return tuple(
            entry
            for entry in self.entries()
            if entry.contract_id == contract_id
        )

    def usage_entries(self, contract_id: str) -> Tuple[EvidenceEntry, ...]:
        return tuple(
            entry
            for entry in self.for_contract(contract_id)
            if entry.kind == "usage-observation"
        )

    def assurance_entries(self, contract_id: str) -> Tuple[EvidenceEntry, ...]:
        return tuple(
            entry
            for entry in self.for_contract(contract_id)
            if entry.kind == "assurance-evaluation"
        )

    def attribution(self, contract_id: str) -> Attribution:
        """The step-8 proof artifact: every entry attributable to THE
        contract plus the contract's canonical state at attribution
        time (read through the real fold)."""
        contract = self._require_known_contract(contract_id)
        return Attribution(
            contract_id=contract_id,
            contract_state=contract.state,
            usage_entries=self.usage_entries(contract_id),
            assurance_entries=self.assurance_entries(contract_id),
        )

    # -- internals -----------------------------------------------------

    def _require_known_contract(self, contract_id: str):
        """Fail-closed attribution verification: the contract must
        exist in the canonical fold (typed translation of the
        authority's own unknown-contract rejection)."""
        try:
            return self._contracts.contract(contract_id)
        except ContractError as error:
            raise ShareNetError(
                REASON_NOT_BOUND,
                "attribution failed closed: %s does not exist in the "
                "canonical fold (the fold is the only attribution "
                "truth; %s)" % (contract_id[:24], error.detail[:96]),
            ) from None


__all__ = [
    "Attribution",
    "EVIDENCE_ISSUERS",
    "EVIDENCE_KINDS",
    "EvidenceEntry",
    "EvidenceLedger",
]
