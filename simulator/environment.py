"""The simulated environment (WORK-031): simulator-owned world state.

The :class:`SimulatedEnvironment` holds the SIMULATED world -- node
power simulators (real WORK-027 :class:`PowerSimulator` instances over
scenario data), link status, partition cuts -- and PROJECTS scenario
data into real authority INPUT records:

- :meth:`link_claims` -- real WORK-007 :class:`TopologyClaim` records
  (one per link, with reporter/subject/source provenance and a
  per-link monotonic sequence);
- :meth:`link_metrics` -- real WORK-011 :class:`LinkMetrics` facts
  (technology-neutral, degraded links deterministically adjusted);
- :meth:`energy_states` -- real WORK-008 :class:`EnergyState`
  measurements from the real WORK-027 power simulators.

The environment holds NO authority references and NEVER mutates any
authority: it produces data that the runner ingests through the
authorities' own public APIs.  Simulator state stays separate from
authoritative protocol state by construction.
"""

from __future__ import annotations

from typing import Dict, Set, Tuple

from energy.model import (
    MAX_SIMULATION_SECONDS,
    PowerProfile,
    PowerStep,
    SurvivalProfile,
    derive_power_profile_id,
    derive_profile_id,
)
from energy.simulation import PowerSimulator
from resources.model import EnergyState
from routing.model import LinkMetrics
from topology.model import (
    ClaimType,
    LinkState,
    SourceClass,
    TopologyClaim,
    make_link_subject,
)

from .model import (
    ScenarioSpec,
    SimulatedLinkSpec,
    SimulatorError,
    SimulatorReasonCode,
)
from .random import DeterministicStream
from .time import ScenarioClock

# Documented constants completing the WORK-027 survival profile from
# the scenario's SimulatedNodeSpec (fixed so profile ids stay a pure
# function of the spec -- see SimulatedNodeSpec docstring).
_UPSTREAM_DEGRADED_AFTER = 2
_UPSTREAM_DOWN_AFTER = 4
_UPSTREAM_RECOVER_AFTER = 3
_UPSTREAM_LOSS_THRESHOLD_BP = 2000
_MAX_GENERATION_MILLIWATTS = 500

# Power schedules run to the energy authority's own simulation horizon.
_SCHEDULE_END_SECOND = MAX_SIMULATION_SECONDS

# Documented deterministic degradation transform (stochastic variation
# comes only from the explicit scenario seed via DeterministicStream).
_LINK_STATES = (LinkState.UP, LinkState.DOWN, LinkState.DEGRADED)

_DEGRADE_LATENCY_MULTIPLIER_BASE = 2
_DEGRADE_LOSS_BASE_BP = 1000
_DEGRADE_LOSS_STEP_BP = 500


