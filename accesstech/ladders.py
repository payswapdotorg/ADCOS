"""ADCOS access-technology degradation ladders (M020 — Access
Technology Capability Envelope, R9-CORE-001, DEC-0120).

The declared degradation ladders per technology class of the R9
charter M020 scope: each ladder is a declared ordered sequence of
**degradation modes** — named, technology-class-local rungs (the
extension surface: ``nominal``, ``capacity-75``, ``constrained`` …
the names the future M021 wireline capacity steps and the M022
propagation-aware margin steps will declare) — **mapped onto the
accepted realization-state vocabulary**.

BY-REFERENCE consumption (the charter's hard rule — imported, NEVER
redefined, never duplicated):

* the realization-state vocabulary is the M008-owned kernel
  ``REALIZING / DEGRADED / FAILED / SUPERSEDED``, imported from the
  accepted ``resilience`` surface (:mod:`resilience.model` — the
  R8-accepted domain that itself consumes the kernel from
  ``replan/``; the identity is verified at import time below);
* the terminal-state set and the legal transition edges are imported
  from the kernel's owning module ``replan``
  (:data:`replan.REALIZATION_TERMINAL_STATES`,
  :data:`replan.REALIZATION_TRANSITIONS`).

The ladders EXTEND the kernel without redefining it: a mode is a
named rung whose ``realization_state`` member MUST be one of the four
imported states (any drift is a typed VOCABULARY rejection — never a
coercion).  The mode-level walk the ladder models (multiple DEGRADED
capacity steps in sequence) is the mode-level extension; at the STATE
level every adjacent pair of rungs is either the identity (a deeper
capacity step on the same explicit DEGRADED state) or an edge that
exists in the imported kernel transition map — a ladder never uses a
kernel-illegal edge, and never invents a fifth state.

Ladder semantics (deterministic, one-way):

* the first rung maps to ``REALIZING`` (a ladder starts from a
  satisfying realization — frozen §9);
* every middle rung maps to ``DEGRADED`` (the explicit degraded
  realization state; recovery edges never appear inside a ladder —
  recovery is the kernel's ``DEGRADED -> REALIZING`` edge, driven by
  the accepted replan/failover machinery, never a ladder step);
* the last rung maps to a terminal kernel state (``FAILED`` or
  ``SUPERSEDED``): every declared ladder carries its explicit
  terminal rung — a realization that cannot satisfy the hard
  constraints enters the EXPLICIT failed state (frozen §9; never a
  silent open-ended degradation).

Stepping is deterministic and fail-closed:
:func:`ladder_step` descends exactly one rung from a declared mode
name (unknown mode names, terminal rungs and mis-shaped ladders are
typed rejections); :func:`mode_realization_state` resolves a mode to
its imported kernel state.

Determinism (LOCK-119): content-derived ladder identities over
canonical JSON (LOCK-106 discipline — derived from the canonical
bytes, never wall clock, never randomness); canonical-JSON
round-trips with tamper-evident re-verification at reconstruction;
no wall clock, no randomness, no network, no secrets.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes

# BY REFERENCE: the accepted resilience/ realization-state vocabulary —
# the M008-owned kernel consumed through the accepted R8 surface (the
# exact object resilience.model itself imported from replan).
from resilience.model import REALIZATION_STATES as _RESILIENCE_REALIZATION_STATES

# BY REFERENCE: the kernel's owning structures (terminal set + legal
# transition edges), imported from replan exactly as the accepted
# resilience domain does.
from replan import (
    REALIZATION_STATES,
    REALIZATION_TERMINAL_STATES,
    REALIZATION_TRANSITIONS,
)

from .errors import AccessTechError, AccessTechReason

__all__ = [
    "DegradationMode",
    "DegradationLadder",
    "derive_ladder_id",
    "ladder_step",
    "ladder_from_mapping",
    "mode_realization_state",
    "REALIZATION_STATES",
    "REALIZATION_TERMINAL_STATES",
]


def _check_consumed_vocabularies() -> None:
    """Fail loud on drift (never silently mis-project): the accepted
    resilience surface's realization-state vocabulary must BE the
    M008-owned kernel (the same imported object), and the kernel must
    be exactly the frozen four-state set this domain projects onto."""
    if REALIZATION_STATES is not _RESILIENCE_REALIZATION_STATES:
        raise AccessTechError(
            AccessTechReason.VOCABULARY,
            "the resilience/ realization-state vocabulary and the replan "
            "kernel object diverged (the ladder vocabulary is consumed BY "
            "REFERENCE — a fork is a drift, fail loud)",
        )
    if REALIZATION_STATES != ("REALIZING", "DEGRADED", "FAILED", "SUPERSEDED"):
        raise AccessTechError(
            AccessTechReason.VOCABULARY,
            "the consumed M008 realization-state kernel has drifted from "
            "the frozen four-state set (REALIZING/DEGRADED/FAILED/"
            "SUPERSEDED) this domain maps its ladder modes onto",
        )
    if REALIZATION_TERMINAL_STATES != ("FAILED", "SUPERSEDED"):
        raise AccessTechError(
            AccessTechReason.VOCABULARY,
            "the consumed realization terminal-state set has drifted",
        )


_check_consumed_vocabularies()


#: Identity namespace (WORK-003 canonical-JSON SHA-256 convention).
_LADDER_NAMESPACE = "adcos.accesstech.ladder"

#: Maximum number of rungs in one declared ladder (fail-closed bound).
MAX_LADDER_MODES = 32

#: Maximum mode-name length.
_MAX_MODE_NAME_LEN = 64

_MODE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


# ----------------------------------------------------------------------
# The degradation mode
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class DegradationMode:
    """One named rung of a degradation ladder, mapped onto the accepted
    realization-state vocabulary.

    ``name`` is the technology-class-local mode name (lowercase
    hyphen-token grammar; unique within its ladder).  ``realization_
    state`` MUST be a member of the imported M008-owned kernel
    (:data:`REALIZATION_STATES`) — a mode naming any other state is a
    typed VOCABULARY rejection (undeclared mode state — never a
    coercion, never a fifth state).
    """

    name: str
    realization_state: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "degradation mode name must be a non-empty string",
            )
        if len(self.name) > _MAX_MODE_NAME_LEN:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "degradation mode name exceeds %d characters" % _MAX_MODE_NAME_LEN,
            )
        if _MODE_NAME_PATTERN.fullmatch(self.name) is None:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "degradation mode name %r must match the lowercase "
                "hyphen-token grammar ^[a-z][a-z0-9-]*$" % self.name,
            )
        if not isinstance(self.realization_state, str):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "degradation mode %r carries a non-string realization_state"
                % self.name,
            )
        if self.realization_state not in REALIZATION_STATES:
            raise AccessTechError(
                AccessTechReason.VOCABULARY,
                "degradation mode %r maps onto %r — outside the accepted "
                "realization-state vocabulary %s (the kernel is consumed "
                "BY REFERENCE and never extended with new states)"
                % (self.name, self.realization_state, ", ".join(REALIZATION_STATES)),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "realization_state": self.realization_state,
        }


# ----------------------------------------------------------------------
# The degradation ladder
# ----------------------------------------------------------------------


def derive_ladder_id(technology_class: str, modes: Sequence[DegradationMode]) -> str:
    """The content-derived ladder identity (LOCK-106 discipline: sha256
    over the canonical JSON of the declared mode sequence)."""
    document = {
        "kind": "adcos.accesstech.ladder",
        "technology_class": technology_class,
        "modes": [mode.to_dict() for mode in modes],
    }
    payload = dict(document)
    payload["namespace"] = _LADDER_NAMESPACE
    return "sha256:" + hashlib.sha256(
        _canonical_bytes(payload, "the degradation ladder")
    ).hexdigest()


@dataclass(frozen=True)
class DegradationLadder:
    """The declared degradation ladder of ONE technology class: an
    ordered sequence of :class:`DegradationMode` rungs mapped onto the
    accepted realization-state vocabulary (consumed BY REFERENCE —
    extended with named modes, never with new states).

    The declared walk discipline (all typed rejections, fail closed):

    * at least one rung, at most :data:`MAX_LADDER_MODES`; rung names
      unique within the ladder (duplicates are contradictory);
    * the first rung maps to ``REALIZING``;
    * every middle rung maps to ``DEGRADED`` (explicit degradation
      steps; a recovery edge inside a one-way ladder is rejected);
    * the last rung maps to a terminal kernel state (``FAILED`` or
      ``SUPERSEDED``) — every declared ladder carries its explicit
      terminal rung;
    * every adjacent state pair is the identity (a deeper capacity
      step on the same explicit state) or an edge present in the
      imported kernel transition map (a kernel-illegal edge is
      rejected — the ladder never invents transitions);
    * rungs after a terminal rung are rejected (terminal states have
      no successors in the kernel).
    """

    technology_class: str
    modes: Tuple[DegradationMode, ...]
    ladder_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.technology_class, str) or not self.technology_class:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "ladder technology_class must be a non-empty string",
            )
        if isinstance(self.modes, (str, bytes)) or not isinstance(
            self.modes, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "ladder modes must be a sequence of DegradationMode records",
            )
        normalized: List[DegradationMode] = []
        for index, item in enumerate(self.modes):
            if not isinstance(item, DegradationMode):
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "ladder mode %d must be a DegradationMode record (got %s)"
                    % (index, type(item).__name__),
                )
            normalized.append(item)
        modes = tuple(normalized)
        if not modes:
            raise AccessTechError(
                AccessTechReason.LADDER_ILLEGAL,
                "a declared degradation ladder carries no modes (an empty "
                "ladder declares no degradation semantics)",
            )
        if len(modes) > MAX_LADDER_MODES:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "at most %d ladder modes are declarable (found %d)"
                % (MAX_LADDER_MODES, len(modes)),
            )
        names: List[str] = [mode.name for mode in modes]
        if len(set(names)) != len(names):
            duplicates = sorted(
                {name for name in names if names.count(name) > 1}
            )
            raise AccessTechError(
                AccessTechReason.LADDER_ILLEGAL,
                "duplicate ladder mode names are contradictory: %s"
                % ", ".join(duplicates),
            )
        states = [mode.realization_state for mode in modes]
        if states[0] != "REALIZING":
            raise AccessTechError(
                AccessTechReason.LADDER_ILLEGAL,
                "the first ladder rung maps onto %r — a degradation ladder "
                "starts from a satisfying realization (REALIZING)" % states[0],
            )
        terminal_seen = False
        for position, state in enumerate(states):
            if terminal_seen:
                raise AccessTechError(
                    AccessTechReason.LADDER_ILLEGAL,
                    "ladder rung %d (%r) follows the terminal rung %r — "
                    "terminal realization states have no successors in the "
                    "consumed kernel"
                    % (position, states[position], states[position - 1]),
                )
            if state in REALIZATION_TERMINAL_STATES:
                terminal_seen = True
        if not terminal_seen:
            raise AccessTechError(
                AccessTechReason.LADDER_ILLEGAL,
                "the ladder's last rung maps onto %r — every declared "
                "ladder carries its explicit terminal rung (FAILED or "
                "SUPERSEDED; frozen §9: a realization that cannot satisfy "
                "the hard constraints enters an EXPLICIT terminal state)"
                % states[-1],
            )
        for position in range(len(modes) - 1):
            current, following = states[position], states[position + 1]
            if current == following:
                continue  # a deeper capacity step on the same explicit state
            if following not in REALIZATION_TRANSITIONS.get(current, ()):
                raise AccessTechError(
                    AccessTechReason.LADDER_ILLEGAL,
                    "ladder edge %s -> %s is not legal in the consumed "
                    "realization transition map (the ladder never invents "
                    "kernel transitions)" % (current, following),
                )
            if current == "DEGRADED" and following == "REALIZING":
                raise AccessTechError(
                    # named closed guard for the recovery edge (it IS a
                    # legal kernel edge — the ladder discipline excludes it)
                    AccessTechReason.LADDER_ILLEGAL,
                    "a recovery edge (DEGRADED -> REALIZING) never appears "
                    "inside a one-way degradation ladder (recovery is the "
                    "accepted machinery's edge, never a ladder step)",
                )
        for position in range(1, len(modes) - 1):
            if states[position] not in ("DEGRADED",):
                raise AccessTechError(
                    AccessTechReason.LADDER_ILLEGAL,
                    "middle ladder rung %d maps onto %r — middle rungs are "
                    "explicit degradation steps (DEGRADED); the recovery "
                    "edge never appears inside a ladder" % (position, states[position]),
                )
        object.__setattr__(self, "modes", modes)
        derived = derive_ladder_id(self.technology_class, modes)
        if not isinstance(self.ladder_id, str) or not self.ladder_id:
            object.__setattr__(self, "ladder_id", derived)
        elif self.ladder_id != derived:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "ladder_id does not match the content-derived identity "
                "(tamper evidence): declared %s, derived %s"
                % (self.ladder_id, derived),
            )

    def content_dict(self) -> Dict[str, Any]:
        return {
            "technology_class": self.technology_class,
            "modes": [mode.to_dict() for mode in self.modes],
            "ladder_id": self.ladder_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content_dict()

    def to_canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.content_dict(), "the degradation ladder")

    def mode_names(self) -> Tuple[str, ...]:
        """The declared rung names in ladder order (deterministic)."""
        return tuple(mode.name for mode in self.modes)

    def mode_position(self, mode_name: str) -> int:
        """The declared position of one rung (fail-closed on an
        undeclared mode name — the typed 'ladders referencing
        undeclared modes' rejection)."""
        if not isinstance(mode_name, str):
            raise AccessTechError(
                AccessTechReason.LADDER_ILLEGAL,
                "mode name must be a string",
            )
        for position, mode in enumerate(self.modes):
            if mode.name == mode_name:
                return position
        raise AccessTechError(
            AccessTechReason.LADDER_ILLEGAL,
            "mode %r is not declared in this ladder (declared: %s)"
            % (mode_name, ", ".join(self.mode_names())),
        )

    def terminal_mode(self) -> DegradationMode:
        """The explicit terminal rung (the last declared mode)."""
        return self.modes[-1]


def ladder_step(
    ladder: DegradationLadder, from_mode_name: str
) -> DegradationMode:
    """Descend EXACTLY one rung from a declared mode (deterministic
    stepping — the same declared ladder and mode always step to the
    same next rung).

    Fail-closed typed rejections: an undeclared mode name; stepping
    from a terminal rung (terminal realization states never
    transition — the consumed kernel's discipline).
    """
    if not isinstance(ladder, DegradationLadder):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "ladder_step requires a DegradationLadder (got %s)"
            % type(ladder).__name__,
        )
    position = ladder.mode_position(from_mode_name)
    mode = ladder.modes[position]
    if mode.realization_state in REALIZATION_TERMINAL_STATES:
        raise AccessTechError(
            AccessTechReason.LADDER_ILLEGAL,
            "mode %r is the terminal rung (%s — terminal realization "
            "states never transition; the consumed kernel's discipline)"
            % (from_mode_name, mode.realization_state),
        )
    return ladder.modes[position + 1]


