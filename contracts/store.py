"""ADCOS connectivity-contract journal and state (M002 — Connectivity
Contract Core).

The contract state is a DETERMINISTIC FOLD over an append-only command
journal (the W057/W052 discipline: construction-is-recovery — the fold IS
the state). Durable recovery after an interruption means exactly this:
re-folding the journaled command prefix on a fresh store reproduces the
byte-identical contract and lease states, and resuming from the watermark
never duplicates a contract, a lease, or an artifact binding.

Journal discipline (the resource-store merge semantics applied to
commands):

1. an exact duplicate command (identical content-derived id) is idempotent
   (``duplicate`` — no state change, no second fold effect);
2. a stale sequence (at or below the per-contract watermark) fails closed
   (``replay-stale`` / ``sequence-conflict``);
3. a sequence above the next slot fails closed (``sequence-gap``);
4. every decision is a pure function of (watermark, accepted command ids,
   content, injected instants) — never wall clock, randomness, or thread
   scheduling.

Authority shape (LOCK-101/LOCK-117): the store is the ONLY writer of
contract state; every command flows through the contract authority. A
``Path``/``Session``/``Tunnel``/``Bearer``/``eSIM``/adapter artifact can
be BOUND as data (``bind-artifact``); there is no API that accepts an
execution artifact as an authority input — authority always flows from
the contract, never toward it.

The journal never carries secrets (LOCK-119): command payloads are
validated at record construction and the serialized journal line is
re-scanned before persisting.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import parse_instant

from .model import (
    COMMAND_KINDS,
    ContractError,
    ContractReason,
    ConnectivityContract,
    CreateContract,
    GrantLease,
    RenewLease,
    RevokeLease,
    ExpireLease,
    ExpireContract,
    ActivateContract,
    ContractLease,
    apply_command,
    build_contract,
    build_lease,
    _require_instant,
)

_COMMAND_ID_NAMESPACE = "adc-os-connectivity-contract-command"
_SECRET_VALUE_PATTERN_LINE = re.compile(
    r"\"(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+\""
)


def _derive_command_id(
    contract_id: str, payload: Mapping[str, Any], recorded_at: str
) -> str:
    """Content-derived command identity over (contract, payload, instant).

    The sequence is deliberately NOT part of the identity: a retried
    submission of the same (command, instant) derives the same id and is
    therefore recognized as an idempotent duplicate by the merge
    discipline; genuinely distinct events always differ in payload or
    instant.
    """
    document = {
        "namespace": _COMMAND_ID_NAMESPACE,
        "contract_id": contract_id,
        "recorded_at": recorded_at,
        "command": dict(payload),
    }
    try:
        payload_bytes = canonical_json_bytes(document)
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise ContractError(
            ContractReason.INVALID_INPUT,
            "command payload is not canonicalizable: %s" % error,
        ) from None
    return "sha256:" + hashlib.sha256(payload_bytes).hexdigest()


@dataclass(frozen=True)
class CommandRecord:
    """The journal envelope: one command, one contract, one sequence slot."""

    command_id: str
    contract_id: str
    sequence: int
    recorded_at: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.command_id, str) or not self.command_id.startswith("sha256:"):
            raise ContractError(
                ContractReason.INVALID_INPUT,
                "record.command_id must be the content-derived identity (sha256:...)",
            )
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 1:
            raise ContractError(
                ContractReason.INVALID_INPUT, "record.sequence must be an integer >= 1"
            )
        _require_instant(self.recorded_at, "record.recorded_at")
        if not isinstance(self.payload, Mapping) or not self.payload:
            raise ContractError(
                ContractReason.INVALID_INPUT, "record.payload must be a non-empty mapping"
            )
        kind = self.payload.get("command")
        if kind not in COMMAND_KINDS:
            raise ContractError(
                ContractReason.VOCABULARY,
                "record.payload.command must be one of %s" % ", ".join(COMMAND_KINDS),
            )
        expected = _derive_command_id(self.contract_id, self.payload, self.recorded_at)
        if self.command_id != expected:
            raise ContractError(
                ContractReason.ID_MISMATCH,
                "command_id does not match the derived identity (journal tamper evidence)",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "contract_id": self.contract_id,
            "sequence": self.sequence,
            "recorded_at": self.recorded_at,
            "payload": dict(self.payload),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "CommandRecord":
        if not isinstance(data, Mapping):
            raise ContractError(ContractReason.INVALID_INPUT, "record must be a mapping")
        return CommandRecord(
            command_id=data.get("command_id"),
            contract_id=data.get("contract_id"),
            sequence=data.get("sequence"),
            recorded_at=data.get("recorded_at"),
            payload=data.get("payload") or {},
        )


@dataclass(frozen=True)
class MergeResult:
    """The deterministic outcome of one journal merge."""

    status: str
    contract: Optional[ConnectivityContract]
    detail: str

    @property
    def accepted(self) -> bool:
        return self.status not in (
            ContractReason.DUPLICATE,
            ContractReason.REPLAY_STALE,
            ContractReason.SEQUENCE_CONFLICT,
            ContractReason.SEQUENCE_GAP,
        ) and self.contract is not None


def _command_from_payload(payload: Mapping[str, Any]) -> object:
    """Rehydrate a typed command object from its serialized payload."""
    from . import model as contract_model

    kind = payload.get("command")
    if kind == "create":
        return CreateContract(
            principal=contract_model.ConnectivityPrincipal.from_dict(payload.get("principal")),
            beneficiaries=tuple(
                contract_model.BeneficiaryScope.from_dict(b)
                for b in payload.get("beneficiaries") or ()
            ),
            requirements=tuple(
                contract_model.OpaqueReference.from_dict(r)
                for r in payload.get("requirements") or ()
            ),
            hard_constraints=tuple(
                contract_model.HardConstraint.from_dict(c)
                for c in payload.get("hard_constraints") or ()
            ),
            validity=contract_model.ValidityInterval.from_dict(payload.get("validity")),
            service_properties=tuple(
                contract_model.OpaqueReference.from_dict(p)
                for p in payload.get("service_properties") or ()
            ),
            usage_pricing_terms=(
                contract_model.OpaqueReference.from_dict(payload.get("usage_pricing_terms"))
                if payload.get("usage_pricing_terms") is not None
                else None
            ),
            assurance_obligations=tuple(
                contract_model.OpaqueReference.from_dict(o)
                for o in payload.get("assurance_obligations") or ()
            ),
            execution_scope=tuple(
                contract_model.OpaqueReference.from_dict(s)
                for s in payload.get("execution_scope") or ()
            ),
            termination=contract_model.TerminationRules.from_dict(payload.get("termination")),
            provenance=contract_model.Provenance.from_dict(payload.get("provenance")),
            superseded_contract=(
                contract_model.OpaqueReference.from_dict(payload.get("superseded_contract"))
                if payload.get("superseded_contract") is not None
                else None
            ),
        )
    if kind == "select-offers":
        return contract_model.SelectOffers(
            offers=tuple(
                contract_model.OpaqueReference.from_dict(o)
                for o in payload.get("offers") or ()
            )
        )
    if kind == "activate":
        return contract_model.ActivateContract(
            activated_at=payload.get("activated_at"),
            signature_refs=tuple(
                contract_model.OpaqueReference.from_dict(s)
                for s in payload.get("signature_refs") or ()
            ),
        )
    if kind == "record-execution-activation":
        return contract_model.RecordExecutionActivation(recorded_at=payload.get("recorded_at"))
    if kind == "record-delivery":
        return contract_model.RecordDelivery(recorded_at=payload.get("recorded_at"))
    if kind == "record-assurance":
        return contract_model.RecordAssurance(
            recorded_at=payload.get("recorded_at"),
            assurance_state=payload.get("assurance_state"),
            evidence_refs=tuple(
                contract_model.OpaqueReference.from_dict(e)
                for e in payload.get("evidence_refs") or ()
            ),
        )
    if kind == "record-usage-final":
        return contract_model.RecordUsageFinal(recorded_at=payload.get("recorded_at"))
    if kind == "record-settlement-pending":
        return contract_model.RecordSettlementPending(recorded_at=payload.get("recorded_at"))
    if kind == "record-settled":
        return contract_model.RecordSettled(recorded_at=payload.get("recorded_at"))
    if kind == "terminate":
        return contract_model.TerminateContract(
            recorded_at=payload.get("recorded_at"),
            condition=payload.get("condition"),
            reason=payload.get("reason"),
        )
    if kind == "expire":
        return contract_model.ExpireContract(recorded_at=payload.get("recorded_at"))
    if kind == "fail":
        return contract_model.FailContract(
            recorded_at=payload.get("recorded_at"), reason=payload.get("reason")
        )
    if kind == "bind-artifact":
        return contract_model.BindExecutionArtifact(
            artifact=contract_model.OpaqueReference.from_dict(payload.get("artifact"))
        )
    if kind == "grant-lease":
        return GrantLease(
            granted_at=payload.get("granted_at"),
            not_before=payload.get("not_before"),
            not_after=payload.get("not_after"),
        )
    if kind == "renew-lease":
        return RenewLease(
            lease_id=payload.get("lease_id"),
            granted_at=payload.get("granted_at"),
            not_before=payload.get("not_before"),
            not_after=payload.get("not_after"),
        )
    if kind == "revoke-lease":
        return RevokeLease(
            lease_id=payload.get("lease_id"),
            recorded_at=payload.get("recorded_at"),
            reason=payload.get("reason"),
        )
    if kind == "expire-lease":
        return ExpireLease(lease_id=payload.get("lease_id"), recorded_at=payload.get("recorded_at"))
    raise ContractError(
        ContractReason.VOCABULARY, "unsupported journal command kind %r" % kind
    )


def _is_lease_command(command: object) -> bool:
    return isinstance(command, (GrantLease, RenewLease, RevokeLease, ExpireLease))


class ContractStore:
    """The contract/lease state as a deterministic fold over a journal.

    Thread-safe (a re-entrant lock guards merge and fold). Optionally
    persistent: with a ``journal_path`` the journal is appended as JSONL
    and re-folded on construction (construction-is-recovery). Every
    journal line is tamper-checked (content-derived command ids) and
    secret-scanned (LOCK-119) before it enters the fold.
    """

    def __init__(self, journal_path: Optional[Path] = None) -> None:
        self._lock = threading.RLock()
        self._journal_path = Path(journal_path) if journal_path is not None else None
        self._journal: List[CommandRecord] = []
        self._contracts: Dict[str, ConnectivityContract] = {}
        self._leases: Dict[str, ContractLease] = {}
        self._leases_by_contract: Dict[str, List[str]] = {}
        self._watermarks: Dict[str, int] = {}
        self._accepted_ids: Dict[str, set] = {}
        if self._journal_path is not None and self._journal_path.is_file():
            self._load_journal()

    # -- construction-is-recovery -----------------------------------------

    def _load_journal(self) -> None:
        assert self._journal_path is not None
        try:
            raw_lines = self._journal_path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise ContractError(
                ContractReason.JOURNAL_TAMPER,
                "cannot read the contract journal: %s" % error,
            ) from None
        for line_number, line in enumerate(raw_lines, start=1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except ValueError as error:
                raise ContractError(
                    ContractReason.JOURNAL_TAMPER,
                    "journal line %d is not valid JSON: %s" % (line_number, error),
                ) from None
            if _SECRET_VALUE_PATTERN_LINE.search(line):
                raise ContractError(
                    ContractReason.SECRET_REJECTED,
                    "journal line %d carries secret-shaped material (LOCK-119)" % line_number,
                )
            record = CommandRecord.from_dict(data)
            result = self._merge_unlocked(record)
            if not result.accepted and result.status != ContractReason.DUPLICATE:
                raise ContractError(
                    ContractReason.JOURNAL_TAMPER,
                    "journal line %d failed the merge discipline (%s)" % (line_number, result.status),
                )

    # -- journal merge ------------------------------------------------------

    def next_record(
        self, contract_id: Optional[str], command: object, recorded_at: str
    ) -> CommandRecord:
        """Build the next journal record for a command under a contract.

        ``contract_id`` is None only for CreateContract (the identity is
        derived from the creation core). The sequence is the next slot.
        Re-submitting the same (command, recorded_at) reproduces the same
        command_id — that is the idempotency key.
        """
        _require_instant(recorded_at, "record.recorded_at")
        payload = command.to_dict() if hasattr(command, "to_dict") else None
        if payload is None:
            raise ContractError(
                ContractReason.INVALID_INPUT,
                "command %s is not serializable" % type(command).__name__,
            )
        if isinstance(command, CreateContract):
            if contract_id is not None:
                raise ContractError(
                    ContractReason.INVALID_INPUT,
                    "create derives its own contract identity; do not pass contract_id",
                )
            contract = build_contract(command)
            owner = contract.contract_id
        else:
            if contract_id is None:
                raise ContractError(
                    ContractReason.INVALID_INPUT,
                    "command %s requires the owning contract_id"
                    % type(command).__name__,
                )
            owner = contract_id
        with self._lock:
            sequence = self._watermarks.get(owner, 0) + 1
        command_id = _derive_command_id(owner, payload, recorded_at)
        return CommandRecord(
            command_id=command_id,
            contract_id=owner,
            sequence=sequence,
            recorded_at=recorded_at,
            payload=payload,
        )

    def submit(
        self, command: object, recorded_at: str, contract_id: Optional[str] = None
    ) -> MergeResult:
        """Build and merge the next record for a command (the convenience
        path). Exact duplicate submissions are idempotent."""
        record = self.next_record(contract_id, command, recorded_at)
        return self.merge(record)

    def merge(self, record: CommandRecord) -> MergeResult:
        """Merge one journal record under the journal discipline."""
        with self._lock:
            return self._merge_unlocked(record)

    def _merge_unlocked(self, record: CommandRecord) -> MergeResult:
        owner = record.contract_id
        accepted = self._accepted_ids.setdefault(owner, set())
        watermark = self._watermarks.get(owner, 0)

        if record.command_id in accepted:
            return MergeResult(
                ContractReason.DUPLICATE,
                self._contracts.get(owner),
                "duplicate command id (idempotent no-op)",
            )
        if record.sequence <= watermark:
            if record.sequence == watermark:
                return MergeResult(
                    ContractReason.SEQUENCE_CONFLICT,
                    self._contracts.get(owner),
                    "sequence %d is the current watermark with different content" % record.sequence,
                )
            return MergeResult(
                ContractReason.REPLAY_STALE,
                self._contracts.get(owner),
                "sequence %d is below the watermark %d" % (record.sequence, watermark),
            )
        if record.sequence > watermark + 1:
            return MergeResult(
                ContractReason.SEQUENCE_GAP,
                self._contracts.get(owner),
                "sequence %d skips past the next slot %d" % (record.sequence, watermark + 1),
            )

        command = _command_from_payload(record.payload)

        if isinstance(command, CreateContract):
            if owner in self._contracts:
                return MergeResult(
                    ContractReason.SEQUENCE_CONFLICT,
                    self._contracts[owner],
                    "contract %s already exists; create is once" % owner[:16],
                )
            contract = build_contract(command)
            if contract.contract_id != owner:
                return MergeResult(
                    ContractReason.ID_MISMATCH,
                    None,
                    "create payload identity does not match the journal owner",
                )
            successor = contract
            status = ContractReason.CREATED
        else:
            contract = self._contracts.get(owner)
            if contract is None:
                return MergeResult(
                    ContractReason.UNKNOWN_CONTRACT,
                    None,
                    "contract %s is unknown; create must precede other commands" % owner[:16],
                )

            if _is_lease_command(command):
                successor, status = self._apply_lease_command(owner, contract, command, record)
            else:
                successor = apply_command(contract, command)
                status = _SUCCESS_STATUS.get(type(command).__name__, ContractReason.CREATED)
                # deterministic derived effect: contract activation promotes
                # granted leases of this contract to active
                if isinstance(command, ActivateContract):
                    self._promote_granted_leases(owner)

        self._journal.append(record)
        self._contracts[owner] = successor
        self._watermarks[owner] = record.sequence
        accepted.add(record.command_id)
        self._persist(record)
        return MergeResult(status, successor, "applied sequence %d" % record.sequence)

    # -- lease fold ---------------------------------------------------------

    def _apply_lease_command(
        self,
        owner: str,
        contract: ConnectivityContract,
        command: object,
        record: CommandRecord,
    ) -> Tuple[ConnectivityContract, str]:
        if isinstance(command, GrantLease):
            _require_instant(command.granted_at, "lease.granted_at")
            _require_instant(command.not_before, "lease.not_before")
            _require_instant(command.not_after, "lease.not_after")
            # the lease lives inside the contract validity window
            if (
                parse_instant(command.not_before) < parse_instant(contract.validity.not_before)
                or parse_instant(command.not_after) > parse_instant(contract.validity.not_after)
            ):
                raise ContractError(
                    ContractReason.INVALID_STATE,
                    "lease window must lie inside the contract validity window",
                )
            lease = build_lease(
                contract_id=owner,
                state="granted" if contract.state in ("INTENT", "OFFER_SELECTED") else "active",
                granted_at=command.granted_at,
                not_before=command.not_before,
                not_after=command.not_after,
            )
            self._leases[lease.lease_id] = lease
            self._leases_by_contract.setdefault(owner, []).append(lease.lease_id)
            return contract, ContractReason.LEASE_GRANTED
        if isinstance(command, RenewLease):
            predecessor = self._leases.get(command.lease_id)
            if predecessor is None:
                raise ContractError(
                    ContractReason.UNKNOWN_CONTRACT,
                    "lease %s is unknown" % command.lease_id[:16],
                )
            if predecessor.contract_id != owner:
                raise ContractError(
                    ContractReason.INVALID_STATE,
                    "lease belongs to another contract (authority uniqueness)",
                )
            if predecessor.state not in ("granted", "active"):
                raise ContractError(
                    ContractReason.INVALID_TRANSITION,
                    "only granted/active leases renew (found %s)" % predecessor.state,
                )
            if parse_instant(command.not_before) >= parse_instant(command.not_after):
                raise ContractError(
                    ContractReason.TEMPORAL_INVALID, "renewal window must be non-empty"
                )
            if parse_instant(command.not_after) > parse_instant(contract.validity.not_after):
                raise ContractError(
                    ContractReason.INVALID_STATE,
                    "renewal cannot extend past the contract validity window",
                )
            successor_lease = build_lease(
                contract_id=owner,
                state=predecessor.state,
                granted_at=command.granted_at,
                not_before=command.not_before,
                not_after=command.not_after,
            )
            self._leases[predecessor.lease_id] = ContractLease(
                lease_id=predecessor.lease_id,
                contract_id=predecessor.contract_id,
                state="renewed",
                granted_at=predecessor.granted_at,
                not_before=predecessor.not_before,
                not_after=predecessor.not_after,
            )
            self._leases[successor_lease.lease_id] = successor_lease
            self._leases_by_contract.setdefault(owner, []).append(successor_lease.lease_id)
            return contract, ContractReason.LEASE_RENEWED
        if isinstance(command, RevokeLease):
            lease = self._leases.get(command.lease_id)
            if lease is None:
                raise ContractError(
                    ContractReason.UNKNOWN_CONTRACT,
                    "lease %s is unknown" % command.lease_id[:16],
                )
            if lease.contract_id != owner:
                raise ContractError(
                    ContractReason.INVALID_STATE,
                    "lease belongs to another contract (authority uniqueness)",
                )
            if lease.state not in ("granted", "active"):
                raise ContractError(
                    ContractReason.INVALID_TRANSITION,
                    "only granted/active leases revoke (found %s)" % lease.state,
                )
            self._leases[lease.lease_id] = ContractLease(
                lease_id=lease.lease_id,
                contract_id=lease.contract_id,
                state="revoked",
                granted_at=lease.granted_at,
                not_before=lease.not_before,
                not_after=lease.not_after,
                revocation_reason=command.reason,
            )
            return contract, ContractReason.LEASE_REVOKED
        if isinstance(command, ExpireLease):
            lease = self._leases.get(command.lease_id)
            if lease is None:
                raise ContractError(
                    ContractReason.UNKNOWN_CONTRACT,
                    "lease %s is unknown" % command.lease_id[:16],
                )
            if lease.contract_id != owner:
                raise ContractError(
                    ContractReason.INVALID_STATE,
                    "lease belongs to another contract (authority uniqueness)",
                )
            if lease.state not in ("granted", "active"):
                raise ContractError(
                    ContractReason.INVALID_TRANSITION,
                    "only granted/active leases expire (found %s)" % lease.state,
                )
            if not lease.is_expired(record.recorded_at):
                raise ContractError(
                    ContractReason.INVALID_STATE,
                    "lease expiry requires the evaluation instant past lease.not_after",
                )
            self._leases[lease.lease_id] = ContractLease(
                lease_id=lease.lease_id,
                contract_id=lease.contract_id,
                state="expired",
                granted_at=lease.granted_at,
                not_before=lease.not_before,
                not_after=lease.not_after,
            )
            return contract, ContractReason.EXPIRED
        raise ContractError(
            ContractReason.INVALID_INPUT,
            "unsupported lease command %s" % type(command).__name__,
        )

    def _promote_granted_leases(self, owner: str) -> None:
        """Contract activation deterministically promotes granted leases to
        active (the journal event drives the derived state)."""
        for lease_id in list(self._leases_by_contract.get(owner, ())):
            lease = self._leases.get(lease_id)
            if lease is not None and lease.state == "granted":
                self._leases[lease.lease_id] = ContractLease(
                    lease_id=lease.lease_id,
                    contract_id=lease.contract_id,
                    state="active",
                    granted_at=lease.granted_at,
                    not_before=lease.not_before,
                    not_after=lease.not_after,
                )

    # -- expiry evaluation (pure, injected instants) ------------------------

    def contract_expiry_due(self, contract_id: str, now: str) -> bool:
        """True when the contract is non-terminal and past validity."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            raise ContractError(
                ContractReason.UNKNOWN_CONTRACT,
                "contract %s is unknown" % contract_id[:16],
            )
        return not contract.is_terminal and contract.validity.is_expired(now)

    def expire_contract_if_due(self, contract_id: str, now: str) -> MergeResult:
        """Merge the expiry command when due (no-op detail otherwise)."""
        if self.contract_expiry_due(contract_id, now):
            return self.submit(ExpireContract(recorded_at=now), recorded_at=now, contract_id=contract_id)
        return MergeResult(
            "not-due", self._contracts.get(contract_id), "contract not past validity at the evaluation instant"
        )

    def lease_expiry_due(self, lease_id: str, now: str) -> bool:
        lease = self._leases.get(lease_id)
        if lease is None:
            raise ContractError(
                ContractReason.UNKNOWN_CONTRACT, "lease %s is unknown" % lease_id[:16]
            )
        return lease.state in ("granted", "active") and lease.is_expired(now)

    def expire_leases_if_due(self, contract_id: str, now: str) -> List[MergeResult]:
        results: List[MergeResult] = []
        for lease_id in self.leases_for_contract(contract_id):
            if self.lease_expiry_due(lease_id, now):
                results.append(
                    self.submit(
                        ExpireLease(lease_id=lease_id, recorded_at=now),
                        recorded_at=now,
                        contract_id=contract_id,
                    )
                )
        return results

    # -- read surface (sorted iteration; PYTHONHASHSEED-safe) ---------------

    def contract(self, contract_id: str) -> ConnectivityContract:
        contract = self._contracts.get(contract_id)
        if contract is None:
            raise ContractError(
                ContractReason.UNKNOWN_CONTRACT, "contract %s is unknown" % contract_id[:16]
            )
        return contract

    def contracts(self) -> Tuple[ConnectivityContract, ...]:
        return tuple(self._contracts[key] for key in sorted(self._contracts))

    def lease(self, lease_id: str) -> ContractLease:
        lease = self._leases.get(lease_id)
        if lease is None:
            raise ContractError(
                ContractReason.UNKNOWN_CONTRACT, "lease %s is unknown" % lease_id[:16]
            )
        return lease

    def leases(self) -> Tuple[ContractLease, ...]:
        return tuple(self._leases[key] for key in sorted(self._leases))

    def leases_for_contract(self, contract_id: str) -> Tuple[str, ...]:
        return tuple(sorted(self._leases_by_contract.get(contract_id, ())))

    def journal(self) -> Tuple[CommandRecord, ...]:
        return tuple(self._journal)

    def journal_digest(self) -> str:
        """A digest over the whole journal (cross-process determinism proof)."""
        lines = [
            json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
            for record in self._journal
        ]
        return "sha256:" + hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    def __len__(self) -> int:
        return len(self._journal)

    # -- persistence ---------------------------------------------------------

    def _persist(self, record: CommandRecord) -> None:
        if self._journal_path is None:
            return
        line = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        if _SECRET_VALUE_PATTERN_LINE.search(line):
            raise ContractError(
                ContractReason.SECRET_REJECTED,
                "refusing to persist secret-shaped material (LOCK-119)",
            )
        try:
            self._journal_path.parent.mkdir(parents=True, exist_ok=True)
            with self._journal_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as error:
            raise ContractError(
                ContractReason.JOURNAL_TAMPER,
                "cannot persist the contract journal: %s" % error,
            ) from None


_SUCCESS_STATUS: Dict[str, str] = {
    "SelectOffers": ContractReason.OFFERS_SELECTED,
    "ActivateContract": ContractReason.ACTIVATED,
    "RecordExecutionActivation": ContractReason.EXECUTION_ACTIVATED,
    "RecordDelivery": ContractReason.DELIVERED,
    "RecordAssurance": ContractReason.ASSURED,
    "RecordUsageFinal": ContractReason.USAGE_FINAL,
    "RecordSettlementPending": ContractReason.SETTLEMENT_PENDING,
    "RecordSettled": ContractReason.SETTLED,
    "TerminateContract": ContractReason.TERMINATED,
    "ExpireContract": ContractReason.EXPIRED,
    "FailContract": ContractReason.FAILED,
    "BindExecutionArtifact": ContractReason.ARTIFACT_BOUND,
}
