"""ADCOS local-first domain model (M016 — Local-First and Offline
Operation).

The local-first/offline operation records of the R8 charter M016 scope,
composing the accepted surfaces BY REFERENCE (import and compose; never
reimplement, weaken, fork, or bypass):

- **The authority snapshot** (:class:`AuthoritySnapshot`) — the local
  replica's typed view of the canonical authority material, carrying
  the authority's DECLARED freshness window (injected instants — a
  local state past its declared freshness bound never silently
  authorizes) and the contract's own LOCK-108 constraint fingerprint
  (consumed from ``contracts.ConnectivityContract.hard_constraint_
  fingerprint`` — never recomputed here);
- **The offline operation journal records** (:class:`OfflineOperation`)
  — the ordered, idempotent, replayable records of operations captured
  while partitioned: the journaled partition entry/exit (the M015
  degraded-mode discipline extended across the offline boundary, with
  the runtime journal's event ids as evidence-visible links) and the
  partition-tolerant admission decisions (each carrying the authority's
  declared freshness window and the claimed constraint set — DATA
  re-validated through the consumed M008 gates, the ``ReplanCandidate``
  precedent);
- **The local state** (:class:`LocalState`) — the deterministic fold
  result of one partition episode's journal (construction-is-recovery,
  the ``resilience/journal.py`` discipline conventions consumed as
  conventions, never forked: this is its own typed surface);
- **The resynchronization records** (:class:`DivergenceRecord`,
  :class:`ConvergenceRejection`, :class:`ResyncResult`) — the typed
  divergence evidence (full provenance on both sides of every
  conflict) and the deterministic convergence outcome (the DECLARED
  RECORDED resolution rule, the LOCK-111 class).

The central boundary (enforced throughout):

    AUTHORITY SNAPSHOT / OFFLINE JOURNAL
        = LOCAL-FIRST EXECUTION MATERIAL riding the canonical
          ``ConnectivityContract`` as an opaque reference (LOCK-101/
          LOCK-117: the contract is the sole authority; the local
          records cite the contract id, never re-derive contract
          identity, and the claimed constraint sets riding on the
          journal records are optimizer-supplied DATA re-validated by
          the consumed M008 gates at admission AND at resynchronization
          — LOCK-108 across the offline boundary, never a silent
          weakening)
        != CONTRACT AUTHORITY (contracts/ stays the sole authority)
        != THE M015 RUNTIME (resilience/ owns the session lifecycle;
          this domain DRIVES the accepted RuntimeStore for the offline
          transitions — never duplicates it)
        != THE M008 REPLAN KERNEL (replan/ owns the LOCK-108 gates and
          the tie-break key vocabulary; this domain CONSUMES both)

Determinism (LOCK-111/LOCK-119): content-derived ids over canonical
JSON (namespaced); injected instants only (no wall clock); no
randomness, no UUIDs, no network, no secrets; canonical-JSON
round-trips with tamper-evident ids re-verified at deserialization;
sorted and order-normalized iteration; PYTHONHASHSEED-safe.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from contracts import (
    CONSTRAINT_KINDS,
    HardConstraint,
    OpaqueReference,
    Provenance,
)

from replan import TIE_BREAK_KEYS

from resilience import RUNTIME_STATES

from .errors import LocalFirstError, LocalFirstReason

__all__ = [
    # frozen vocabularies
    "OPERATION_KINDS",
    "ADMISSION_OUTCOMES",
    "EPISODE_STATES",
    "RESOLUTION_CANDIDATE_KINDS",
    "DIVERGENCE_RESOLUTIONS",
    "DEFAULT_RESOLUTION_RULE",
    "LOCALFRESH_ISSUER",
    "RESYNC_DRIVEN_ISSUER",
    # typed records
    "AuthoritySnapshot",
    "OfflineOperation",
    "LocalState",
    "DivergenceRecord",
    "ConvergenceRejection",
    "ResyncResult",
    # the pure kernels
    "derive_episode_id",
    "derive_operation_id",
    "check_episode_state",
    "normalize_resolution_rule",
    "resolve_conflict",
]


# ----------------------------------------------------------------------
# The consumed-boundary error wrap (exception isolation)
# ----------------------------------------------------------------------

_CONSUMED_CODE_MAP = {
    "secret-rejected": LocalFirstReason.SECRET_REJECTED,
    "vocabulary": LocalFirstReason.VOCABULARY,
    "temporal-invalid": LocalFirstReason.TEMPORAL_INVALID,
    "invalid-input": LocalFirstReason.INVALID_INPUT,
    "id-mismatch": LocalFirstReason.ID_MISMATCH,
}


def _wrap_consumed_error(label: str) -> Iterator[None]:
    """Exception isolation at the consumed-domain boundary: a
    ``ContractError``/``ReplanError``/``ResilienceError`` (all ValueError
    subclasses carrying ``code``/``detail``) surfaces as a typed
    LocalFirstError with its deterministic text preserved — never a
    foreign exception type, never raw exception text into stored state.
    The consumed domains' LOCK-119 secret rejection maps onto this
    surface's own ``localfirst-secret-rejected``."""

    @contextlib.contextmanager
    def _ctx() -> Iterator[None]:
        try:
            yield
        except LocalFirstError:
            raise
        except ValueError as error:  # consumed typed errors are ValueError
            code = getattr(error, "code", "")
            mapped = _CONSUMED_CODE_MAP.get(code, LocalFirstReason.COMPOSITION)
            raise LocalFirstError(
                mapped,
                "%s was rejected by a consumed domain: %s"
                % (label, getattr(error, "detail", error)),
            ) from None

    return _ctx()


# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------

#: The M016-owned offline journal record kinds (the deterministic,
#: replayable offline journal vocabulary):
#:
#: - ``partition-entered`` — the journaled offline/degraded-mode ENTRY:
#:   the local node lost the authority and begins operating on its
#:   freshness-bounded local snapshot (carries the base snapshot id and
#:   the M015 runtime degraded-entry event id — the evidence-visible
#:   composition link);
#: - ``connectivity-admission`` — one partition-tolerant local admission
#:   decision (carries the authority's declared freshness window, the
#:   claimed constraint set as DATA, the subject, and the typed
#:   outcome — admitted, or the fail-closed stale / not-yet-valid /
#:   constraint-weakened rejections);
#: - ``partition-exited`` — the journaled offline-mode EXIT: the
#:   explicit reconnect and resynchronization completed (carries the
#:   fresh snapshot id, the resync result id and the M015 reconnect
#:   evidence id — the evidence-visible composition link).
OPERATION_KINDS: Tuple[str, ...] = (
    "partition-entered",
    "connectivity-admission",
    "partition-exited",
)

#: The typed admission outcomes (the fail-closed decision vocabulary —
#: an admission attempt is either ADMITTED (the freshness window holds
#: and the claimed constraint set preserves the contract's hard
#: constraints verbatim) or REJECTED with the specific typed class:
#: ``stale-rejected`` (past the declared freshness bound — the
#: charter's fail-closed stale-authority rejection), ``not-yet-valid-
#: rejected`` (before the window opens), or ``weakened-rejected``
#: (LOCK-108: the claimed set drops/relaxes/re-interprets a hard
#: constraint).  A rejected admission is JOURNALED (fail-closed is
#: evidence, never a silent allow and never a silent drop).
ADMISSION_OUTCOMES: Tuple[str, ...] = (
    "admitted",
    "stale-rejected",
    "not-yet-valid-rejected",
    "weakened-rejected",
)

