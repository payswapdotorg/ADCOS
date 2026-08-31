"""WORK-042 integration with the accepted authorities (public
reads only).

The composition helpers that connect the platform-integration
layer to the existing accepted authorities through their PUBLIC
surfaces only:

- :func:`session_bindings_from_manager` reads the WORK-041
  ``NetworkPathManager``'s public binding facts (paths + their
  ``session_id``) and projects them into checkpoint DATA
  references, so process death can be reported honestly;
- :func:`interface_names_from_state` and the reconciled seams in
  ``platform.lifecycle`` feed event-reconstructed state BACK into
  the accepted authorities unchanged.

Nothing here mutates any authority: the NetworkPath authority
(WORK-041), the session authority (WORK-012), the mobility
authority (WORK-014), the AgentRuntime (WORK-033), and the
MobileAgent (WORK-035) remain the single owners of their state.
"""

from __future__ import annotations

from typing import Tuple

from networkpath import NetworkPath, NetworkPathManager, NetworkPathState

from .errors import PlatformError, PlatformReasonCode
from .model import SessionBindingRef


def session_bindings_from_manager(
    manager: NetworkPathManager,
) -> Tuple[SessionBindingRef, ...]:
    """Project the manager's PUBLIC binding facts into checkpoint
    references (pure reads; sorted deterministically).

    A binding reference exists for every path whose ``session_id``
    is set (bound or active): the reference records (session_id,
    network_path_id, interface_name) as DATA.  These references let
    a future process death be reported honestly; they grant no
    continuity and never recreate anything.
    """
    if not isinstance(manager, NetworkPathManager):
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "manager must be a NetworkPathManager (the accepted "
            "WORK-041 public surface)",
        )
    bindings = []
    for path_id in manager.paths():
        path = manager.path(path_id)
        if not isinstance(path, NetworkPath):
            continue
        if not path.session_id:
            continue
        bindings.append(
            SessionBindingRef(
                session_id=path.session_id,
                network_path_id=path.network_path_id,
                interface_name=path.interface_name,
            )
        )
    return tuple(
        sorted(bindings, key=lambda binding: binding.binding_key())
    )


def path_supports_state(path: NetworkPath) -> bool:
    """Is this path's lifecycle state one a checkpoint binding
    should record (BOUND or ACTIVE)?"""
    if not isinstance(path, NetworkPath):
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "path must be a NetworkPath",
        )
    return path.state in (NetworkPathState.BOUND, NetworkPathState.ACTIVE)


__all__ = [
    "path_supports_state",
    "session_bindings_from_manager",
]
