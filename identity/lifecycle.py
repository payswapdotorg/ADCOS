"""Credential/key lifecycle states and transitions (WORK-004 section 7).

States:

    PROVISIONED -> ACTIVE        (activation)
    ACTIVE -> ROTATING           (rotation begins)
    ROTATING -> SUPERSEDED       (rotation completes for the old key)
    PROVISIONED/ACTIVE/ROTATING/SUPERSEDED -> REVOKED   (revocation)
    PROVISIONED/ACTIVE/ROTATING/EXPIRED-candidates -> EXPIRED (expiry)

REVOKED and EXPIRED are terminal. Re-activation of superseded/revoked/
expired credentials is forbidden (fail closed). Expiry and revocation
are distinct concepts: expiry is a time-based transition evaluated
against an injected clock; revocation is an explicit administrative act
carrying metadata.

Transitions are data (the table below); validation is deterministic and
invalid transitions raise LifecycleError.
"""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet, Mapping


class LifecycleState(Enum):
    PROVISIONED = "provisioned"
    ACTIVE = "active"
    ROTATING = "rotating"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"
    EXPIRED = "expired"

    @property
    def terminal(self) -> bool:
        return self in (LifecycleState.REVOKED, LifecycleState.EXPIRED)


#: Legal transitions: from -> set(to).
_LEGAL_TRANSITIONS: Mapping[LifecycleState, FrozenSet[LifecycleState]] = {
    LifecycleState.PROVISIONED: frozenset(
        {LifecycleState.ACTIVE, LifecycleState.REVOKED, LifecycleState.EXPIRED}
    ),
    LifecycleState.ACTIVE: frozenset(
        {LifecycleState.ROTATING, LifecycleState.REVOKED, LifecycleState.EXPIRED}
    ),
    LifecycleState.ROTATING: frozenset(
        {LifecycleState.SUPERSEDED, LifecycleState.REVOKED, LifecycleState.EXPIRED}
    ),
    LifecycleState.SUPERSEDED: frozenset({LifecycleState.REVOKED}),
    LifecycleState.REVOKED: frozenset(),
    LifecycleState.EXPIRED: frozenset(),
}


class LifecycleError(ValueError):
    """Raised when a lifecycle transition is invalid (fails closed)."""

    def __init__(self, current: "LifecycleState", target: "LifecycleState") -> None:
        self.current = current
        self.target = target
        super().__init__(
            "invalid lifecycle transition: %s -> %s (legal transitions from %s: %s)"
            % (current.value, target.value, current.value, _legal_targets_text(current))
        )


def _legal_targets_text(state: "LifecycleState") -> str:
    targets = sorted(t.value for t in _LEGAL_TRANSITIONS[state])
    return "[%s]" % ", ".join(targets) if targets else "none (terminal)"


def can_transition(current: "LifecycleState", target: "LifecycleState") -> bool:
    return target in _LEGAL_TRANSITIONS[current]


def transition(current: "LifecycleState", target: "LifecycleState") -> "LifecycleState":
    """Deterministic, fail-closed transition. Returns the target state."""
    if not isinstance(current, LifecycleState) or not isinstance(target, LifecycleState):
        raise LifecycleError(
            current if isinstance(current, LifecycleState) else LifecycleState.PROVISIONED,
            target if isinstance(target, LifecycleState) else LifecycleState.PROVISIONED,
        )
    if not can_transition(current, target):
        raise LifecycleError(current, target)
    return target