#: The partition-episode lifecycle states (the offline journal's own
#: deterministic two-state vocabulary — deliberately NOT the M015
#: runtime-state vocabulary, which stays owned by ``resilience/`` and is
#: consumed through the runtime composition in
#: :mod:`localfirst.offline`): ``OPEN`` (partitioned — the journal
#: accepts local operations) and ``CLOSED`` (resynchronized — the exit
#: is final; a new partition opens a new episode).
EPISODE_STATES: Tuple[str, ...] = ("OPEN", "CLOSED")

#: The projected resolution-candidate kinds for conflict resolution
#: (the LOCK-111 class): each side of a conflict projects onto the
#: orderable candidate shape consumed from the M008 key vocabulary —
#: ``authority-record`` (the fresh authority snapshot's record) and
#: ``local-offline-operation`` (the local journal's admitted
#: operation).  With the declared rule ordering by candidate-kind first
#: (the default), the authority side wins (``authority-record`` <
#: ``local-offline-operation``, lexicographic on the projected content
#: keys — LOCK-101: the canonical authority never silently loses to a
#: local replica unless the DECLARED rule says so).
RESOLUTION_CANDIDATE_KINDS: Tuple[str, ...] = (
    "authority-record",
    "local-offline-operation",
)

#: The deterministic divergence-resolution outcomes: the converged
#: replica state retains the authority record or the local offline
#: operation for the conflicting subject (both sides stay cited on the
#: divergence record — the loser is never silently dropped, only
#: explicitly superseded IN THE REPLICA, with the full provenance of
#: both sides recorded).
DIVERGENCE_RESOLUTIONS: Tuple[str, ...] = (
    "authority-record",
    "local-offline-operation",
)

#: The default declared conflict-resolution rule (the consumed M008
#: ``DEFAULT_TIE_BREAK`` shape: candidate-kind first, then the
#: total-order candidate-id key) — the authority side wins every
#: conflict by declared kind order (LOCK-101: the canonical authority
#: is the authority; a local replica defers unless a caller explicitly
#: declares the content-order rule).
DEFAULT_RESOLUTION_RULE: Tuple[str, ...] = ("candidate-kind", "candidate-id")

#: The default issuer recorded on local-first provenance (LOCK-118: the
#: local-first surface asserts its own records; the contract stays the
#: sole authority).
LOCALFRESH_ISSUER = "localfirst:offline"

#: The issuer recorded on records produced by the resynchronization
#: drive (LOCK-118: the resync cites the episode and the fresh snapshot
#: it converges onto).
RESYNC_DRIVEN_ISSUER = "localfirst:resync-drive"


# ----------------------------------------------------------------------
# Internal helpers (the consumed-domain conventions, re-used)
# ----------------------------------------------------------------------

_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")
_SECRET_NAME_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$")

_SNAPSHOT_NAMESPACE = "adc-os-localfirst-snapshot"
_EPISODE_NAMESPACE = "adc-os-localfirst-episode"
_OPERATION_NAMESPACE = "adc-os-localfirst-operation"
_DIVERGENCE_NAMESPACE = "adc-os-localfirst-divergence"
_RESYNC_NAMESPACE = "adc-os-localfirst-resync"


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_id(namespace: str, document: Mapping[str, Any], label: str) -> str:
    payload = dict(document)
    payload["namespace"] = namespace
    return "sha256:" + hashlib.sha256(
        _canonical_bytes(payload, label)
    ).hexdigest()


def _reject_secret(value: object, label: str) -> None:
    """LOCK-119 guard: secret-shaped material never enters local-first data."""
    if _SECRET_NAME_PATTERN.search(label):
        raise LocalFirstError(
            LocalFirstReason.SECRET_REJECTED,
            "%s looks like secret material; secrets never enter local-first "
            "data" % label,
        )
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.match(value):
        raise LocalFirstError(
            LocalFirstReason.SECRET_REJECTED,
            "%s carries a secret-shaped value; secrets never enter "
            "local-first data" % label,
        )


def _require_str(value: object, label: str, *, pattern: Optional[re.Pattern] = None) -> str:
    if not isinstance(value, str) or not value:
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "%s must be a non-empty string" % label
        )
    if pattern is not None and pattern.fullmatch(value) is None:
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "%s has an invalid format: %r" % (label, value)
        )
    _reject_secret(value, label)
    return value


def _require_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "%s must be the content-derived identity (sha256:...)" % label,
        )
    _reject_secret(value, label)
    return value


def _require_in(value: object, vocabulary: Sequence[str], label: str) -> str:
    if value not in vocabulary:
        raise LocalFirstError(
            LocalFirstReason.VOCABULARY,
            "%s must be one of %s (found %r)" % (label, ", ".join(vocabulary), value),
        )
    return str(value)


def _require_instant(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "%s must be a non-empty instant string" % label
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise LocalFirstError(
            LocalFirstReason.TEMPORAL_INVALID,
            "%s %r is not RFC 3339 UTC: %s" % (label, value, error),
        ) from None
    _reject_secret(value, label)
    return value


def _require_provenance(value: object, label: str) -> Provenance:
    if not isinstance(value, Provenance):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "%s must be a Provenance record" % label
        )
    return value


def _require_sequence(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "%s must be a positive integer journal position (found %r)" % (label, value),
        )
    return value


