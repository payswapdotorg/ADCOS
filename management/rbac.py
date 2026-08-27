"""Management-plane RBAC authority (WORK-030): the role-assignment
store.

Ownership: ``/management`` owns the operator role-assignment state
(the RBAC plane).  It owns NO identity truth -- operator references
are opaque strings resolved by EXACT match against assignment records;
canonical NodeID enforcement for privileged actions happens inside the
WORK-010 policy authority (the evaluation context validates the
requester id fail-closed), so the management plane never becomes a
second identity authority (LOCK: no duplicate identity authority).

Design (the accepted closure-owned authority discipline -- the
WORK-027 PolicyRevalidationAuthority precedent):

- the assignment history is an IMMUTABLE tuple held in closure cells
  of the constructor frame, rebound only via ``nonlocal`` by the
  genuine grant/revoke code paths -- there is NO instance attribute
  holding the ledger, so post-construction attribute mutation or
  shadowing can never rewrite RBAC history;
- the public callables' closure cells hold DATA ONLY (the immutable
  history tuple, the immutable catalog tuple, the role-id set, and
  the synchronization lock): every helper they use is module-level,
  so no nested callable capability is extractable from any closure
  cell (the same mechanical bar the accepted WORK-027 battery
  enforces) and no mutable collection is reachable;
- the log is APPEND-ONLY: there is no mutation or removal API at all;
  revocation is a new event (auditable history), never a rewrite;
- resolution is a deterministic fold over the log evaluated at an
  INJECTED instant (never the wall clock): only events that have
  already happened (``event.instant <= now``) participate, the last
  such event per (operator, role) wins, and a GRANT is active only
  inside its optional validity window (inclusive bounds).  Expired,
  revoked, not-yet-granted, and never-granted all yield "no
  capability" -- deny-by-default (P6 least authority).

Bootstrap: initial assignments are CONSTRUCTOR-INJECTED deployment
configuration (like the initial policy material a node ships with);
every later mutation flows through :meth:`RoleAssignmentStore.grant` /
:meth:`RoleAssignmentStore.revoke`, which the management API exposes
ONLY behind the policy-gated ``management.role-assign`` operation (see
``management.api``).
"""

from __future__ import annotations

import threading
from typing import Any, Dict, FrozenSet, Set, Tuple

from .errors import ManagementError, ManagementReasonCode
from .model import (
    RoleAssignmentEvent,
    RoleDefinition,
    RoleEventKind,
    derive_role_event_id,
    instant_lt,
    require_instant,
    validate_role_catalog,
)

#: The closure-captured history type (typing aid only).
_History = Tuple[RoleAssignmentEvent, ...]


def _validate_operator_ref(value: object, label: str) -> str:
    """Operator references are opaque non-empty strings in the
    management plane (exact-match resolution; canonical-form
    enforcement for privileged actions lives in the WORK-010 context
    validation -- management is not an identity authority)."""
    if not isinstance(value, str) or not value:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "%s must be a non-empty operator reference string" % label,
        )
    if len(value) > 256:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "%s exceeds 256 characters" % label,
        )
    return value


