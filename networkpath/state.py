"""WORK-041 NetworkPath lifecycle vocabulary.

The frozen five-state lifecycle the W041 contract requires, keeping
path DETECTION, VALIDATION, BINDING, ACTIVATION, and RETIREMENT
explicitly separated:

    DISCOVERED -> VALIDATED -> BOUND -> ACTIVE -> RETIRED

Vocabulary provenance (the contract's own words, so no conflicting
state names are invented):

- ``DISCOVERED / VALIDATED / BOUND / ACTIVE / RETIRED`` come directly
  from the W041 ready-candidate contract and the WORK-041-CORE-001
  authorization (``discover/validate/bind/activate/retire``).
- The WORK-013 constituent-status vocabulary (``ACTIVE / DEGRADED /
  FAILED``) is a DIFFERENT concern: it describes constituents of an
  accepted multipath plan.  A NetworkPath that reaches ``ACTIVE`` may
  be consumed by the multipath authority as a constituent where that
  authority admits it; degradation of a constituent is then recorded
  by THAT authority in ITS vocabulary.  The NetworkPath lifecycle
  never reuses or redefines WORK-013 states.

Fail-closed discipline: ``RETIRED`` is terminal (a retired path can
never return to ``ACTIVE``); ``ACTIVE`` is reachable ONLY through
``BOUND`` (an unvalidated or unbound candidate can never activate);
every illegal transition is rejected by :func:`transition_is_legal`
returning ``False`` -- callers fail closed on it.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Tuple


class NetworkPathState:
    """The frozen NetworkPath lifecycle states (W041 contract)."""

    DISCOVERED = "DISCOVERED"
    VALIDATED = "VALIDATED"
    BOUND = "BOUND"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.DISCOVERED,
            cls.VALIDATED,
            cls.BOUND,
            cls.ACTIVE,
            cls.RETIRED,
        )

    @classmethod
    def terminal_values(cls) -> Tuple[str, ...]:
        return (cls.RETIRED,)


#: The frozen lifecycle transition table.  A candidate may be retired
#: (discarded) from any non-terminal state; ``ACTIVE`` is reachable
#: only from ``BOUND``; ``RETIRED`` has no outgoing edges.
LIFECYCLE_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    NetworkPathState.DISCOVERED: frozenset(
        {NetworkPathState.VALIDATED, NetworkPathState.RETIRED}
    ),
    NetworkPathState.VALIDATED: frozenset(
        {NetworkPathState.BOUND, NetworkPathState.RETIRED}
    ),
    NetworkPathState.BOUND: frozenset(
        {NetworkPathState.ACTIVE, NetworkPathState.RETIRED}
    ),
    NetworkPathState.ACTIVE: frozenset({NetworkPathState.RETIRED}),
    NetworkPathState.RETIRED: frozenset(),
}


def transition_is_legal(from_state: str, to_state: str) -> bool:
    """True iff the lifecycle table allows ``from_state -> to_state``.

    Unknown states fail closed (``False``) -- an ``UNKNOWN`` or
    out-of-vocabulary state can never transition to ``ACTIVE``.
    """
    if from_state not in LIFECYCLE_TRANSITIONS:
        return False
    return to_state in LIFECYCLE_TRANSITIONS[from_state]


class NetworkPathAction:
    """The frozen journaled action vocabulary.

    ``PROBE`` is deliberately a state-preserving journaled action
    (``BOUND -> BOUND``): probing records traffic-proof evidence and
    is a REQUIRED precondition of ``ACTIVATE`` (probe/verify before
    activation), but it is not itself a lifecycle transition.
    """

    DISCOVER = "discover"
    VALIDATE = "validate"
    BIND = "bind"
    PROBE = "probe"
    ACTIVATE = "activate"
    RETIRE = "retire"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.DISCOVER,
            cls.VALIDATE,
            cls.BIND,
            cls.PROBE,
            cls.ACTIVATE,
            cls.RETIRE,
        )


#: Which lifecycle state each action requires BEFORE it may run (the
#: fail-closed precondition gate; the manager enforces this in
#: addition to the transition table so duplicate, stale, and
#: out-of-order attempts never silently succeed).
ACTION_REQUIRED_STATE: Dict[str, str] = {
    NetworkPathAction.VALIDATE: NetworkPathState.DISCOVERED,
    NetworkPathAction.BIND: NetworkPathState.VALIDATED,
    NetworkPathAction.PROBE: NetworkPathState.BOUND,
    NetworkPathAction.ACTIVATE: NetworkPathState.BOUND,
    # RETIRE runs from any non-terminal state.
    NetworkPathAction.RETIRE: "",
}