def _normalize_references(
    value: object, label: str, *, ref_kind: str
) -> Tuple[OpaqueReference, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise LocalFirstError(LocalFirstReason.INVALID_INPUT, "%s must be a sequence" % label)
    normalized = []
    for i, item in enumerate(value):
        with _wrap_consumed_error("%s[%d]" % (label, i)):
            if not isinstance(item, OpaqueReference):
                raise LocalFirstError(
                    LocalFirstReason.INVALID_INPUT,
                    "%s[%d] must be an OpaqueReference record" % (label, i),
                )
            if item.ref_kind != ref_kind:
                raise LocalFirstError(
                    LocalFirstReason.VOCABULARY,
                    "%s[%d] must use the %s reference kind (LOCK-117: opaque "
                    "local-first material, never authority — found %s)"
                    % (label, i, ref_kind, item.ref_kind),
                )
        normalized.append(item)
    return tuple(normalized)


def _normalize_constraints(
    value: object, label: str
) -> Tuple[HardConstraint, ...]:
    """Normalize the CLAIMED constraint set (optimizer-supplied DATA,
    the ``ReplanCandidate`` precedent: re-validated against the
    contract's full hard-constraint set by the consumed M008 gates at
    admission AND at resynchronization — LOCK-108 twice, never a
    silent weakening)."""
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise LocalFirstError(LocalFirstReason.INVALID_INPUT, "%s must be a sequence" % label)
    normalized = []
    for i, item in enumerate(value):
        with _wrap_consumed_error("%s[%d]" % (label, i)):
            if not isinstance(item, HardConstraint):
                raise LocalFirstError(
                    LocalFirstReason.INVALID_INPUT,
                    "%s[%d] must be a HardConstraint record (the claimed "
                    "constraint set is DATA re-validated by the consumed M008 "
                    "gates)" % (label, i),
                )
        normalized.append(item)
    return tuple(normalized)


# ----------------------------------------------------------------------
# The resolution-rule kernel (the LOCK-111 class, consuming the M008
# key vocabulary BY REFERENCE)
# ----------------------------------------------------------------------


def normalize_resolution_rule(rule: object, label: str) -> Tuple[str, ...]:
    """Validate a declared conflict-resolution rule (the LOCK-111
    class), against the CONSUMED ``replan.TIE_BREAK_KEYS`` vocabulary
    (never a second vocabulary — the M008-owned content-key set, by
    reference).

    The rule must: be a non-empty sequence of keys from the consumed
    vocabulary, carry no repeats, and END with the ``candidate-id``
    total-order key.  Content keys only — a temporal key does not exist
    in the consumed vocabulary (never wall-clock, never random; same
    inputs -> the same resolution, byte-identical).
    """
    if not isinstance(rule, (tuple, list)) or isinstance(rule, (str, bytes)):
        raise LocalFirstError(
            LocalFirstReason.RESOLUTION_INVALID, "%s must be a sequence" % label
        )
    items = tuple(rule)
    if not items:
        raise LocalFirstError(
            LocalFirstReason.RESOLUTION_INVALID, "%s requires at least one entry" % label
        )
    for i, item in enumerate(items):
        if item not in TIE_BREAK_KEYS:
            raise LocalFirstError(
                LocalFirstReason.RESOLUTION_INVALID,
                "%s[%d] must be one of %s (found %r) — the consumed M008 content-key "
                "vocabulary only, never temporal (the LOCK-111 class: deterministic "
                "declared recorded ordering)" % (label, i, ", ".join(TIE_BREAK_KEYS), item),
            )
    if len(set(items)) != len(items):
        raise LocalFirstError(
            LocalFirstReason.RESOLUTION_INVALID,
            "%s must not repeat a resolution key" % label,
        )
    if items[-1] != "candidate-id":
        raise LocalFirstError(
            LocalFirstReason.RESOLUTION_INVALID,
            "%s must end with the candidate-id key (the total-order guarantee; "
            "the LOCK-111 class: deterministic declared recorded ordering)" % label,
        )
    return items


def resolve_conflict(
    local_kind: str,
    local_id: str,
    authority_kind: str,
    authority_id: str,
    rule: Tuple[str, ...],
) -> str:
    """Resolve ONE conflict deterministically by the DECLARED recorded
    rule (the LOCK-111 class): project both sides onto the orderable
    candidate shape (candidate-kind, candidate-id — the consumed M008
    key vocabulary), order the projected pair ascending by the rule's
    key sequence, and return the kind of the FIRST (winning) side.

    With the default rule (``candidate-kind`` first) the authority
    record wins (``authority-record`` sorts before
    ``local-offline-operation``); with the content-order rule
    (``candidate-id`` only) the projected content identities decide.
    Same inputs -> the same resolution, always (pure, deterministic).
    """
    normalized = normalize_resolution_rule(rule, "resolve_conflict.rule")
    local_kind = _require_in(
        local_kind, RESOLUTION_CANDIDATE_KINDS, "the local candidate kind"
    )
    authority_kind = _require_in(
        authority_kind, RESOLUTION_CANDIDATE_KINDS, "the authority candidate kind"
    )
    local_projection = (local_kind, local_id)
    authority_projection = (authority_kind, authority_id)
    for key in normalized:
        local_value = (
            local_projection[0] if key == "candidate-kind" else local_projection[1]
        )
        authority_value = (
            authority_projection[0]
            if key == "candidate-kind"
            else authority_projection[1]
        )
        if local_value < authority_value:
            return local_kind
        if authority_value < local_value:
            return authority_kind
    # unreachable post-normalization: the rule ends with the
    # candidate-id total-order key, so the projected ids always decide
    raise LocalFirstError(
        LocalFirstReason.RESOLUTION_INVALID,
        "the declared rule does not order the conflicting pair (the "
        "candidate-id total-order key must decide — LOCK-111)",
    )


# ----------------------------------------------------------------------
# The episode-state kernel
# ----------------------------------------------------------------------


def check_episode_state(current: str, required: str, operation: str) -> None:
    """Fail closed unless the partition episode is in the required
    state for the operation (the deterministic two-state lifecycle)."""
    _require_in(current, EPISODE_STATES, "episode.state")
    _require_in(required, EPISODE_STATES, "the required episode state")
    if current != required:
        if current == "CLOSED":
            raise LocalFirstError(
                LocalFirstReason.EPISODE_CLOSED,
                "the partition episode is CLOSED; closed episodes never accept "
                "operations (the %s operation is rejected — a new partition "
                "opens a new episode)" % operation,
            )
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "the %s operation requires a %s partition episode (found %s)"
            % (operation, required, current),
        )


