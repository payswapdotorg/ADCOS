"""ADCOS simulator package -- WORK-031: network and behavior simulator.

A deterministic simulator for ADCOS nodes, links, failures, resources,
mobility, and policies: a controlled, reproducible environment AROUND
the existing accepted authorities, never a replacement protocol
implementation.

Public API:

- :class:`Simulator`, :func:`verify_replay` -- the deterministic
  scenario runner over real composed authorities and the replay
  verification entry point
- :class:`ScenarioSpec`, :class:`ScheduledEvent`,
  :class:`SimulatedNodeSpec`, :class:`SimulatedLinkSpec`,
  :class:`ScenarioPolicyRule` -- the immutable, reproducible scenario
  configuration (explicit seed + injected time base + ordered events)
- :class:`EventKind`, :class:`EventVerdict`, :class:`MutationOutcome`,
  :class:`SimulatorReasonCode`, :class:`SimulatorError` -- the frozen
  vocabularies
- :class:`ObservationRecord`, :class:`AuthorityMutation`,
  :class:`FlowObservation`, :class:`ScenarioResult` -- the observed
  authoritative outputs and evidence/trace state
- :class:`ScenarioClock` -- the injected deterministic time base (no
  wall clock anywhere in the family)
- :class:`DeterministicStream` -- the documented counter-based sha256
  PRNG bound to the explicit scenario seed
- :class:`SimulatedEnvironment` -- simulator-owned environment state
  projecting scenario data into real authority INPUT records
- :class:`AuthorityTestSeam`, :func:`authority_digest`,
  :func:`seam_verdict` -- the explicit, restored test seam over one
  caller-provided authority component
- :func:`spec_to_mapping`, :func:`spec_from_mapping`,
  :func:`result_from_mapping`, :func:`trace_digest` -- canonical
  serialization (cross-process determinism)

Module authority: ``/simulator`` owns deterministic scenario
orchestration and simulated environment state.  It does NOT own
topology truth (WORK-007), resource truth (WORK-008), policy decisions
(WORK-010), path selection (WORK-011), session lifecycle (WORK-012),
multipath plans (WORK-013), mobility transactions (WORK-014),
telemetry records (WORK-026), or energy/resilience mechanics
(WORK-027) -- it composes the real accepted authorities through their
public, least-authority contracts, records every mutation it performs
through an owner contract, and never becomes a second protocol
authority.  Simulator state stays separate from authoritative protocol
state by construction; the simulator is never external
interoperability evidence.
"""

from __future__ import annotations

from .model import (
    AuthorityMutation,
    EventKind,
    EventVerdict,
    FlowObservation,
    MutationOutcome,
    ObservationRecord,
    ScenarioPolicyRule,
    ScenarioResult,
    ScenarioSpec,
    ScheduledEvent,
    SimulatedLinkSpec,
    SimulatedNodeSpec,
    SimulatorError,
    SimulatorReasonCode,
)
from .random import DeterministicStream
from .runner import Simulator, trace_digest, verify_replay
from .seam import AuthorityTestSeam, authority_digest, seam_verdict
from .serialization import result_from_mapping, spec_from_mapping, spec_to_mapping
from .time import ScenarioClock

__all__ = [
    "AuthorityMutation",
    "AuthorityTestSeam",
    "DeterministicStream",
    "EventKind",
    "EventVerdict",
    "FlowObservation",
    "MutationOutcome",
    "ObservationRecord",
    "ScenarioClock",
    "ScenarioPolicyRule",
    "ScenarioResult",
    "ScenarioSpec",
    "ScheduledEvent",
    "SimulatedEnvironment",
    "SimulatedLinkSpec",
    "SimulatedNodeSpec",
    "Simulator",
    "SimulatorError",
    "SimulatorReasonCode",
    "authority_digest",
    "result_from_mapping",
    "seam_verdict",
    "spec_from_mapping",
    "spec_to_mapping",
    "trace_digest",
    "verify_replay",
]

# Re-exported lazily to avoid an import cycle (environment imports
# energy/routing/resources/topology model types only).
def __getattr__(name: str) -> object:  # noqa: D105
    if name == "SimulatedEnvironment":
        from .environment import SimulatedEnvironment

        return SimulatedEnvironment
    raise AttributeError(name)
