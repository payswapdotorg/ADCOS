"""Rolling upgrades across a node population (WORK-029).

The deterministic orchestration layer that turns per-node staged
upgrades into a population-wide ROLLING upgrade with canary
discipline:

1. ``stage_canary`` -- one node (the lexicographically first, a
   deterministic choice) goes through submit/begin/advance and turns
   CANARY: the population is now MIXED-VERSION by design, and
   mixed-version coexistence is exactly what the frozen architecture
   demands (section 25 rule 13: no flag-day upgrade);
2. ``stage_remaining`` -- only after the canary's rollout gate PASSES
   over real telemetry do the remaining nodes stage (each with its
   own canary gate); any failure halts the rollout and rolls back
   EVERY node that had begun (fail closed -- later batches never
   advance on an unhealthy canary);
3. ``commit_population`` -- each node walks rollout gate -> final
   gate -> commit; any failure halts and rolls everything back;
4. ``rollback_population(target)`` -- the population-wide rollback,
   with downgrade protection: a target below any node's
   minimum-version floor is DOWNGRADE_BLOCKED, fail closed.

The coordinator is ORCHESTRATION DATA, not an authority: it owns no
state of its own beyond the mapping of node ids to their OWN
:class:`upgrade.manager.UpgradeManager` instances -- every verdict
(plan validity, gate pass/fail, stage, rollback) is the per-node
manager's verdict, produced by the frozen per-node rules.  It never
touches topology, session, routing, policy, or identity state.

Determinism: nodes are processed in sorted node-id order; instants
are injected; no wall clock, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

from .errors import UpgradeError, UpgradeReasonCode
from .manager import UpgradeManager
from .model import (
    HealthGateSpec,
    ProtocolProfile,
    SoftwareVersion,
    UpgradePlan,
    UpgradeStage,
    VersionInventory,
)
from .validation import validate_instant, validate_opaque_ref


@dataclass(frozen=True)
class RolloutTemplate:
    """The population-wide upgrade template: everything every node's
    plan shares.  Per-node plans are DERIVED (the plan's node_id and
    from_version come from each node's current state); the per-node
    :class:`UpgradePlan` construction and the manager's
    ``submit_plan`` validate the rest."""

    to_version: SoftwareVersion
    target_protocol_profile: ProtocolProfile
    target_schema_versions: Tuple[Tuple[str, str], ...]
    minimum_version_floor: Optional[SoftwareVersion]
    canary_gate: HealthGateSpec
    rollout_gate: HealthGateSpec
    final_gate: HealthGateSpec

    def plan_for(self, node_id: str, from_version: SoftwareVersion) -> UpgradePlan:
        """Derive one node's plan from this template."""
        return UpgradePlan(
            node_id=node_id,
            from_version=from_version,
            to_version=self.to_version,
            target_protocol_profile=self.target_protocol_profile,
            target_schema_versions=self.target_schema_versions,
            minimum_version_floor=self.minimum_version_floor,
            canary_gate=self.canary_gate,
            rollout_gate=self.rollout_gate,
            final_gate=self.final_gate,
        )


class RolloutCoordinator:
    """Deterministic rolling-upgrade orchestration over per-node
    managers."""

    def __init__(self, population: Mapping[str, UpgradeManager]) -> None:
        if not isinstance(population, Mapping) or not population:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "population must be a non-empty Mapping of node ids to "
                "UpgradeManagers",
            )
        for node_id, manager in population.items():
            validate_opaque_ref(node_id, "population node id")
            if not isinstance(manager, UpgradeManager):
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "population[%r] must be an UpgradeManager (got %s)"
                    % (node_id, type(manager).__name__),
                )
            if manager.node_id != node_id:
                raise UpgradeError(
                    UpgradeReasonCode.POPULATION_MISMATCH,
                    "population key %r does not match manager node id %r"
                    % (node_id, manager.node_id),
                )
        self._population: dict = dict(population)

    # -- introspection --------------------------------------------------

    @property
    def node_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._population))

    def manager(self, node_id: str) -> UpgradeManager:
        if node_id not in self._population:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "unknown node %r in population" % (node_id,),
            )
        return self._population[node_id]

    def inventories(self) -> Tuple[VersionInventory, ...]:
        """Every node's current inventory in sorted node-id order."""
        return tuple(
            self._population[node_id].inventory() for node_id in self.node_ids
        )

    def stages(self) -> Tuple[Tuple[str, Optional[str]], ...]:
        """(node_id, stage) pairs in sorted order (stage None = no plan)."""
        return tuple(
            (node_id, self._population[node_id].stage) for node_id in self.node_ids
        )

    def distinct_software_versions(self) -> Tuple[SoftwareVersion, ...]:
        """Sorted distinct software versions across the population
        (a MIXED-version population has more than one)."""
        return tuple(sorted({m.software_version for m in self._population.values()}))

    # -- rollout phases ---------------------------------------------------

    def _uniform_from_version(self) -> SoftwareVersion:
        versions = self.distinct_software_versions()
        if len(versions) != 1:
            raise UpgradeError(
                UpgradeReasonCode.POPULATION_MISMATCH,
                "a rolling upgrade starts from a uniform population "
                "(found mixed versions %s -- finish or roll back the "
                "active rollout first)"
                % ", ".join(str(version) for version in versions),
            )
        return versions[0]

    def stage_canary(
        self,
        template: RolloutTemplate,
        at: str,
        canary_observations: Sequence[Any],
    ) -> str:
        """Stage the canary (the lexicographically first node): the
        population becomes deliberately mixed-version."""
        validate_instant(at, "stage_canary at")
        if not isinstance(template, RolloutTemplate):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "stage_canary requires a RolloutTemplate",
            )
        from_version = self._uniform_from_version()
        canary_id = self.node_ids[0]
        manager = self._population[canary_id]
        manager.submit_plan(template.plan_for(canary_id, from_version), at)
        manager.begin(at)
        manager.advance(at, canary_observations)
        return canary_id

    def stage_remaining(
        self,
        template: RolloutTemplate,
        at: str,
        observations_by_node: Mapping[str, Sequence[Any]],
    ) -> Tuple[str, ...]:
        """Verify the canary's rollout gate, then stage every
        remaining node.  Any canary failure rolls the canary back and
        halts (later batches never advance on an unhealthy canary);
        any per-node failure rolls back EVERY begun node."""
        validate_instant(at, "stage_remaining at")
        canary_id = self.node_ids[0]
        canary = self._population[canary_id]
        if canary.stage != UpgradeStage.CANARY:
            raise UpgradeError(
                UpgradeReasonCode.WRONG_STAGE,
                "stage_remaining requires the canary %r in CANARY (found "
                "%r -- call stage_canary first)" % (canary_id, canary.stage),
            )
        canary_obs = observations_by_node.get(canary_id, ())
        plan = self._plan_of(canary_id)
        assert plan is not None and plan.rollout_gate is not None
        canary_verdict = canary.evaluate_gate(plan.rollout_gate, canary_obs, at)
        if not canary_verdict.passed():
            # Fail closed: the canary is not healthy enough to roll out
            # -- roll it back, halt, and surface the verdict.
            canary.rollback(at)
            raise UpgradeError(
                UpgradeReasonCode.GATE_NOT_PASSED,
                "canary %r rollout gate %s: rollout halted and canary "
                "rolled back (%s)" % (canary_id, canary_verdict.verdict,
                                      canary_verdict.detail),
            )
        begun: list = [canary_id]
        from_version = self._population[canary_id].plan_from_version()
        assert from_version is not None
        try:
            for node_id in self.node_ids[1:]:
                manager = self._population[node_id]
                manager.submit_plan(template.plan_for(node_id, from_version), at)
                manager.begin(at)
                manager.advance(at, observations_by_node.get(node_id, ()))
                begun.append(node_id)
        except UpgradeError:
            self.halt_and_rollback(at)
            raise
        return tuple(begun)

    def commit_population(
        self,
        at: str,
        observations_by_node: Mapping[str, Sequence[Any]],
    ) -> Tuple[str, ...]:
        """Walk every staged node through rollout gate -> final gate
        -> commit.  Any failure halts and rolls back EVERY node."""
        validate_instant(at, "commit_population at")
        committed: list = []
        try:
            for node_id in self.node_ids:
                manager = self._population[node_id]
                if manager.stage != UpgradeStage.CANARY:
                    raise UpgradeError(
                        UpgradeReasonCode.WRONG_STAGE,
                        "node %r is in %r (commit_population requires every "
                        "node staged in CANARY)" % (node_id, manager.stage),
                    )
                manager.advance(at, observations_by_node.get(node_id, ()))  # -> ROLLING
                manager.advance(at, observations_by_node.get(node_id, ()))  # -> commit-ready
                manager.commit(at)
                committed.append(node_id)
        except UpgradeError:
            self.halt_and_rollback(at)
            raise
        return tuple(committed)

    def halt_and_rollback(self, at: str) -> Tuple[str, ...]:
        """Clean up every node with an active (non-terminal) plan, in
        sorted order: staged-live nodes roll back; PLANNED nodes (a
        submit succeeded but begin() never did) abort.  This never
        raises: it is the failure-path cleanup, and it must never mask
        the error that triggered it."""
        validate_instant(at, "halt_and_rollback at")
        rolled = []
        for node_id in self.node_ids:
            manager = self._population[node_id]
            stage = manager.stage
            if stage is None or UpgradeStage.is_terminal(stage):
                continue
            if stage == UpgradeStage.PLANNED:
                manager.abort(at)
            else:
                manager.rollback(at)
            rolled.append(node_id)
        return tuple(rolled)

    def rollback_population(self, at: str, target: SoftwareVersion) -> Tuple[str, ...]:
        """Roll the whole population back to one target version.

        Downgrade protection is enforced per node: a target below any
        node's minimum-version floor is DOWNGRADE_BLOCKED (event
        recorded, fail closed) BEFORE anything is rolled back; a
        target that is not some node's staged from_version is a
        POPULATION_MISMATCH (there is nothing else to roll back to --
        in-band rollbacks restore staged plans' origins only).
        """
        validate_instant(at, "rollback_population at")
        if not isinstance(target, SoftwareVersion):
            raise UpgradeError(
                UpgradeReasonCode.VERSION_KIND_CONFLATED,
                "rollback target must be a SoftwareVersion",
            )
        active = {
            node_id: self._population[node_id]
            for node_id in self.node_ids
            if self._population[node_id].stage is not None
            and not UpgradeStage.is_terminal(self._population[node_id].stage or "")
        }
        # Downgrade protection first, for EVERY node, before anything
        # is rolled back (fail closed atomically, not node-by-node).
        for node_id in sorted(active):
            manager = active[node_id]
            if target < manager.minimum_version_floor:
                manager.record_downgrade_block(at, target)
                raise UpgradeError(
                    UpgradeReasonCode.DOWNGRADE_BLOCKED,
                    "population rollback to %s is blocked: node %r minimum "
                    "version floor is %s (downgrade protection fails closed)"
                    % (target, node_id, manager.minimum_version_floor),
                )
        for node_id in sorted(active):
            manager = active[node_id]
            plan_from = manager.plan_from_version()
            if plan_from is None or plan_from != target:
                raise UpgradeError(
                    UpgradeReasonCode.POPULATION_MISMATCH,
                    "node %r has no staged plan from %s (its active plan "
                    "starts at %s); in-band population rollback restores "
                    "staged origins only"
                    % (node_id, target, plan_from),
                )
        rolled = []
        for node_id in sorted(active):
            manager = active[node_id]
            if manager.stage == UpgradeStage.PLANNED:
                manager.abort(at)  # never went live; the honest exit
            else:
                manager.rollback(at)
            rolled.append(node_id)
        return tuple(rolled)

    # -- helpers -----------------------------------------------------------

    def _plan_of(self, node_id: str) -> Optional[UpgradePlan]:
        return self._population[node_id].active_plan()
