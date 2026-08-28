"""WORK-035 mobile lifecycle: the phase machine and participation gate.

Two pure, frozen decision surfaces:

- **the phase transition table** -- which OS-reported application
  phase changes are legal (foreground/background/stopped).  The
  mobile layer never drives the phase itself; it validates what the
  OS reports and adapts;
- **the participation gate** -- what the mobile node may do RIGHT
  NOW, derived only from (phase, platform snapshot, active user
  grants).  Background limitations, offline state, metering, and
  user consent are all EXPLICIT inputs to this pure function; none
  of them mutates -- or is decided by -- any agent authority.

The gate is the entire "OS limits within which participation
operates" model.  It is deliberately total: every input combination
maps to exactly one decision with a frozen defer reason.
"""

from __future__ import annotations

from typing import Mapping, Tuple

from agent.clock import parse_utc

from .errors import MobileError, MobileReasonCode
from .model import (
    DeferReason,
    GrantScope,
    MobilePhase,
    NetworkKind,
    ParticipationDecision,
    PlatformSnapshot,
    UserGrant,
)

#: The frozen legal phase-transition table.  ``stopped`` is terminal
#: for a process: the ONLY continuation is a relaunch through
#: recovery (a NEW process starts in the foreground).  Same-phase
#: observations are no-ops, not transitions.
PHASE_TRANSITIONS: Mapping[str, Tuple[str, ...]] = {
    MobilePhase.FOREGROUND: (
        MobilePhase.BACKGROUND,
        MobilePhase.STOPPED,
    ),
    MobilePhase.BACKGROUND: (
        MobilePhase.FOREGROUND,
        MobilePhase.STOPPED,
    ),
    MobilePhase.STOPPED: (),
}


def transition_is_legal(previous: str, new: str) -> bool:
    """True iff ``previous -> new`` is a legal OS phase edge."""
    return new in PHASE_TRANSITIONS.get(previous, ())


def grant_active(
    grants: Mapping[str, UserGrant], scope: str, *, now: str
) -> bool:
    """Is the user's ``scope`` grant active at the injected instant?

    A grant is active when it is present, unexpired, and its expiry
    boundary is strictly in the future (``expires_at <= now`` is
    expired -- the same boundary discipline as the WORK-006 verifier).
    """
    if scope not in GrantScope.values():
        raise MobileError(
            MobileReasonCode.GRANT_INVALID,
            "grant scope %r not in the frozen vocabulary" % (scope,),
        )
    grant = grants.get(scope)
    if grant is None or grant.scope != scope:
        return False
    if grant.expires_at == "":
        return True
    return parse_utc(grant.expires_at) > parse_utc(now)


def participation_gate(
    phase: str,
    platform: PlatformSnapshot,
    grants: Mapping[str, UserGrant],
    *,
    now: str,
) -> ParticipationDecision:
    """The pure participation gate.

    Order of authority (most fundamental first):

    1. connectivity -- no usable access means nothing is sent
       (offline defer);
    2. user consent for metered access -- a metered access is not
       used without the user's ``metered-data`` grant (user-controlled
       resource sharing);
    3. the OS phase -- foreground participates; background
       participates only with the user's ``background-data`` grant
       AND while the OS does not currently restrict background work;
    4. discovery -- additionally requires the explicit
       ``local-discovery`` consent in every phase.
    """
    if phase not in MobilePhase.values():
        raise MobileError(
            MobileReasonCode.INVALID_INPUT,
            "phase must be one of %s (got %r)" % (MobilePhase.values(), phase),
        )
    if not isinstance(platform, PlatformSnapshot):
        raise MobileError(
            MobileReasonCode.INVALID_INPUT,
            "gate requires a genuine PlatformSnapshot",
        )
    online = platform.network_kind != NetworkKind.NONE
    # Metering is the OS's report about the CURRENT access (a Wi-Fi
    # hotspot can be metered exactly like cellular); the gate honors
    # the report for every access kind.
    metered = platform.metered
    if not online:
        reason = DeferReason.OFFLINE
    elif metered and not grant_active(grants, GrantScope.METERED_DATA, now=now):
        reason = DeferReason.METERED_NOT_AUTHORIZED
    elif phase == MobilePhase.FOREGROUND:
        reason = ""
    elif phase == MobilePhase.BACKGROUND:
        if not grant_active(grants, GrantScope.BACKGROUND_DATA, now=now):
            reason = DeferReason.BACKGROUND_NOT_AUTHORIZED
        elif platform.background_restricted:
            reason = DeferReason.BACKGROUND_RESTRICTED
        else:
            reason = ""
    else:  # STOPPED: a stopped process participates in nothing
        reason = DeferReason.STOPPED
    sends_allowed = reason == ""
    discovery_allowed = sends_allowed and grant_active(
        grants, GrantScope.LOCAL_DISCOVERY, now=now
    )
    return ParticipationDecision(
        phase=phase,
        network_kind=platform.network_kind,
        online=online,
        metered=metered,
        background_restricted=platform.background_restricted,
        sends_allowed=sends_allowed,
        discovery_allowed=discovery_allowed,
        defer_reason=reason,
    )