def mode_realization_state(
    ladder: DegradationLadder, mode_name: str
) -> str:
    """Resolve one declared mode to its imported kernel realization
    state (fail-closed on an undeclared mode name)."""
    if not isinstance(ladder, DegradationLadder):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "mode_realization_state requires a DegradationLadder (got %s)"
            % type(ladder).__name__,
        )
    position = ladder.mode_position(mode_name)
    return ladder.modes[position].realization_state


def ladder_from_mapping(value: object) -> DegradationLadder:
    """Reconstruct a :class:`DegradationLadder` from its canonical
    mapping (fail-closed on grammar drift, on every ladder-discipline
    violation, and on identity tampering — the content-derived ladder
    id is recomputed and compared at load)."""
    if not isinstance(value, Mapping):
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "the degradation ladder must be a mapping",
        )
    data = dict(value)
    ladder_id = data.get("ladder_id")
    if not isinstance(ladder_id, str) or not ladder_id:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "the degradation ladder lacks its content-derived ladder_id",
        )
    technology_class = data.get("technology_class")
    if not isinstance(technology_class, str) or not technology_class:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "the degradation ladder lacks its technology_class",
        )
    modes_raw = data.get("modes")
    if isinstance(modes_raw, (str, bytes)) or not isinstance(
        modes_raw, (tuple, list)
    ):
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "ladder modes must be a sequence of mode mappings",
        )
    modes: List[DegradationMode] = []
    for item in modes_raw:
        if not isinstance(item, Mapping):
            raise AccessTechError(
                AccessTechReason.SERIALIZATION_INVALID,
                "each ladder mode must be a mapping",
            )
        mode_data = dict(item)
        for member in ("name", "realization_state"):
            if member not in mode_data:
                raise AccessTechError(
                    AccessTechReason.SERIALIZATION_INVALID,
                    "a ladder mode lacks the %r member" % member,
                )
        modes.append(
            DegradationMode(
                name=mode_data["name"],
                realization_state=mode_data["realization_state"],
            )
        )
    return DegradationLadder(
        technology_class=technology_class,
        modes=tuple(modes),
        ladder_id=ladder_id,
    )
