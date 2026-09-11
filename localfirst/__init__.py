"""ADCOS local-first package (M016 — Local-First and Offline
Operation).

The local-first/offline operation domain of the R8 charter (R8-CORE-001,
DEC-0115 the current-child state; composing the accepted authorities
BY REFERENCE — import and compose, never reimplement, weaken, fork,
or bypass):

- **Deterministic offline operation journals** (:mod:`localfirst.journal`):
  ordered, idempotent, replayable records of operations captured while
  partitioned.  The journal discipline conventions of the accepted
  ``resilience/journal.py`` are consumed as CONVENTIONS (ordered,
  gapless, conflict-free, kind/member-disciplined, tamper-evident
  identities, construction-is-recovery) — this is its OWN typed
  surface, never a fork of the runtime journal.  The append is
  IDEMPOTENT (an operation retried while partitioned derives the same
  position-independent content identity and never double-applies), and
  the fold is the sole writer of local state.
- **Partition-tolerant admission with fail-closed stale-authority
  rejection** (:mod:`localfirst.admission`): a local authority snapshot
  past its declared freshness bound NEVER silently authorizes — the
  admission decisions carry the authority's declared freshness window;
  expiry is the typed ``localfirst-authority-stale`` rejection (and a
  pre-window instant the typed
  ``localfirst-authority-not-yet-valid`` rejection), with the journal
  fold MECHANICALLY rejecting a forged admitted record outside its
  carried window.  LOCK-108 across the offline boundary: the claimed
  constraint set is validated through the ACCEPTED M008 gates
  (``replan.validate_constraints_preserved``, consumed BY REFERENCE) —
  a set that drops, relaxes or re-interprets ANY hard constraint is
  REJECTED with the typed reason citing the specific kinds.
- **Explicit reconnect and resynchronization with divergence detection
  and deterministic convergence** (:mod:`localfirst.resync`):
  conflicting offline operations resolve by the DECLARED RECORDED
  rule (the LOCK-111 class: both sides projected onto the orderable
  candidate shape over the CONSUMED M008 tie-break key vocabulary —
  content keys only, never temporal, never random), never silently
  dropped or duplicated; divergence records are typed with full
  provenance on BOTH sides, and the finished result MECHANICALLY
  enforces the no-silent-loss invariant (every admitted operation is
  accounted exactly once across the applied set, the divergence
  citations and the typed LOCK-108 rejections).
- **Degraded-mode operation that is explicit and journaled**
  (:mod:`localfirst.offline`): entering/leaving offline/degraded
  operation is a journaled event with typed provenance — the M015
  degraded-mode discipline extended across the offline boundary.
- **The M015 composition substrate** (:mod:`localfirst.offline`): the
  accepted ``resilience/`` runtime (``RuntimeStore``, the lifecycle
  states, the reconnect discipline) is driven BY REFERENCE for every
  offline transition — the partition entry is the accepted
  ``enter_degraded`` (LOCK-106 ``observation`` evidence kind, the
  episode id as the decision-kinded evidence reference), the
  resynchronization is the accepted explicit reconnect pair naming
  BOTH the OLD and the NEW authority-view references (the WORK-012
  discipline, mechanically enforced by the accepted fold), and the
  journaled offline entry/exit records carry the runtime EVENT and
  EVIDENCE ids as the evidence-visible composition links.

Authority boundaries (the layering contract, frozen 1.1):

- **LOCK-101/LOCK-117**: contracts/ stays the sole authority; the
  local-first records ride the contract as opaque references, cite
  contract ids, never re-derive contract identity, and never become a
  second contract authority.  The claimed constraint sets riding the
  journal records are optimizer-supplied DATA re-validated by the
  consumed M008 gates at admission AND at resynchronization (the
  ``ReplanCandidate`` precedent).  Imports flow one way:
  ``localfirst/`` imports the accepted authorities (contracts,
  replan, resilience); NO accepted authority imports ``localfirst/``.
- **LOCK-108 (the core discipline, across the offline boundary)**:
  every local admission and every resynchronization step that would
  weaken ANY hard contract constraint is REJECTED with the typed
  reason citing the kinds — never a silent weakening during partition
  or resynchronization.
- **LOCK-111**: conflict resolution is deterministic with DECLARED
  injected recorded rules over the CONSUMED M008 content-key
  vocabulary; same inputs -> the byte-identical resolution.
- **LOCK-119**: no wall clock, no randomness, no network, no secrets;
  content-derived ids over canonical JSON; canonical-JSON round-trips
  with tamper-evident ids.

Harvest disclosure (R8 charter M016 scope): the legacy 1.0 reservoir
(``sessions/``, ``mobility/``, ``multipath/``, ``edge/``,
``appliance/``) is SOURCE MATERIAL ONLY — the WORK-012 journaling
discipline (the append-only deterministic fold), the handover
resynchronization semantics and the edge/offline operational patterns
are studied and RE-EXPRESSED on the 1.1 authority inside this package;
the legacy packages are NOT imported, NOT modified (their M008
docstring disclosures stay byte-identical), and remain their own
authorities for their existing consumers.
"""

from __future__ import annotations

from .errors import LocalFirstError, LocalFirstReason
from .model import (
    ADMISSION_OUTCOMES,
    DEFAULT_RESOLUTION_RULE,
    DIVERGENCE_RESOLUTIONS,
    EPISODE_STATES,
    LOCALFRESH_ISSUER,
    OPERATION_KINDS,
    RESOLUTION_CANDIDATE_KINDS,
    RESYNC_DRIVEN_ISSUER,
    AuthoritySnapshot,
    ConvergenceRejection,
    DivergenceRecord,
    LocalState,
    OfflineOperation,
    ResyncResult,
    check_episode_state,
    derive_episode_id,
    derive_operation_id,
    derive_snapshot_id,
    normalize_resolution_rule,
    resolve_conflict,
)
from .journal import (
    OfflineJournal,
    fold_operations,
)
from .admission import (
    admit_operation,
    authority_snapshot,
    check_admission_preserves_contract,
    check_authority_fresh,
)
from .resync import resynchronize
from .offline import (
    CloseResult,
    attach_runtime_session,
    close_partition,
    local_admit,
    open_partition,
    sync_authority_view,
)

__all__ = [
    # typed errors
    "LocalFirstError",
    "LocalFirstReason",
    # frozen vocabularies
    "OPERATION_KINDS",
    "ADMISSION_OUTCOMES",
    "EPISODE_STATES",
    "RESOLUTION_CANDIDATE_KINDS",
    "DIVERGENCE_RESOLUTIONS",
    "DEFAULT_RESOLUTION_RULE",
    # typed records
    "AuthoritySnapshot",
    "OfflineOperation",
    "LocalState",
    "DivergenceRecord",
    "ConvergenceRejection",
    "ResyncResult",
    "CloseResult",
    # the pure kernels
    "check_episode_state",
    "check_authority_fresh",
    "check_admission_preserves_contract",
    "derive_episode_id",
    "derive_operation_id",
    "derive_snapshot_id",
    "normalize_resolution_rule",
    "resolve_conflict",
    # the offline journal (the fold is the sole writer of local state)
    "OfflineJournal",
    "fold_operations",
    "LOCALFRESH_ISSUER",
    "RESYNC_DRIVEN_ISSUER",
    # partition-tolerant admission
    "admit_operation",
    "authority_snapshot",
    # reconnect + resynchronization
    "resynchronize",
    # the M015 composition substrate (the offline transitions)
    "attach_runtime_session",
    "sync_authority_view",
    "open_partition",
    "local_admit",
    "close_partition",
]
