"""WORK-034 resource-aware command scheduling.

The scheduler decides WHAT runs when a constrained board is under
pressure -- and it decides nothing else.  Session, routing, resource,
and policy semantics stay exactly where the accepted authorities put
them; a command that the scheduler admits executes through the
unchanged WORK-033 ``AgentRuntime.execute`` path, and a command the
scheduler defers or sheds is recorded with a typed reason (never
silently dropped).

The admission matrix is frozen DATA:

- **priority classes** -- every WORK-033 command kind is classified
  protected / essential / bulk.  Lifecycle and self-verification
  (boot, shutdown, self-test) are protected; authority-observation
  and negotiation commands are essential; bulk datagram relay is
  bulk.
- **level gates** -- nominal runs everything; pressured defers bulk;
  critical defers bulk AND essential.  Protected commands always run
  (a node must always be able to boot, verify itself, and shut down
  cleanly -- the survival discipline).
- **cpu budget gate** -- essential and bulk commands additionally
  require remaining epoch budget; protected commands run and are
  charged (usage may exceed the envelope, driving pressure to
  critical -- honest, never silent).
- **offline gate** -- datagram relay is deferred while the node's
  access posture is offline (bounded queue, explicit TTL); everything
  else keeps running: a Pi-class gateway must keep observing,
  negotiating, and verifying while disconnected.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .errors import EdgeError, EdgeReasonCode
from .model import (
    CommandPriority,
    ConnectivityPosture,
    PressureLevel,
    SchedulerDecision,
    SchedulingVerdict,
)

#: Frozen command-kind -> priority classification (the WORK-033
#: ``CommandKind`` VALUES as keys; the battery cross-checks
#: completeness).
PRIORITY_FOR_KIND: Dict[str, str] = {
    "boot": CommandPriority.PROTECTED,
    "expose-interfaces": CommandPriority.ESSENTIAL,
    "register-peer": CommandPriority.ESSENTIAL,
    "monitor": CommandPriority.ESSENTIAL,
    "send-datagram": CommandPriority.BULK,
    "receive-datagram": CommandPriority.BULK,
    "suspend-session": CommandPriority.ESSENTIAL,
    "terminate-session": CommandPriority.ESSENTIAL,
    "negotiate-peer": CommandPriority.ESSENTIAL,
    "self-test": CommandPriority.PROTECTED,
    "shutdown": CommandPriority.PROTECTED,
}

#: The frozen admission matrix: pressure level x priority -> verdict.
ADMISSION_BY_LEVEL: Dict[str, Dict[str, str]] = {
    PressureLevel.NOMINAL: {
        CommandPriority.PROTECTED: SchedulingVerdict.EXECUTED,
        CommandPriority.ESSENTIAL: SchedulingVerdict.EXECUTED,
        CommandPriority.BULK: SchedulingVerdict.EXECUTED,
    },
    PressureLevel.PRESSURED: {
        CommandPriority.PROTECTED: SchedulingVerdict.EXECUTED,
        CommandPriority.ESSENTIAL: SchedulingVerdict.EXECUTED,
        CommandPriority.BULK: SchedulingVerdict.DEFERRED,
    },
    PressureLevel.CRITICAL: {
        CommandPriority.PROTECTED: SchedulingVerdict.EXECUTED,
        CommandPriority.ESSENTIAL: SchedulingVerdict.DEFERRED,
        CommandPriority.BULK: SchedulingVerdict.DEFERRED,
    },
}

#: Command kinds deferred (not run) while the access posture is
#: offline: bulk datagram relay cannot proceed with no access path;
#: every other kind keeps operating (offline is not dead).
OFFLINE_DEFERRED_KINDS: Tuple[str, ...] = (
    "send-datagram",
    "receive-datagram",
)


def priority_for_kind(kind: str) -> str:
    """The frozen priority class of a command kind (unknown kinds are
    essential-by-default with a battery-checked completeness rule:
    new command kinds must be classified deliberately)."""
    priority = PRIORITY_FOR_KIND.get(kind)
    if priority is None:
        return CommandPriority.ESSENTIAL
    return priority


def decide_command(
    kind: str,
    *,
    pressure_level_now: str,
    posture: str,
    cpu_steps_remaining: int,
    cpu_charge: int,
) -> SchedulerDecision:
    """The pure, deterministic admission decision for one command.

    Inputs only -- no hidden state; the caller owns the ledger and
    the defer queue.  Order of gates (documented, discriminating):

    1. offline gate (posture == offline and kind is bulk relay);
    2. priority lookup;
    3. cpu epoch-budget gate (essential/bulk only);
    4. pressure-level admission matrix.
    """
    if pressure_level_now not in PressureLevel.values():
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "pressure level %r not in the frozen vocabulary"
            % (pressure_level_now,),
        )
    if posture not in ConnectivityPosture.values():
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "posture %r not in the frozen vocabulary" % (posture,),
        )
    if isinstance(cpu_steps_remaining, bool) \
            or not isinstance(cpu_steps_remaining, int) \
            or cpu_steps_remaining < 0:
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "cpu_steps_remaining must be a non-negative integer",
        )
    if isinstance(cpu_charge, bool) or not isinstance(cpu_charge, int) \
            or cpu_charge < 0:
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "cpu charge must be a non-negative integer",
        )
    if not kind:
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "command kind must be a non-empty string",
        )
    # 1. offline gate: bulk relay waits for an access path.
    if posture == ConnectivityPosture.OFFLINE \
            and kind in OFFLINE_DEFERRED_KINDS:
        return SchedulerDecision(
            verdict=SchedulingVerdict.DEFERRED,
            reason="offline",
            priority=priority_for_kind(kind),
        )
    # 2. priority class.
    priority = priority_for_kind(kind)
    # 3. cpu epoch-budget gate (protected bypasses; still charged).
    if priority != CommandPriority.PROTECTED and cpu_charge > 0:
        if cpu_steps_remaining < cpu_charge:
            return SchedulerDecision(
                verdict=SchedulingVerdict.DEFERRED,
                reason="cpu-budget-exhausted",
                priority=priority,
            )
    # 4. pressure-level admission matrix.
    verdict = ADMISSION_BY_LEVEL[pressure_level_now][priority]
    if verdict == SchedulingVerdict.DEFERRED:
        return SchedulerDecision(
            verdict=SchedulingVerdict.DEFERRED,
            reason="resource-pressure:%s" % pressure_level_now,
            priority=priority,
        )
    return SchedulerDecision(
        verdict=SchedulingVerdict.EXECUTED,
        reason="",
        priority=priority,
    )


__all__ = [
    "PRIORITY_FOR_KIND",
    "ADMISSION_BY_LEVEL",
    "OFFLINE_DEFERRED_KINDS",
    "priority_for_kind",
    "decide_command",
]
