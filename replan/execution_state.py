"""ADCOS replan execution-state surface (M008 — Replan and Failover).

**The disclosed harvest seam.**  The WORK-era execution packages are
harvested onto the Architecture 1.1 authority here, BY REFERENCE
(one-way: this module imports their frozen public APIs; they never
import ``replan/``):

- ``sessions/`` (WORK-012) — the session lifecycle discipline becomes
  THE execution-state surface replan operates over:
  :func:`session_realization_snapshot` projects a session onto the
  M008-owned realization-state vocabulary through the FROZEN mapping
  table :data:`SESSION_STATE_MAP`, and :func:`reconnect_history`
  re-reads the explicit reconnect events (old AND new route
  references, append-only) as typed replan evidence — the WORK-012
  authority rules (never recompute, never silently replace the route)
  are PRESERVED, never bypassed: a reconnect event missing either
  side of the route change fails closed with
  ``replan-silent-replacement``;
- ``mobility/`` (WORK-014) — :func:`handover_surface` reads the
  prepared/committed mobility handover transactions for a session
  (the handover alternative models the replan engine selects among,
  by reference);
- ``multipath/`` (WORK-013) — :func:`multipath_surface` reads the
  session's multipath plan constituents (the multi-path alternative
  models the replan engine selects among, by reference).

None of the harvested packages is modified here (the R7 charter's
minimal-consistent-refactor discipline, the M006 composition-harvest
precedent): their public APIs, authority boundaries and batteries are
preserved verbatim; the harvest direction is one-way and disclosed at
both ends (their module docstrings carry the M008 disclosure).

Determinism (LOCK-119): read-only views over injected-instant stores;
no wall clock, no randomness, no network, no secrets; content-derived
ids over WORK-003 canonical JSON; canonical-JSON round-trips.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

from contracts import OpaqueReference, Provenance

from mobility import MobilityStore
from multipath import MultipathStore
from sessions import (
    META_NEW_PATH_EXPIRES_AT,
    META_NEW_PATH_ID,
    META_NEW_ROUTE_DECISION_ID,
    META_OLD_PATH_ID,
    META_OLD_ROUTE_DECISION_ID,
    RECONNECT_EVENT_TYPE,
    SessionStore,
)

from .errors import ReplanError, ReplanReason
from .model import RealizationSnapshot, ReconnectRecord

#: The FROZEN WORK-012 session-state -> M008 realization-state
#: mapping (the disclosed harvest projection — one-way, additive over
#: the frozen session vocabulary, never a re-interpretation of it):
#:
#: - ``ESTABLISHED`` / ``RECONNECTING`` / ``SUSPENDED`` -> ``REALIZING``
#:   (the session is the active realization; RECONNECTING is the
#:   explicit WORK-012 transitional state of an in-progress route
#:   change — still the same realization, never a silent replacement);
#: - ``DEGRADED`` -> ``DEGRADED`` (the explicit degraded session
#:   state IS the explicit degraded realization — frozen §9);
#: - ``FAILED`` -> ``FAILED`` (terminal);
#: - ``TERMINATED`` / ``TERMINATING`` -> NOT a replan surface (a
#:   deliberately terminated session is a lifecycle decision, not a
#:   failure — the snapshot fails closed with
#:   ``replan-realization-terminal``);
#: - ``REQUESTED`` / ``AUTHORIZED`` -> NOT a replan surface (no
#:   established realization exists yet — fails closed with
#:   ``replan-realization-not-established``).
SESSION_STATE_MAP: Tuple[Tuple[str, str], ...] = (
    ("ESTABLISHED", "REALIZING"),
    ("RECONNECTING", "REALIZING"),
    ("SUSPENDED", "REALIZING"),
    ("DEGRADED", "DEGRADED"),
    ("FAILED", "FAILED"),
)

#: The session states that fail closed as deliberate terminations
#: (never a replan surface).
_SESSION_TERMINAL_STATES: Tuple[str, ...] = ("TERMINATED", "TERMINATING")

#: The session states that fail closed as pre-establishment (no
#: realization to replan yet).
_SESSION_PRE_ESTABLISHMENT_STATES: Tuple[str, ...] = ("REQUESTED", "AUTHORIZED")

#: The default issuer recorded on harvest-view provenance (LOCK-118:
#: the seam asserts the projection; the underlying stores stay their
#: own authorities).
HARVEST_VIEW_ISSUER = "replan:execution-state"

#: The mobility transaction states that count as open handover
#: alternatives (a PREPARED transaction is the open, validated,
#: mutation-free handover candidate the replan engine may select; a
#: COMMITTED transaction is history — its effect is visible through
#: the session's own current-route members and reconnect events).
_OPEN_HANDOVER_STATES: Tuple[str, ...] = ("PREPARED",)

#: The multipath constituent statuses that count as available
#: alternatives (the non-terminal constituents: an ACTIVE path is
#: immediately usable; a DEGRADED path is still a plannable
#: constituent — the WORK-013 table allows its explicit recovery —
#: while FAILED is terminal and never an alternative).
_AVAILABLE_PATH_STATUSES: Tuple[str, ...] = ("ACTIVE", "DEGRADED")


def session_realization_snapshot(
    store: SessionStore,
    session_id: str,
    contract_id: str,
    *,
    observed_at: str,
    provenance: Optional[Provenance] = None,
) -> RealizationSnapshot:
    """Project one WORK-012 session onto the M008 realization view.

    Fail-closed gates: the store must be a WORK-012 ``SessionStore``
    (the harvest surface is consumed by reference, never re-implemented),
    the session must exist (unknown session -> typed error), and the
    session state must map onto a replannable realization state (the
    FROZEN :data:`SESSION_STATE_MAP` — deliberately terminated and
    pre-establishment sessions are not replan surfaces, and the
    mapping says so with typed reasons, never a silent downgrade).

    The snapshot cites the session id, the CURRENT route references
    (the session's authoritative current-route members — only the
    explicit WORK-012 reconnect operation ever updates them) and the
    current path as an opaque execution-artifact reference (LOCK-117:
    DATA, never authority).
    """
    if not isinstance(store, SessionStore):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "session_realization_snapshot requires a WORK-012 SessionStore "
            "(the harvested surface is consumed by reference — got %s)"
            % type(store).__name__,
        )
    if not isinstance(session_id, str) or not session_id:
        raise ReplanError(ReplanReason.INVALID_INPUT, "session_id must be a non-empty string")
    session = store.get(session_id)
    if session is None:
        raise ReplanError(
            ReplanReason.REALIZATION_TERMINAL,
            "session %s is unknown to the session store (fail-closed: the "
            "execution-state surface never invents a session)" % session_id[:32],
        )
    if session.state in _SESSION_TERMINAL_STATES:
        raise ReplanError(
            ReplanReason.REALIZATION_TERMINAL,
            "session %s is in the deliberate %s state — a deliberately "
            "terminated session is not a replan surface"
            % (session_id[:32], session.state),
        )
    if session.state in _SESSION_PRE_ESTABLISHMENT_STATES:
        raise ReplanError(
            ReplanReason.REALIZATION_NOT_ESTABLISHED,
            "session %s is in the pre-establishment %s state — no realized "
            "connectivity exists to replan yet" % (session_id[:32], session.state),
        )
    mapped = dict(SESSION_STATE_MAP).get(session.state)
    if mapped is None:
        # unreachable post-construction (the frozen WORK-012 vocabulary
        # is fully covered above); kept as a closed guard
        raise ReplanError(
            ReplanReason.VOCABULARY,
            "session state %r has no frozen realization mapping" % session.state,
        )
    view_provenance = provenance if provenance is not None else Provenance(
        issuer=HARVEST_VIEW_ISSUER,
        decision_refs=(session_id,),
    )
    if not isinstance(view_provenance, Provenance):
        raise ReplanError(
            ReplanReason.INVALID_INPUT, "provenance must be a Provenance record"
        )
    return RealizationSnapshot(
        contract_id=contract_id,
        surface="session",
        state=mapped,
        observed_at=observed_at,
        session_ref=session.session_id,
        route_refs=(session.current_route_decision_id,),
        artifact_refs=(
            OpaqueReference(
                ref_kind="execution-artifact",
                value=session.current_path_id,
                provenance=Provenance(
                    issuer=HARVEST_VIEW_ISSUER,
                    decision_refs=(session.session_id,),
                ),
            ),
        ),
        provenance=view_provenance,
    )


def reconnect_history(store: SessionStore, session_id: str) -> Tuple[ReconnectRecord, ...]:
    """Re-read the explicit reconnect events of one session as typed
    replan evidence (the WORK-012 discipline, PRESERVED and enforced).

    Every ``reconnected`` event in the session's append-only history
    must carry BOTH the old AND the new route references (the four
    meta members) — an event missing either side fails closed with
    ``replan-silent-replacement`` (a route change is ALWAYS an
    explicit lifecycle event recording old and new; never a silent
    replacement).  Returns the typed records in the session's own
    deterministic event order (append-only sequence).
    """
    if not isinstance(store, SessionStore):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "reconnect_history requires a WORK-012 SessionStore (got %s)"
            % type(store).__name__,
        )
    if not isinstance(session_id, str) or not session_id:
        raise ReplanError(ReplanReason.INVALID_INPUT, "session_id must be a non-empty string")
    session = store.get(session_id)
    if session is None:
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "session %s is unknown to the session store" % session_id[:32],
        )
    records: list = []
    for event in store.get_events(session_id):
        if event.event_type != RECONNECT_EVENT_TYPE:
            continue
        meta = dict(event.metadata or ())
        required = (
            META_OLD_ROUTE_DECISION_ID,
            META_NEW_ROUTE_DECISION_ID,
            META_OLD_PATH_ID,
            META_NEW_PATH_ID,
            META_NEW_PATH_EXPIRES_AT,
        )
        missing = [key for key in required if not meta.get(key)]
        if missing:
            raise ReplanError(
                ReplanReason.SILENT_REPLACEMENT,
                "reconnect event %s is missing the route-change members %s "
                "(the WORK-012 discipline requires BOTH the old AND the new "
                "route references on every reconnect — a route change is "
                "never a silent replacement)"
                % (event.event_id[:32], ", ".join(sorted(missing))),
            )
        records.append(
            ReconnectRecord(
                session_id=session_id,
                event_id=event.event_id,
                reconnect_instant=event.event_instant,
                old_route_decision_id=meta[META_OLD_ROUTE_DECISION_ID],
                new_route_decision_id=meta[META_NEW_ROUTE_DECISION_ID],
                old_path_id=meta[META_OLD_PATH_ID],
                new_path_id=meta[META_NEW_PATH_ID],
                new_path_expires_at=meta[META_NEW_PATH_EXPIRES_AT],
            )
        )
    return tuple(records)


def handover_surface(
    store: MobilityStore, session_id: str
) -> Tuple[Tuple[str, str, str], ...]:
    """Read the open mobility handover alternatives for one session.

    Returns ``(transaction_id, candidate_path_id, candidate_route_
    decision_id)`` triples for every PREPARED handover transaction
    the WORK-014 store carries for the session — the handover
    alternative models the replan engine selects among, consumed BY
    REFERENCE (the mobility store stays the authority; this view
    never prepares, commits or cancels a handover — a COMMITTED
    handover's effect is read through the session surface instead).

    Deterministic order: the store's own ``get_transactions`` order
    (append-only transaction history), preserved verbatim.
    """
    if not isinstance(store, MobilityStore):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "handover_surface requires a WORK-014 MobilityStore (got %s)"
            % type(store).__name__,
        )
    if not isinstance(session_id, str) or not session_id:
        raise ReplanError(ReplanReason.INVALID_INPUT, "session_id must be a non-empty string")
    triples: list = []
    for transaction in store.get_transactions(session_id):
        if transaction.state not in _OPEN_HANDOVER_STATES:
            continue
        triples.append(
            (
                transaction.transaction_id,
                transaction.candidate_binding.path_id,
                transaction.candidate_binding.route_decision_id,
            )
        )
    return tuple(triples)


def multipath_surface(
    store: MultipathStore, session_id: str
) -> Tuple[Tuple[str, str], ...]:
    """Read the multipath alternative paths for one session.

    Returns ``(path_id, route_decision_id)`` pairs for every AVAILABLE
    constituent path (ACTIVE/STANDBY) of the session's WORK-013
    multipath plan — the multi-path alternative models the replan
    engine selects among, consumed BY REFERENCE (the multipath plan
    stays the authority; this view never adds, removes or re-statuses
    a path).  Deterministic order: the plan's own ``path_id``-sorted
    entries, preserved verbatim.
    """
    if not isinstance(store, MultipathStore):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "multipath_surface requires a WORK-013 MultipathStore (got %s)"
            % type(store).__name__,
        )
    if not isinstance(session_id, str) or not session_id:
        raise ReplanError(ReplanReason.INVALID_INPUT, "session_id must be a non-empty string")
    plan = store.get_plan(session_id)
    if plan is None:
        return ()
    pairs: list = []
    for entry in plan.entries:
        if entry.status in _AVAILABLE_PATH_STATUSES:
            pairs.append((entry.path_id, entry.route_decision_id))
    return tuple(pairs)