# ----------------------------------------------------------------------
# The authority snapshot (the freshness-bounded authority view)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AuthoritySnapshot:
    """The local replica's typed view of the canonical authority
    material, carrying the authority's DECLARED freshness window.

    ``snapshot_id`` is content-derived over the full snapshot core
    (tamper-evident).  ``contract_id`` cites the OWNING canonical
    contract (attribution; the contract is the sole authority — this
    record carries no contract semantics beyond the citation).  The
    ``authority_records`` are the authority's current records as opaque
    ``execution-artifact`` references (LOCK-117: DATA, never
    authority; unique values — the authority's post-partition record
    set the resynchronization detects divergence against).
    ``fresh_from``/``fresh_until`` is the authority's declared
    freshness window: a local admission decided at an instant OUTSIDE
    the window NEVER authorizes (fail-closed
    ``localfirst-authority-stale`` /
    ``localfirst-authority-not-yet-valid`` — never a silent allow).
    ``constraint_fingerprint`` is the contract's own LOCK-108
    fingerprint (consumed from
    ``contracts.ConnectivityContract.hard_constraint_fingerprint`` —
    the snapshot constructor helper enforces the equality; the
    resynchronization re-verifies it against the live contract — a
    snapshot whose fingerprint disagrees with the contract is a
    forged/stale authority view and fails closed).
    ``state_digest`` (derived) names the authority state material the
    snapshot carries — the local-first runtime session's realization
    references name the snapshot pair
    (``snapshot_id``/``state_digest``), so every authority-view
    transition rides the accepted M015 WORK-012 reconnect discipline
    naming the OLD and the NEW views verbatim.
    """

    snapshot_id: str
    contract_id: str
    authority_records: Tuple[OpaqueReference, ...]
    fresh_from: str
    fresh_until: str
    constraint_fingerprint: str
    recorded_at: str
    provenance: Provenance
    state_digest: str = ""

    def __post_init__(self) -> None:
        # the snapshot identity is derived/verified LAST (it derives
        # over the validated core — the derive-if-empty convention)
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "snapshot.contract_id")
        )
        object.__setattr__(
            self,
            "authority_records",
            _normalize_references(self.authority_records, "snapshot.authority_records", ref_kind="execution-artifact"),
        )
        seen: Dict[str, str] = {}
        for i, ref in enumerate(self.authority_records):
            if ref.value in seen:
                raise LocalFirstError(
                    LocalFirstReason.INVALID_INPUT,
                    "snapshot.authority_records[%d] repeats the record value %r "
                    "(a divergent authority view carries each record once)"
                    % (i, ref.value[:40]),
                )
            seen[ref.value] = ref.value
        object.__setattr__(
            self, "fresh_from", _require_instant(self.fresh_from, "snapshot.fresh_from")
        )
        object.__setattr__(
            self, "fresh_until", _require_instant(self.fresh_until, "snapshot.fresh_until")
        )
        if parse_instant(self.fresh_until) < parse_instant(self.fresh_from):
            raise LocalFirstError(
                LocalFirstReason.TEMPORAL_INVALID,
                "the declared freshness window is empty (fresh_until %s precedes "
                "fresh_from %s)" % (self.fresh_until, self.fresh_from),
            )
        object.__setattr__(
            self,
            "constraint_fingerprint",
            _require_id(self.constraint_fingerprint, "snapshot.constraint_fingerprint"),
        )
        object.__setattr__(
            self, "recorded_at", _require_instant(self.recorded_at, "snapshot.recorded_at")
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "snapshot.provenance")
        )
        expected_digest = self._derive_state_digest()
        if not self.state_digest:
            object.__setattr__(self, "state_digest", expected_digest)
        else:
            if _ID_PATTERN.fullmatch(self.state_digest) is None:
                raise LocalFirstError(
                    LocalFirstReason.INVALID_INPUT,
                    "snapshot.state_digest must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.state_digest != expected_digest:
                raise LocalFirstError(
                    LocalFirstReason.ID_MISMATCH,
                    "state_digest does not match the derived authority-state "
                    "identity (tamper evidence)",
                )
        expected_id = self._derive_snapshot_id()
        if not self.snapshot_id:
            object.__setattr__(self, "snapshot_id", expected_id)
        else:
            if _ID_PATTERN.fullmatch(self.snapshot_id) is None:
                raise LocalFirstError(
                    LocalFirstReason.INVALID_INPUT,
                    "snapshot.snapshot_id must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.snapshot_id != expected_id:
                raise LocalFirstError(
                    LocalFirstReason.ID_MISMATCH,
                    "snapshot_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def _derive_state_digest(self) -> str:
        document = {
            "contract_id": self.contract_id,
            "authority_records": [r.to_dict() for r in self.authority_records],
        }
        return _derive_id(_SNAPSHOT_NAMESPACE, document, "the authority-state document")

    def _derive_snapshot_id(self) -> str:
        document = {
            "contract_id": self.contract_id,
            "authority_records": [r.to_dict() for r in self.authority_records],
            "fresh_from": self.fresh_from,
            "fresh_until": self.fresh_until,
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
        }
        return _derive_id(_SNAPSHOT_NAMESPACE, document, "the snapshot id document")

    def realization_refs(self) -> Tuple[str, str]:
        """The authority-view realization references (the snapshot id
        and the state digest — the WORK-012 member shape the
        local-first runtime session names its realization by)."""
        return (self.snapshot_id, self.state_digest)

    def freshness_outcome(self, decided_at: str) -> str:
        """The declared freshness outcome of an instant against this
        snapshot's window (pure, deterministic, inclusive bounds):
        ``fresh`` (within the window), ``stale`` (past fresh_until) or
        ``not-yet-valid`` (before fresh_from)."""
        decided = parse_instant(_require_instant(decided_at, "the decision instant"))
        if decided < parse_instant(self.fresh_from):
            return "not-yet-valid"
        if decided > parse_instant(self.fresh_until):
            return "stale"
        return "fresh"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "contract_id": self.contract_id,
            "authority_records": [r.to_dict() for r in self.authority_records],
            "fresh_from": self.fresh_from,
            "fresh_until": self.fresh_until,
            "constraint_fingerprint": self.constraint_fingerprint,
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
            "state_digest": self.state_digest,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "AuthoritySnapshot":
        if not isinstance(data, Mapping):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT, "the snapshot must be a mapping"
            )
        with _wrap_consumed_error("the snapshot deserialization"):
            return AuthoritySnapshot(
                snapshot_id=data.get("snapshot_id"),
                contract_id=data.get("contract_id"),
                authority_records=tuple(
                    OpaqueReference.from_dict(r) for r in data.get("authority_records") or ()
                ),
                fresh_from=data.get("fresh_from"),
                fresh_until=data.get("fresh_until"),
                constraint_fingerprint=data.get("constraint_fingerprint"),
                recorded_at=data.get("recorded_at"),
                provenance=Provenance.from_dict(data.get("provenance")),
                state_digest=data.get("state_digest") or "",
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the snapshot record")


def derive_snapshot_id(
    contract_id: str,
    authority_records: Tuple[OpaqueReference, ...],
    *,
    fresh_from: str,
    fresh_until: str,
    recorded_at: str,
    provenance: Provenance,
) -> str:
    """The content-derived authority-snapshot identity over the full
    snapshot core."""
    document = {
        "contract_id": contract_id,
        "authority_records": [r.to_dict() for r in authority_records],
        "fresh_from": fresh_from,
        "fresh_until": fresh_until,
        "recorded_at": recorded_at,
        "provenance": provenance.to_dict(),
    }
    return _derive_id(_SNAPSHOT_NAMESPACE, document, "the snapshot id document")


# ----------------------------------------------------------------------
# The offline operation journal record
# ----------------------------------------------------------------------

#: The per-kind member discipline (the ``RuntimeEvent`` convention,
#: re-expressed for the offline journal): kind -> (required members,
#: members that must be ABSENT).  A member outside its kind's shape
#: fails closed — most notably, an admission outcome/freshness members
#: on a partition record, or the runtime links on an admission record.
_ADMISSION_ONLY_MEMBERS = ("fresh_from", "fresh_until", "outcome")
_PARTITION_MEMBERS = ("base_snapshot_id", "base_state_digest", "runtime_event_id")
_EXIT_MEMBERS = ("fresh_snapshot_id", "fresh_state_digest", "resync_id", "reconnect_id")
_KIND_MEMBER_RULES: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {
    "partition-entered": (
        ("base_snapshot_id", "base_state_digest", "runtime_event_id"),
        _ADMISSION_ONLY_MEMBERS + _EXIT_MEMBERS + ("subject",),
    ),
    "connectivity-admission": (
        ("subject", "fresh_from", "fresh_until", "outcome"),
        _PARTITION_MEMBERS + _EXIT_MEMBERS,
    ),
    "partition-exited": (
        ("fresh_snapshot_id", "fresh_state_digest", "resync_id", "reconnect_id"),
        _ADMISSION_ONLY_MEMBERS + _PARTITION_MEMBERS + ("subject",),
    ),
}


@dataclass(frozen=True)
class OfflineOperation:
    """One typed offline journal record (the deterministic, replayable
    evidence unit of one partition episode).

    ``operation_id`` is content-derived over the POSITION-INDEPENDENT
    operation core (the episode, the contract, the kind, the instant,
    the subject, the claimed constraints, the outcome, the freshness
    window, the provenance) — deliberately NOT over the journal
    position: an operation retried while partitioned (an uncertain
    outcome) derives the SAME identity, so the journal append is
    IDEMPOTENT (a retried append returns the existing record; the same
    operation never double-applies).  The journal position
    (``sequence``, assigned by the journal, validated by the fold)
    stays a separate monotonic member.

    Kind-specific members (fail-closed by kind — the full
    :data:`_KIND_MEMBER_RULES` discipline):

    - ``partition-entered`` — ``base_snapshot_id`` /
      ``base_state_digest`` (the authority view the local node operates
      on while partitioned) and ``runtime_event_id`` (the M015
      degraded-entry event id — the evidence-visible composition
      link);
    - ``connectivity-admission`` — ``subject`` (the opaque
      ``execution-artifact`` reference naming the admission's subject
      — the conflict key), the claimed ``hard_constraints`` (DATA,
      re-validated by the consumed M008 gates), the carried freshness
      window ``fresh_from``/``fresh_until`` (the authority's declared
      window AT THE DECISION — the charter's requirement that
      admission decisions carry it), and the typed ``outcome``
      (admitted, or the fail-closed stale / not-yet-valid / weakened
      rejections — a rejected admission is JOURNALED, never a silent
      allow and never a silent drop);
    - ``partition-exited`` — ``fresh_snapshot_id`` /
      ``fresh_state_digest`` (the fresh authority view converged
      onto), ``resync_id`` (the resynchronization result) and
      ``reconnect_id`` (the M015 reconnect evidence id — the
      evidence-visible composition link).
    """

    operation_id: str
    episode_id: str
    contract_id: str
    sequence: int
    kind: str
    recorded_at: str
    provenance: Provenance
    subject: OpaqueReference = None  # type: ignore[assignment]
    hard_constraints: Tuple[HardConstraint, ...] = ()
    fresh_from: str = ""
    fresh_until: str = ""
    outcome: str = ""
    base_snapshot_id: str = ""
    base_state_digest: str = ""
    runtime_event_id: str = ""
    fresh_snapshot_id: str = ""
    fresh_state_digest: str = ""
    resync_id: str = ""
    reconnect_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "episode_id", _require_id(self.episode_id, "operation.episode_id")
        )
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "operation.contract_id")
        )
        object.__setattr__(
            self, "sequence", _require_sequence(self.sequence, "operation.sequence")
        )
        object.__setattr__(
            self, "kind", _require_in(self.kind, OPERATION_KINDS, "operation.kind")
        )
        object.__setattr__(
            self, "recorded_at", _require_instant(self.recorded_at, "operation.recorded_at")
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "operation.provenance")
        )
        # the kind-member discipline (fail-closed per kind)
        required, forbidden = _KIND_MEMBER_RULES[self.kind]
        missing = [name for name in required if not getattr(self, name)]
        if missing:
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "the %s record is missing the members %s" % (self.kind, ", ".join(missing)),
            )
        foreign = [name for name in forbidden if getattr(self, name)]
        if foreign:
            raise LocalFirstError(
                LocalFirstReason.VOCABULARY,
                "the %s record carries the members %s outside its frozen shape"
                % (self.kind, ", ".join(foreign)),
            )
        # the typed members
        if self.subject is not None:
            with _wrap_consumed_error("operation.subject"):
                if not isinstance(self.subject, OpaqueReference):
                    raise LocalFirstError(
                        LocalFirstReason.INVALID_INPUT,
                        "operation.subject must be an OpaqueReference record",
                    )
                if self.subject.ref_kind != "execution-artifact":
                    raise LocalFirstError(
                        LocalFirstReason.VOCABULARY,
                        "operation.subject must use the execution-artifact "
                        "reference kind (LOCK-117: opaque local-first material, "
                        "never authority — found %s)" % self.subject.ref_kind,
                    )
        elif self.kind == "connectivity-admission":
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "a connectivity-admission requires its subject reference",
            )
        object.__setattr__(
            self,
            "hard_constraints",
            _normalize_constraints(self.hard_constraints, "operation.hard_constraints"),
        )
        if self.fresh_from:
            object.__setattr__(
                self, "fresh_from", _require_instant(self.fresh_from, "operation.fresh_from")
            )
        if self.fresh_until:
            object.__setattr__(
                self, "fresh_until", _require_instant(self.fresh_until, "operation.fresh_until")
            )
        if self.outcome:
            object.__setattr__(
                self,
                "outcome",
                _require_in(self.outcome, ADMISSION_OUTCOMES, "operation.outcome"),
            )
        for member in (
            "base_snapshot_id",
            "fresh_snapshot_id",
            "resync_id",
            "reconnect_id",
            "runtime_event_id",
        ):
            value = getattr(self, member)
            if value:
                object.__setattr__(self, member, _require_id(value, "operation.%s" % member))
        for member in ("base_state_digest", "fresh_state_digest"):
            value = getattr(self, member)
            if value:
                object.__setattr__(
                    self, member, _require_id(value, "operation.%s" % member)
                )
        # the claimed constraint set exists exactly on admission records
        if self.kind != "connectivity-admission" and self.hard_constraints:
            raise LocalFirstError(
                LocalFirstReason.VOCABULARY,
                "the %s record carries a claimed constraint set outside the "
                "admission discipline (constraint material rides ONLY as "
                "admission DATA re-validated by the consumed M008 gates)"
                % self.kind,
            )
        # an admitted record MUST carry a non-empty claimed set (the
        # LOCK-108 re-verification material); a rejected record carries
        # the set it was rejected over (the evidence of what was
        # claimed — full provenance of the rejection)
        if self.kind == "connectivity-admission" and not self.hard_constraints:
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "a connectivity-admission must carry its claimed constraint set "
                "(the LOCK-108 re-verification material — DATA re-validated by "
                "the consumed M008 gates at admission AND at resynchronization)",
            )
        # the episode identity re-derives from the episode core named on
        # the partition-entered record (the fold enforces it; direct
        # construction of admission/exit records requires the episode
        # id to be a well-formed content identity only)
        expected = self._derive_operation_id()
        if not self.operation_id:
            object.__setattr__(self, "operation_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.operation_id) is None:
                raise LocalFirstError(
                    LocalFirstReason.INVALID_INPUT,
                    "operation.operation_id must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.operation_id != expected:
                raise LocalFirstError(
                    LocalFirstReason.ID_MISMATCH,
                    "operation_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def _derive_operation_id(self) -> str:
        document = {
            "episode_id": self.episode_id,
            "contract_id": self.contract_id,
            "kind": self.kind,
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
            "subject": self.subject.to_dict() if self.subject is not None else None,
            "hard_constraints": [c.to_dict() for c in self.hard_constraints],
            "fresh_from": self.fresh_from,
            "fresh_until": self.fresh_until,
            "outcome": self.outcome,
            "base_snapshot_id": self.base_snapshot_id,
            "base_state_digest": self.base_state_digest,
            "runtime_event_id": self.runtime_event_id,
            "fresh_snapshot_id": self.fresh_snapshot_id,
            "fresh_state_digest": self.fresh_state_digest,
            "resync_id": self.resync_id,
            "reconnect_id": self.reconnect_id,
        }
        return _derive_id(_OPERATION_NAMESPACE, document, "the operation id document")

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "operation_id": self.operation_id,
            "episode_id": self.episode_id,
            "contract_id": self.contract_id,
            "sequence": self.sequence,
            "kind": self.kind,
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
        }
        if self.subject is not None:
            data["subject"] = self.subject.to_dict()
        if self.hard_constraints:
            data["hard_constraints"] = [c.to_dict() for c in self.hard_constraints]
        for member in (
            "fresh_from",
            "fresh_until",
            "outcome",
            "base_snapshot_id",
            "base_state_digest",
            "runtime_event_id",
            "fresh_snapshot_id",
            "fresh_state_digest",
            "resync_id",
            "reconnect_id",
        ):
            value = getattr(self, member)
            if value:
                data[member] = value
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "OfflineOperation":
        if not isinstance(data, Mapping):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT, "the operation must be a mapping"
            )
        with _wrap_consumed_error("the operation deserialization"):
            return OfflineOperation(
                operation_id=data.get("operation_id") or "",
                episode_id=data.get("episode_id"),
                contract_id=data.get("contract_id"),
                sequence=data.get("sequence"),
                kind=data.get("kind"),
                recorded_at=data.get("recorded_at"),
                provenance=Provenance.from_dict(data.get("provenance")),
                subject=(
                    OpaqueReference.from_dict(data["subject"])
                    if data.get("subject")
                    else None
                ),
                hard_constraints=tuple(
                    HardConstraint.from_dict(c)
                    for c in data.get("hard_constraints") or ()
                ),
                fresh_from=data.get("fresh_from") or "",
                fresh_until=data.get("fresh_until") or "",
                outcome=data.get("outcome") or "",
                base_snapshot_id=data.get("base_snapshot_id") or "",
                base_state_digest=data.get("base_state_digest") or "",
                runtime_event_id=data.get("runtime_event_id") or "",
                fresh_snapshot_id=data.get("fresh_snapshot_id") or "",
                fresh_state_digest=data.get("fresh_state_digest") or "",
                resync_id=data.get("resync_id") or "",
                reconnect_id=data.get("reconnect_id") or "",
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the operation record")


def derive_operation_id(
    episode_id: str,
    contract_id: str,
    kind: str,
    recorded_at: str,
    provenance: Provenance,
    *,
    subject: Optional[OpaqueReference] = None,
    hard_constraints: Tuple[HardConstraint, ...] = (),
    fresh_from: str = "",
    fresh_until: str = "",
    outcome: str = "",
    base_snapshot_id: str = "",
    base_state_digest: str = "",
    runtime_event_id: str = "",
    fresh_snapshot_id: str = "",
    fresh_state_digest: str = "",
    resync_id: str = "",
    reconnect_id: str = "",
) -> str:
    """The content-derived offline-operation identity over the
    POSITION-INDEPENDENT operation core (the idempotency key: a retried
    operation derives the same identity — the same operation never
    double-applies)."""
    document = {
        "episode_id": episode_id,
        "contract_id": contract_id,
        "kind": kind,
        "recorded_at": recorded_at,
        "provenance": provenance.to_dict(),
        "subject": subject.to_dict() if subject is not None else None,
        "hard_constraints": [c.to_dict() for c in hard_constraints],
        "fresh_from": fresh_from,
        "fresh_until": fresh_until,
        "outcome": outcome,
        "base_snapshot_id": base_snapshot_id,
        "base_state_digest": base_state_digest,
        "runtime_event_id": runtime_event_id,
        "fresh_snapshot_id": fresh_snapshot_id,
        "fresh_state_digest": fresh_state_digest,
        "resync_id": resync_id,
        "reconnect_id": reconnect_id,
    }
    return _derive_id(_OPERATION_NAMESPACE, document, "the operation id document")


def derive_episode_id(
    contract_id: str, base_snapshot_id: str, opened_at: str, provenance: Provenance
) -> str:
    """The content-derived partition-episode identity over the episode
    core (the owning contract, the base authority view, the opening
    instant, the opening provenance)."""
    document = {
        "contract_id": contract_id,
        "base_snapshot_id": base_snapshot_id,
        "opened_at": opened_at,
        "provenance": provenance.to_dict(),
    }
    return _derive_id(_EPISODE_NAMESPACE, document, "the episode id document")


# ----------------------------------------------------------------------
# The local state (the fold result — the replayable episode state)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class LocalState:
    """The typed local-state record (the deterministic fold result of
    one partition episode's offline journal).

    ``episode_id`` is content-derived over the episode core (the
    owning contract, the base authority view, the opening instant and
    provenance — re-derived and verified by the fold, tamper
    evidence).  ``state`` is the episode lifecycle state (``OPEN`` /
    ``CLOSED``).  ``admitted``/``rejected`` carry the admitted /
    rejected admission operation ids in JOURNAL ORDER (the replayable
    admission history — the resynchronization input).  ``sequence`` is
    the journal position of the last applied record (the deterministic
    replay watermark).  The base and (on exit) fresh authority-view
    references name the authority views the episode operated between.
    """

    episode_id: str
    contract_id: str
    state: str
    base_snapshot_id: str
    base_state_digest: str
    sequence: int
    provenance: Provenance
    fresh_snapshot_id: str = ""
    fresh_state_digest: str = ""
    resync_id: str = ""
    admitted: Tuple[str, ...] = ()
    rejected: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "episode_id", _require_id(self.episode_id, "state.episode_id")
        )
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "state.contract_id")
        )
        object.__setattr__(
            self, "state", _require_in(self.state, EPISODE_STATES, "state.state")
        )
        object.__setattr__(
            self, "base_snapshot_id", _require_id(self.base_snapshot_id, "state.base_snapshot_id")
        )
        object.__setattr__(
            self, "base_state_digest", _require_id(self.base_state_digest, "state.base_state_digest")
        )
        object.__setattr__(
            self, "sequence", _require_sequence(self.sequence, "state.sequence")
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "state.provenance")
        )
        for member in ("fresh_snapshot_id", "fresh_state_digest", "resync_id"):
            value = getattr(self, member)
            if value:
                object.__setattr__(self, member, _require_id(value, "state.%s" % member))
        if self.state == "CLOSED" and not (self.fresh_snapshot_id and self.resync_id):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "a CLOSED local state must name the fresh authority view and "
                "the resynchronization it closed under",
            )
        if self.state == "OPEN" and (self.fresh_snapshot_id or self.resync_id):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "an OPEN local state carries no fresh authority view (the "
                "episode has not resynchronized yet)",
            )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "episode_id": self.episode_id,
            "contract_id": self.contract_id,
            "state": self.state,
            "base_snapshot_id": self.base_snapshot_id,
            "base_state_digest": self.base_state_digest,
            "sequence": self.sequence,
            "provenance": self.provenance.to_dict(),
        }
        for member in ("fresh_snapshot_id", "fresh_state_digest", "resync_id"):
            value = getattr(self, member)
            if value:
                data[member] = value
        if self.admitted:
            data["admitted"] = list(self.admitted)
        if self.rejected:
            data["rejected"] = list(self.rejected)
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "LocalState":
        if not isinstance(data, Mapping):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT, "the local state must be a mapping"
            )
        with _wrap_consumed_error("the local-state deserialization"):
            return LocalState(
                episode_id=data.get("episode_id"),
                contract_id=data.get("contract_id"),
                state=data.get("state"),
                base_snapshot_id=data.get("base_snapshot_id"),
                base_state_digest=data.get("base_state_digest"),
                sequence=data.get("sequence"),
                provenance=Provenance.from_dict(data.get("provenance")),
                fresh_snapshot_id=data.get("fresh_snapshot_id") or "",
                fresh_state_digest=data.get("fresh_state_digest") or "",
                resync_id=data.get("resync_id") or "",
                admitted=tuple(data.get("admitted") or ()),
                rejected=tuple(data.get("rejected") or ()),
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the local-state record")


# ----------------------------------------------------------------------
# The resynchronization records (typed divergence + convergence)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class DivergenceRecord:
    """One detected divergence between the local offline journal and
    the fresh authority view, with FULL PROVENANCE on both sides and
    the DECLARED RECORDED resolution (never a silent drop, never a
    silent duplicate — the loser stays cited, only explicitly
    superseded IN THE REPLICA).

    ``divergence_id`` is content-derived over the full record.
    ``subject_value`` is the conflicting subject's opaque identity.
    ``local_operation_id`` cites the local admitted operation;
    ``authority_record`` rides the authority's record verbatim (with
    its own provenance).  ``resolution_rule`` is the declared rule
    VERBATIM (the LOCK-111 class) and ``resolution`` names the
    converged side (the projected candidate kind that won).
    """

    divergence_id: str
    episode_id: str
    contract_id: str
    subject_value: str
    local_operation_id: str
    authority_record: OpaqueReference
    resolution_rule: Tuple[str, ...]
    resolution: str
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "episode_id", _require_id(self.episode_id, "divergence.episode_id")
        )
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "divergence.contract_id")
        )
        object.__setattr__(
            self,
            "subject_value",
            _require_str(
                self.subject_value, "divergence.subject_value", pattern=_REF_VALUE_PATTERN
            ),
        )
        object.__setattr__(
            self,
            "local_operation_id",
            _require_id(self.local_operation_id, "divergence.local_operation_id"),
        )
        with _wrap_consumed_error("divergence.authority_record"):
            if not isinstance(self.authority_record, OpaqueReference):
                raise LocalFirstError(
                    LocalFirstReason.INVALID_INPUT,
                    "divergence.authority_record must be an OpaqueReference record",
                )
            if self.authority_record.ref_kind != "execution-artifact":
                raise LocalFirstError(
                    LocalFirstReason.VOCABULARY,
                    "divergence.authority_record must use the execution-artifact "
                    "reference kind (LOCK-117 — found %s)" % self.authority_record.ref_kind,
                )
        object.__setattr__(
            self,
            "resolution_rule",
            normalize_resolution_rule(
                self.resolution_rule, "divergence.resolution_rule"
            ),
        )
        object.__setattr__(
            self,
            "resolution",
            _require_in(
                self.resolution, DIVERGENCE_RESOLUTIONS, "divergence.resolution"
            ),
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "divergence.provenance")
        )
        expected = self._derive_divergence_id()
        if not self.divergence_id:
            object.__setattr__(self, "divergence_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.divergence_id) is None:
                raise LocalFirstError(
                    LocalFirstReason.INVALID_INPUT,
                    "divergence.divergence_id must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.divergence_id != expected:
                raise LocalFirstError(
                    LocalFirstReason.ID_MISMATCH,
                    "divergence_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def _derive_divergence_id(self) -> str:
        document = {
            "episode_id": self.episode_id,
            "contract_id": self.contract_id,
            "subject_value": self.subject_value,
            "local_operation_id": self.local_operation_id,
            "authority_record": self.authority_record.to_dict(),
            "resolution_rule": list(self.resolution_rule),
            "resolution": self.resolution,
        }
        return _derive_id(_DIVERGENCE_NAMESPACE, document, "the divergence id document")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "divergence_id": self.divergence_id,
            "episode_id": self.episode_id,
            "contract_id": self.contract_id,
            "subject_value": self.subject_value,
            "local_operation_id": self.local_operation_id,
            "authority_record": self.authority_record.to_dict(),
            "resolution_rule": list(self.resolution_rule),
            "resolution": self.resolution,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "DivergenceRecord":
        if not isinstance(data, Mapping):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT, "the divergence must be a mapping"
            )
        with _wrap_consumed_error("the divergence deserialization"):
            return DivergenceRecord(
                divergence_id=data.get("divergence_id") or "",
                episode_id=data.get("episode_id"),
                contract_id=data.get("contract_id"),
                subject_value=data.get("subject_value"),
                local_operation_id=data.get("local_operation_id"),
                authority_record=OpaqueReference.from_dict(data.get("authority_record")),
                resolution_rule=tuple(data.get("resolution_rule") or ()),
                resolution=data.get("resolution"),
                provenance=Provenance.from_dict(data.get("provenance")),
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the divergence record")


@dataclass(frozen=True)
class ConvergenceRejection:
    """One resynchronization rejection (LOCK-108 across the offline
    boundary): a local admitted operation whose claimed constraint set
    fails the consumed M008 re-verification against the live contract
    at resynchronization time — REJECTED with the typed reason citing
    the specific constraint kinds, never silently converged, never
    silently dropped (the rejection is the evidence)."""

    operation_id: str
    code: str
    detail: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operation_id", _require_id(self.operation_id, "rejection.operation_id")
        )
        object.__setattr__(
            self,
            "code",
            _require_str(self.code, "rejection.code", pattern=_REF_VALUE_PATTERN),
        )
        if not isinstance(self.detail, str) or not self.detail:
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "rejection.detail must be a non-empty string",
            )
        _reject_secret(self.detail, "rejection.detail")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "code": self.code,
            "detail": self.detail,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ConvergenceRejection":
        if not isinstance(data, Mapping):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT, "the rejection must be a mapping"
            )
        return ConvergenceRejection(
            operation_id=data.get("operation_id"),
            code=data.get("code"),
            detail=data.get("detail"),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the rejection record")


@dataclass(frozen=True)
class ResyncResult:
    """The typed resynchronization outcome: the deterministic
    convergence of one partition episode onto the fresh authority
    view.

    ``resync_id`` is content-derived over the full result core.
    ``base_snapshot_id``/``fresh_snapshot_id`` name the authority views
    the episode operated between (the M015 reconnect pair names the
    same views — the WORK-012 discipline across the offline
    boundary).  ``resolution_rule`` is the DECLARED rule VERBATIM (the
    LOCK-111 class).  ``divergences`` carries every detected conflict
    (typed, full provenance).  ``applied_operations`` carries every
    local admitted operation id that converged into the replica state
    (clean or conflict-won); ``rejected_operations`` carries the
    LOCK-108 resynchronization rejections; together with the
    divergence citations they account for EVERY admitted operation
    exactly once — never a silent drop, never a silent duplicate.
    ``converged_records`` is the converged replica record set (the
    fresh authority records plus the converged local subjects,
    deterministic order).
    """

    resync_id: str
    episode_id: str
    contract_id: str
    base_snapshot_id: str
    fresh_snapshot_id: str
    resolution_rule: Tuple[str, ...]
    divergences: Tuple[DivergenceRecord, ...]
    applied_operations: Tuple[str, ...]
    rejected_operations: Tuple[ConvergenceRejection, ...]
    converged_records: Tuple[OpaqueReference, ...]
    recorded_at: str
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "episode_id", _require_id(self.episode_id, "resync.episode_id")
        )
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "resync.contract_id")
        )
        object.__setattr__(
            self, "base_snapshot_id", _require_id(self.base_snapshot_id, "resync.base_snapshot_id")
        )
        object.__setattr__(
            self,
            "fresh_snapshot_id",
            _require_id(self.fresh_snapshot_id, "resync.fresh_snapshot_id"),
        )
        object.__setattr__(
            self,
            "resolution_rule",
            normalize_resolution_rule(self.resolution_rule, "resync.resolution_rule"),
        )
        if isinstance(self.divergences, (str, bytes)) or not isinstance(
            self.divergences, (tuple, list)
        ):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT, "resync.divergences must be a sequence"
            )
        for i, item in enumerate(self.divergences):
            if not isinstance(item, DivergenceRecord):
                raise LocalFirstError(
                    LocalFirstReason.INVALID_INPUT,
                    "resync.divergences[%d] must be a DivergenceRecord record" % i,
                )
        object.__setattr__(self, "divergences", tuple(self.divergences))
        object.__setattr__(
            self, "applied_operations", tuple(self.applied_operations or ())
        )
        for i, value in enumerate(self.applied_operations):
            _require_id(value, "resync.applied_operations[%d]" % i)
        if isinstance(self.rejected_operations, (str, bytes)) or not isinstance(
            self.rejected_operations, (tuple, list)
        ):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "resync.rejected_operations must be a sequence",
            )
        for i, item in enumerate(self.rejected_operations):
            if not isinstance(item, ConvergenceRejection):
                raise LocalFirstError(
                    LocalFirstReason.INVALID_INPUT,
                    "resync.rejected_operations[%d] must be a "
                    "ConvergenceRejection record" % i,
                )
        object.__setattr__(self, "rejected_operations", tuple(self.rejected_operations))
        object.__setattr__(
            self,
            "converged_records",
            _normalize_references(
                self.converged_records, "resync.converged_records", ref_kind="execution-artifact"
            ),
        )
        object.__setattr__(
            self, "recorded_at", _require_instant(self.recorded_at, "resync.recorded_at")
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "resync.provenance")
        )
        # the no-silent-loss invariant (mechanically enforced on the
        # finished record): every divergence cites its local operation,
        # and no local operation appears twice across the outcome sets
        cited = [d.local_operation_id for d in self.divergences]
        accounted = list(self.applied_operations) + [
            r.operation_id for r in self.rejected_operations
        ] + cited
        if len(accounted) != len(set(accounted)):
            raise LocalFirstError(
                LocalFirstReason.JOURNAL_DIVERGENCE,
                "the resynchronization result double-accounts a local "
                "operation (never a silent duplicate)",
            )
        # every divergence's local operation is accounted exactly once
        for divergence in self.divergences:
            if divergence.local_operation_id not in accounted:
                raise LocalFirstError(
                    LocalFirstReason.JOURNAL_DIVERGENCE,
                    "a divergence cites an operation the result does not account "
                    "for (never a silent drop)",
                )
        expected = self._derive_resync_id()
        if not self.resync_id:
            object.__setattr__(self, "resync_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.resync_id) is None:
                raise LocalFirstError(
                    LocalFirstReason.INVALID_INPUT,
                    "resync.resync_id must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.resync_id != expected:
                raise LocalFirstError(
                    LocalFirstReason.ID_MISMATCH,
                    "resync_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def _derive_resync_id(self) -> str:
        document = {
            "episode_id": self.episode_id,
            "contract_id": self.contract_id,
            "base_snapshot_id": self.base_snapshot_id,
            "fresh_snapshot_id": self.fresh_snapshot_id,
            "resolution_rule": list(self.resolution_rule),
            "divergences": [d.to_dict() for d in self.divergences],
            "applied_operations": list(self.applied_operations),
            "rejected_operations": [r.to_dict() for r in self.rejected_operations],
            "converged_records": [r.to_dict() for r in self.converged_records],
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
        }
        return _derive_id(_RESYNC_NAMESPACE, document, "the resync id document")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resync_id": self.resync_id,
            "episode_id": self.episode_id,
            "contract_id": self.contract_id,
            "base_snapshot_id": self.base_snapshot_id,
            "fresh_snapshot_id": self.fresh_snapshot_id,
            "resolution_rule": list(self.resolution_rule),
            "divergences": [d.to_dict() for d in self.divergences],
            "applied_operations": list(self.applied_operations),
            "rejected_operations": [r.to_dict() for r in self.rejected_operations],
            "converged_records": [r.to_dict() for r in self.converged_records],
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ResyncResult":
        if not isinstance(data, Mapping):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT, "the resync result must be a mapping"
            )
        with _wrap_consumed_error("the resync-result deserialization"):
            return ResyncResult(
                resync_id=data.get("resync_id") or "",
                episode_id=data.get("episode_id"),
                contract_id=data.get("contract_id"),
                base_snapshot_id=data.get("base_snapshot_id"),
                fresh_snapshot_id=data.get("fresh_snapshot_id"),
                resolution_rule=tuple(data.get("resolution_rule") or ()),
                divergences=tuple(
                    DivergenceRecord.from_dict(d) for d in data.get("divergences") or ()
                ),
                applied_operations=tuple(data.get("applied_operations") or ()),
                rejected_operations=tuple(
                    ConvergenceRejection.from_dict(r)
                    for r in data.get("rejected_operations") or ()
                ),
                converged_records=tuple(
                    OpaqueReference.from_dict(r)
                    for r in data.get("converged_records") or ()
                ),
                recorded_at=data.get("recorded_at"),
                provenance=Provenance.from_dict(data.get("provenance")),
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the resync-result record")


# ----------------------------------------------------------------------
# Import-time vocabulary consistency (fail loud on drift)
# ----------------------------------------------------------------------


def _check_vocabularies() -> None:
    """The consumed vocabularies must be exactly the frozen sets this
    domain was built against (fail loud on drift — never silently
    mis-project)."""
    if TIE_BREAK_KEYS != ("candidate-kind", "candidate-id"):
        raise LocalFirstError(
            LocalFirstReason.VOCABULARY,
            "the consumed M008 tie-break key vocabulary has drifted from the "
            "frozen two-key set this domain resolves conflicts through",
        )
    if set(CONSTRAINT_KINDS) != {
        "latency-bound",
        "throughput-floor",
        "availability-floor",
        "loss-bound",
        "jitter-bound",
        "isolation",
        "jurisdiction",
        "security-level",
        "provider-trust",
        "evidence-obligation",
        "geography",
        "priority",
    }:
        raise LocalFirstError(
            LocalFirstReason.VOCABULARY,
            "the consumed contracts constraint-kind vocabulary has drifted "
            "from the frozen 12-kind set",
        )
    if RUNTIME_STATES != (
        "PENDING",
        "ACTIVE",
        "RECONNECTING",
        "DEGRADED",
        "FAILED",
        "TERMINATED",
    ):
        raise LocalFirstError(
            LocalFirstReason.VOCABULARY,
            "the consumed M015 runtime-state vocabulary has drifted (the "
            "offline composition drives that lifecycle)",
        )
    if DEFAULT_RESOLUTION_RULE != ("candidate-kind", "candidate-id"):
        raise LocalFirstError(
            LocalFirstReason.VOCABULARY,
            "the default declared resolution rule has drifted from the "
            "consumed DEFAULT_TIE_BREAK shape",
        )
    for kind in OPERATION_KINDS:
        required, _ = _KIND_MEMBER_RULES[kind]
        if any(
            name
            not in _ADMISSION_ONLY_MEMBERS
            + _PARTITION_MEMBERS
            + _EXIT_MEMBERS
            + ("subject",)
            for name in required
        ):
            raise LocalFirstError(
                LocalFirstReason.VOCABULARY,
                "the offline record kind %r carries an unknown required member "
                "(drift guard)" % kind,
            )


_check_vocabularies()