class SimulatedEnvironment:
    """Simulator-owned environment state for one scenario run."""

    def __init__(
        self,
        spec: ScenarioSpec,
        clock: ScenarioClock,
        stream: DeterministicStream,
    ) -> None:
        self._clock = clock
        self._stream = stream
        self._nodes: Dict[str, PowerSimulator] = {}
        self._survival: Dict[str, SurvivalProfile] = {}
        self._online: Dict[str, bool] = {}
        self._links: Dict[str, SimulatedLinkSpec] = {}
        self._link_status: Dict[str, str] = {}
        self._link_degraded: Dict[str, bool] = {}
        self._link_sequence: Dict[str, int] = {}
        self._partition_cuts: Set[str] = set()
        for node in spec.nodes:
            load_steps = (
                PowerStep(0, _SCHEDULE_END_SECOND, node.load_milliwatts),
            )
            generation_steps = (
                PowerStep(0, _SCHEDULE_END_SECOND, node.generation_milliwatts),
            )
            profile = PowerProfile(
                profile_id=derive_power_profile_id(
                    node.node_id,
                    node.power_source,
                    node.capacity_millijoules,
                    node.initial_level_millijoules,
                    load_steps,
                    generation_steps,
                ),
                node_id=node.node_id,
                power_source=node.power_source,
                capacity_millijoules=node.capacity_millijoules,
                initial_level_millijoules=node.initial_level_millijoules,
                load_steps=load_steps,
                generation_steps=generation_steps,
            )
            self._nodes[node.node_id] = PowerSimulator(profile)
            self._survival[node.node_id] = SurvivalProfile(
                profile_id=derive_profile_id(
                    node.node_id,
                    node.conserve_threshold_bp,
                    node.critical_threshold_bp,
                    node.survival_threshold_bp,
                    node.survival_reserve_bp,
                    (),
                    (),
                    (),
                    node.offline_grace_seconds,
                    _UPSTREAM_DEGRADED_AFTER,
                    _UPSTREAM_DOWN_AFTER,
                    _UPSTREAM_RECOVER_AFTER,
                    _UPSTREAM_LOSS_THRESHOLD_BP,
                    _MAX_GENERATION_MILLIWATTS,
                ),
                node_id=node.node_id,
                conserve_threshold_bp=node.conserve_threshold_bp,
                critical_threshold_bp=node.critical_threshold_bp,
                survival_threshold_bp=node.survival_threshold_bp,
                survival_reserve_bp=node.survival_reserve_bp,
                essential_services=(),
                deferrable_services=(),
                droppable_services=(),
                offline_grace_seconds=node.offline_grace_seconds,
                upstream_degraded_after=_UPSTREAM_DEGRADED_AFTER,
                upstream_down_after=_UPSTREAM_DOWN_AFTER,
                upstream_recover_after=_UPSTREAM_RECOVER_AFTER,
                upstream_loss_threshold_bp=_UPSTREAM_LOSS_THRESHOLD_BP,
                max_generation_milliwatts=_MAX_GENERATION_MILLIWATTS,
            )
            self._online[node.node_id] = True
        for link in spec.links:
            subject = make_link_subject(link.node_a, link.node_b)
            self._links[subject] = link
            self._link_status[subject] = LinkState.UP
            self._link_degraded[subject] = False
            self._link_sequence[subject] = 1

    # ------------------------------------------------------------------
    # Node power / restart state
    # ------------------------------------------------------------------

    @property
    def node_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._nodes))

    def survival_profile(self, node_id: str) -> SurvivalProfile:
        self._require_node(node_id)
        return self._survival[node_id]

    def power_simulator(self, node_id: str) -> PowerSimulator:
        self._require_node(node_id)
        return self._nodes[node_id]

    def advance_power(self, seconds: int) -> None:
        """Advance every node's power simulation by ``seconds``."""
        for simulator in self._nodes.values():
            simulator.step(seconds)

    def is_online(self, node_id: str) -> bool:
        self._require_node(node_id)
        return self._online[node_id]

    def set_online(self, node_id: str, online: bool) -> None:
        self._require_node(node_id)
        self._online[node_id] = online

    def energy_states(self) -> Dict[str, EnergyState]:
        """REAL WORK-008 ``EnergyState`` measurements per node (DATA)."""
        return {
            node_id: simulator.energy_state()
            for node_id, simulator in sorted(self._nodes.items())
        }

    # ------------------------------------------------------------------
    # Link / partition state
    # ------------------------------------------------------------------

    @property
    def link_subjects(self) -> Tuple[str, ...]:
        return tuple(sorted(self._links))

    def link_subject(self, node_a: str, node_b: str) -> str:
        self._require_node(node_a)
        self._require_node(node_b)
        subject = make_link_subject(node_a, node_b)
        if subject not in self._links:
            raise SimulatorError(
                SimulatorReasonCode.UNKNOWN_LINK,
                "no simulated link between %r and %r" % (node_a, node_b),
            )
        return subject

    def link_status(self, subject: str) -> str:
        self._require_link(subject)
        if subject in self._partition_cuts:
            return LinkState.DOWN
        return self._link_status[subject]

    def set_link_status(self, subject: str, status: str) -> None:
        self._require_link(subject)
        if status not in _LINK_STATES:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "link status %r must be one of %s" % (status, _LINK_STATES),
            )
        self._link_status[subject] = status
        self._link_degraded[subject] = False

    def degrade_link(self, subject: str) -> None:
        """Mark a link degraded: a METRIC-quality dimension (LOCK-009),
        never a topology link-state change -- the emitted claim stays
        ``up`` and the metric facts carry the deterministic penalty."""
        self._require_link(subject)
        self._link_degraded[subject] = True

    def is_degraded(self, subject: str) -> bool:
        self._require_link(subject)
        return self._link_degraded[subject]

    def cut_links(self, subjects: Tuple[str, ...]) -> None:
        for subject in subjects:
            self._require_link(subject)
            self._partition_cuts.add(subject)

    def restore_links(self, subjects: Tuple[str, ...]) -> None:
        for subject in subjects:
            self._require_link(subject)
            self._partition_cuts.discard(subject)

    # ------------------------------------------------------------------
    # Projections into real authority INPUT records (DATA only)
    # ------------------------------------------------------------------

    def node_claims(self, now: str, freshness_until: str) -> Tuple[TopologyClaim, ...]:
        """One REACHABLE self-claim per scenario node (real WORK-007
        records: reporter == subject, SELF_ADVERTISEMENT -- the
        provenance-correct shape for authoritative reachability)."""
        claims = []
        for node_id in sorted(self._nodes):
            claims.append(
                TopologyClaim(
                    subject=node_id,
                    reporter=node_id,
                    claim_type=ClaimType.REACHABLE,
                    value="true",
                    source_class=SourceClass.SELF_ADVERTISEMENT,
                    issued_at=now,
                    freshness_until=freshness_until,
                    sequence=1,
                    provenance="simulator:environment",
                )
            )
        return tuple(claims)

    def link_claim(
        self, subject: str, now: str, freshness_until: str
    ) -> TopologyClaim:
        """The real WORK-007 :class:`TopologyClaim` for ONE link.

        The reporter is the link's first endpoint (a scenario node);
        the claim is a SELF_ADVERTISEMENT about the reporter's own
        link observation.  The per-link sequence advances
        monotonically and deterministically with each emission.
        """
        self._require_link(subject)
        link = self._links[subject]
        sequence = self._link_sequence[subject]
        self._link_sequence[subject] = sequence + 1
        return TopologyClaim(
            subject=subject,
            reporter=link.node_a,
            claim_type=ClaimType.LINK_STATE,
            value=self.link_status(subject),
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at=now,
            freshness_until=freshness_until,
            sequence=sequence,
            provenance="simulator:environment",
        )

    def all_link_claims(self, now: str, freshness_until: str) -> Tuple[TopologyClaim, ...]:
        """LINK_STATE claims for every simulated link (bootstrap form)."""
        return tuple(
            self.link_claim(subject, now, freshness_until)
            for subject in sorted(self._links)
        )

    def link_metrics(
        self, now: str, freshness_until: str
    ) -> Dict[str, LinkMetrics]:
        """Real WORK-011 :class:`LinkMetrics` facts per link.

        Degraded links carry a deterministic, seed-derived penalty
        (latency multiplier 2..4, extra loss 1000..2000 bp) -- the only
        stochastic metric variation in the simulator, drawn from the
        explicit scenario seed.
        """
        metrics: Dict[str, LinkMetrics] = {}
        for subject in sorted(self._links):
            link = self._links[subject]
            status = self.link_status(subject)
            latency = link.latency_ms
            loss = link.loss_basis_points
            if status == LinkState.UP and self.is_degraded(subject):
                latency = latency * (
                    _DEGRADE_LATENCY_MULTIPLIER_BASE + self._stream.uint(3)
                )
                loss = min(
                    10_000,
                    loss
                    + _DEGRADE_LOSS_BASE_BP
                    + self._stream.uint(3) * _DEGRADE_LOSS_STEP_BP,
                )
            elif status == LinkState.DOWN:
                loss = 10_000  # a down link carries total loss facts
            metrics[subject] = LinkMetrics(
                latency_ms=latency,
                loss_basis_points=loss,
                capacity_bps=link.capacity_bps,
                energy_cost_millijoules=link.energy_cost_millijoules,
                confidence_basis_points=link.confidence_basis_points,
                observed_at=now,
                freshness_until=freshness_until,
                provenance="simulator:environment",
            )
        return metrics

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise SimulatorError(
                SimulatorReasonCode.UNKNOWN_NODE,
                "node %r is not part of this scenario" % node_id,
            )

    def _require_link(self, subject: str) -> None:
        if subject not in self._links:
            raise SimulatorError(
                SimulatorReasonCode.UNKNOWN_LINK,
                "link %r is not part of this scenario" % subject,
            )