def _materialize(
    kind: str,
    operator_node_id: str,
    role_id: str,
    instant: str,
    actor_node_id: str,
    reason: str,
    valid_from: str,
    valid_until: str,
) -> RoleAssignmentEvent:
    """Build a genuine event with its content-derived id (the id is
    minted from the content, never caller-supplied)."""
    probe = RoleAssignmentEvent(
        event_id="0" * 64,
        kind=kind,
        operator_node_id=operator_node_id,
        role_id=role_id,
        instant=instant,
        actor_node_id=actor_node_id,
        reason=reason,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    return RoleAssignmentEvent(
        event_id=derive_role_event_id(probe),
        kind=probe.kind,
        operator_node_id=probe.operator_node_id,
        role_id=probe.role_id,
        instant=probe.instant,
        actor_node_id=probe.actor_node_id,
        reason=probe.reason,
        valid_from=probe.valid_from,
        valid_until=probe.valid_until,
    )


def _fold_active_pairs(
    history: _History, now: str
) -> FrozenSet[Tuple[str, str]]:
    """The deterministic fold (a module-level PURE function so the
    public callables' closure cells hold DATA ONLY): the
    {(operator, role)} pairs active at ``now``.

    Only events that have already happened (``event.instant <= now``)
    participate: the last such event per pair wins, a GRANT must
    additionally sit inside its optional validity window (inclusive
    bounds), and anything absent -- expired, revoked,
    not-yet-granted, never-granted -- yields no capability
    (deny-by-default)."""
    latest: Dict[Tuple[str, str], RoleAssignmentEvent] = {}
    for event in history:
        if instant_lt(now, event.instant):
            continue  # event is in the future -- has not happened
        latest[(event.operator_node_id, event.role_id)] = event
    pairs: Set[Tuple[str, str]] = set()
    for (operator, role_id), event in latest.items():
        if event.kind != RoleEventKind.GRANT:
            continue
        if event.valid_from and instant_lt(now, event.valid_from):
            continue  # window not yet open
        if event.valid_until and instant_lt(event.valid_until, now):
            continue  # window closed (inclusive upper bound)
        pairs.add((operator, role_id))
    return frozenset(pairs)


class RoleAssignmentStore:
    """The append-only role-assignment (RBAC) authority.

    Construct with a frozen role catalog and optional deployment-time
    initial assignment events.  All state changes thereafter are
    append-only grant/revoke events.
    """

    def __init__(
        self,
        roles: Tuple[RoleDefinition, ...] = (),
        initial_events: Tuple[RoleAssignmentEvent, ...] = (),
    ) -> None:
        validate_role_catalog(roles)
        role_ids = frozenset(role.role_id for role in roles)
        # Validate initial events against the catalog BEFORE any
        # closure state exists (fail-closed construction).
        for event in initial_events:
            if not isinstance(event, RoleAssignmentEvent):
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "initial_events entries must be RoleAssignmentEvent "
                    "instances",
                )
            if event.role_id not in role_ids:
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "initial event references role %r which is not in "
                    "the catalog" % event.role_id,
                )

        history: _History = tuple(initial_events)
        catalog: Tuple[RoleDefinition, ...] = roles
        lock = threading.Lock()

        def grant(
            operator_node_id: str,
            role_id: str,
            *,
            instant: str,
            actor_node_id: str,
            reason: str = "",
            valid_from: str = "",
            valid_until: str = "",
        ) -> RoleAssignmentEvent:
            """Append a GRANT event (fail-closed validation; append
            only -- the immutable history tuple is rebound under the
            lock; there is no other mutation primitive).  Granting a
            role that is ALREADY active at ``instant`` fails closed --
            a duplicate grant is an operational error, not an
            idempotent no-op (the RBAC log stays meaningful)."""
            nonlocal history
            _validate_operator_ref(operator_node_id, "operator_node_id")
            _validate_operator_ref(actor_node_id, "actor_node_id")
            require_instant(instant, "role event instant")
            if role_id not in role_ids:
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "role %r is not in the frozen catalog" % role_id,
                )
            if (operator_node_id, role_id) in _fold_active_pairs(
                history, instant
            ):
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "role %r is already active for %r at %s (duplicate "
                    "grant fails closed)"
                    % (role_id, operator_node_id, instant),
                )
            event = _materialize(
                RoleEventKind.GRANT,
                operator_node_id,
                role_id,
                instant,
                actor_node_id,
                reason,
                valid_from,
                valid_until,
            )
            with lock:
                history = history + (event,)
            return event

        def revoke(
            operator_node_id: str,
            role_id: str,
            *,
            instant: str,
            actor_node_id: str,
            reason: str = "",
        ) -> RoleAssignmentEvent:
            """Append a REVOKE event.  Revoking an assignment that is
            not currently granted fails closed (revocation is an
            operational act against a live grant, not a prophylactic
            no-op -- a mistyped operator/role pair must surface)."""
            nonlocal history
            _validate_operator_ref(operator_node_id, "operator_node_id")
            _validate_operator_ref(actor_node_id, "actor_node_id")
            require_instant(instant, "role event instant")
            if role_id not in role_ids:
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "role %r is not in the frozen catalog" % role_id,
                )
            if (operator_node_id, role_id) not in _fold_active_pairs(
                history, instant
            ):
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "cannot revoke %r for %r: the assignment is not "
                    "active at %s" % (role_id, operator_node_id, instant),
                )
            event = _materialize(
                RoleEventKind.REVOKE,
                operator_node_id,
                role_id,
                instant,
                actor_node_id,
                reason,
                "",
                "",
            )
            with lock:
                history = history + (event,)
            return event

        def active_roles(
            operator_node_id: str, *, now: str
        ) -> Tuple[str, ...]:
            """The operator's active role ids at ``now`` (deterministic
            sorted order; empty when nothing is granted)."""
            _validate_operator_ref(operator_node_id, "operator_node_id")
            require_instant(now, "now")
            return tuple(
                sorted(
                    role_id
                    for (operator, role_id) in _fold_active_pairs(history, now)
                    if operator == operator_node_id
                )
            )

        def active_capabilities(
            operator_node_id: str, *, now: str
        ) -> FrozenSet[str]:
            """The operator's effective capabilities at ``now``: the
            UNION of capabilities over active role assignments
            (additive roles).  Deny-by-default: an operator with no
            active assignment holds NOTHING."""
            _validate_operator_ref(operator_node_id, "operator_node_id")
            require_instant(now, "now")
            caps: Set[str] = set()
            by_id = {role.role_id: role for role in catalog}
            for role_id in (
                role_id
                for (operator, role_id) in _fold_active_pairs(history, now)
                if operator == operator_node_id
            ):
                caps.update(by_id[role_id].capabilities)
            return frozenset(caps)

        def events() -> Tuple[RoleAssignmentEvent, ...]:
            """The full append-only history (read-only tuple)."""
            return history

        def snapshot() -> Dict[str, Any]:
            """A JSON-shaped read-only snapshot (deterministic)."""
            return {
                "roles": [role.content_dict() for role in catalog],
                "events": [event.content_dict() for event in history],
                "event_count": len(history),
            }

        def catalog_roles() -> Tuple[RoleDefinition, ...]:
            """The frozen role catalog (read-only)."""
            return catalog

        # The public surface: EXACTLY these instance-attribute
        # callables.  The history/catalog live in closure cells only
        # (data + lock; every helper is module-level).
        self.grant = grant
        self.revoke = revoke
        self.active_roles = active_roles
        self.active_capabilities = active_capabilities
        self.events = events
        self.snapshot = snapshot
        self.catalog_roles = catalog_roles

    # ------------------------------------------------------------------
    # Surface audit aid (used by the self-test battery to prove the
    # closure-owned discipline; not a mutation path).
    # ------------------------------------------------------------------

    def public_surface(self) -> Tuple[str, ...]:
        """The sorted names of the public instance-attribute callables
        (the complete public surface of this object)."""
        return tuple(sorted(k for k in vars(self) if not k.startswith("_")))

    def __repr__(self) -> str:  # pragma: no cover -- trivial
        return "RoleAssignmentStore(events=%d)" % len(self.events())


__all__ = [
    "RoleAssignmentStore",
]
