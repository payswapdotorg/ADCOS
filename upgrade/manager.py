"""The node-local staged-upgrade lifecycle manager (WORK-029).

Implements the frozen staged-upgrade ladder over one node's version
truth:

    PLANNED -> PREPARED -> CANARY -> ROLLING -> COMMITTED
                        \\-> ROLLED_BACK  /-> ABORTED

Layering contract (spec/architecture.md 5.6 -- "upgrade state" is
node-local lifecycle state):

- the manager owns EXACTLY the node's own upgrade lifecycle: its
  staged plan, its stage, its health-gate verdicts, its rollback
  window, and its minimum-version floor.  It never touches topology,
  session, routing, policy, or identity state, and it is never a
  second authority for any of them;
- protocol compatibility stays WORK-003 (the plan's target profile
  major is validated against the real protocol artifact);
- capability negotiation stays WORK-005 (mixed-version coexistence is
  answered in ``upgrade.compatibility`` by delegation);
- gate evidence stays WORK-026: gates consume REAL telemetry
  observations read-only as DATA -- and the node's own genuine
  WORK-026 ``TelemetryStore`` is the provenance oracle: every
  supplied observation must be a genuine ``TelemetryObservation``
  that the store has actually RECORDED (caller-fabricated objects,
  duck-typed fakes, and valid-but-unrecorded observations are
  rejected outright; PR #31 Architect review blocker 1 -- a
  complete-content observation id is integrity, recordedness is
  authority provenance).  A recorded-but-absent or stale observation
  still means INSUFFICIENT_EVIDENCE and the gate FAILS CLOSED
  (health is never assumed);
- schema evolution is the migration registry's (:mod:`upgrade
  .migrations`) verdict -- the manager only walks registered,
  reversible paths.

Fail-closed invariants enforced here:

1. **A stage advance is earned only by an explicit gate PASS.**  A
   FAIL or INSUFFICIENT_EVIDENCE verdict raises and leaves the stage
   unchanged.
2. **Staged implies reversible.**  ``begin()`` rehearses the complete
   forward migration chain on a copy and verifies the chain is fully
   reversible BEFORE any live change; a plan with a non-reversible
   chain cannot be staged at all.
3. **COMMITTED is irreversible.**  Post-commit rollback raises
   ROLLBACK_WINDOW_CLOSED -- a further change is a new plan, never a
   silent re-open of the closed window.
4. **Downgrade protection is a ratchet.**  The node's
   minimum-version floor only ever moves UP (at commit), a plan may
   never start below the floor (FLOOR_VIOLATION), and a population
   rollback target below the floor is blocked
   (:class:`upgrade.population.RolloutCoordinator`).
5. **Plans are upgrades by construction** (``UpgradePlan`` rejects
   ``to <= from``): an in-band downgrade does not exist.
6. **Live migration application is transactional** (PR #31
   Architect review blocker 2): the PREPARED->CANARY transition
   executes the COMPLETE forward chain for EVERY artifact on
   isolated deep copies and swaps the live schema state/versions
   only after the entire chain succeeds -- a mutating, raising, or
   invalid-returning migration callable can never leave live state
   partially modified (migration purity is a documented
   requirement, but the registry accepts arbitrary callables, so
   the manager does not rely on it).  The rollback path applies
   the same isolation to its reverse proof-walk; its authoritative
   restore is the byte-identical pre-plan snapshot.

Determinism: injected instants only (never a wall clock), sorted
iteration everywhere, deep copies through canonical JSON round-trips
(schema state is canonical-JSON DATA by contract), no randomness.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .errors import UpgradeError, UpgradeReasonCode
from .migrations import MigrationRegistry
from .model import (
    EventKind,
    GateVerdict,
    HealthGateResult,
    HealthGateSpec,
    ProtocolProfile,
    SoftwareVersion,
    UpgradeEvent,
    UpgradePlan,
    UpgradeStage,
    VersionInventory,
    event_ledger_digest,
)
from .validation import validate_instant, validate_opaque_ref

# The WORK-026 telemetry authority's recorded-evidence boundary (PR
# #31 Architect review blocker 1): the manager never accepts
# caller-supplied observation objects on faith -- provenance is
# resolved against the node's own genuine TelemetryStore.
from telemetry.store import TelemetryStore


def _deep_copy_state(state: Mapping[str, Any]) -> Dict[str, Any]:
    """A deterministic deep copy of canonical-JSON schema state DATA."""
    return json.loads(json.dumps(state, sort_keys=True))


def _observation_at_least(observation: Any, at: str) -> bool:
    """True iff the observation's freshness window still covers ``at``."""
    from protocol.temporal import parse_instant

    return parse_instant(observation.freshness_until) >= parse_instant(at)


class UpgradeManager:
    """One node's staged-upgrade lifecycle state machine."""

    def __init__(
        self,
        node_id: str,
        software_version: SoftwareVersion,
        protocol_profile: ProtocolProfile,
        schema_versions: Mapping[str, str],
        schema_state: Mapping[str, Mapping[str, Any]],
        migration_registry: MigrationRegistry,
        telemetry_store: TelemetryStore,
        minimum_version_floor: Optional[SoftwareVersion] = None,
    ) -> None:
        validate_opaque_ref(node_id, "manager node_id")
        if not isinstance(software_version, SoftwareVersion):
            raise UpgradeError(
                UpgradeReasonCode.VERSION_KIND_CONFLATED,
                "software_version must be a SoftwareVersion",
            )
        if not isinstance(protocol_profile, ProtocolProfile):
            raise UpgradeError(
                UpgradeReasonCode.VERSION_KIND_CONFLATED,
                "protocol_profile must be a ProtocolProfile",
            )
        if not isinstance(migration_registry, MigrationRegistry):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "migration_registry must be a MigrationRegistry",
            )
        if not isinstance(telemetry_store, TelemetryStore):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "telemetry_store must be the node's genuine WORK-026 "
                "TelemetryStore (gate-evidence provenance is resolved "
                "against the telemetry authority's recorded set, never "
                "against caller-supplied objects)",
            )
        if set(schema_versions) != set(schema_state):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "schema_versions and schema_state must cover the same "
                "schema ids (got %r vs %r)"
                % (sorted(schema_versions), sorted(schema_state)),
            )
        for schema_id, version in schema_versions.items():
            validate_opaque_ref(schema_id, "schema id")
            from .validation import parse_dotted_pair

            parse_dotted_pair(version, "schema version")
        if not isinstance(schema_state, Mapping):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT, "schema_state must be a Mapping"
            )
        floor = minimum_version_floor if minimum_version_floor is not None else software_version
        if not isinstance(floor, SoftwareVersion):
            raise UpgradeError(
                UpgradeReasonCode.VERSION_KIND_CONFLATED,
                "minimum_version_floor must be a SoftwareVersion",
            )
        self._node_id = node_id
        self._software_version = software_version
        self._protocol_profile = protocol_profile
        self._schema_versions: Dict[str, str] = dict(schema_versions)
        self._schema_state: Dict[str, Dict[str, Any]] = {
            schema_id: _deep_copy_state(state) for schema_id, state in schema_state.items()
        }
        self._registry = migration_registry
        self._telemetry_store = telemetry_store
        self._floor = floor
        self._plan: Optional[UpgradePlan] = None
        self._stage: Optional[str] = None
        self._pre_plan: Optional[Tuple[SoftwareVersion, ProtocolProfile, Dict[str, str], Dict[str, Dict[str, Any]]]] = None
        self._events: List[UpgradeEvent] = []
        self._final_gate_passed = False

    # -- read accessors -----------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def software_version(self) -> SoftwareVersion:
        return self._software_version

    @property
    def protocol_profile(self) -> ProtocolProfile:
        return self._protocol_profile

    @property
    def minimum_version_floor(self) -> SoftwareVersion:
        return self._floor

    @property
    def stage(self) -> Optional[str]:
        """The active plan's stage, or None when no plan exists."""
        return self._stage

    @property
    def plan_id(self) -> Optional[str]:
        return self._plan.plan_id if self._plan is not None else None

    def inventory(self) -> VersionInventory:
        return VersionInventory(
            node_id=self._node_id,
            software_version=self._software_version,
            protocol_profile=self._protocol_profile,
            schema_versions=tuple(sorted(self._schema_versions.items())),
        )

    def schema_state(self, schema_id: str) -> Mapping[str, Any]:
        """A deep copy of one artifact's persisted state (read-only out)."""
        if schema_id not in self._schema_state:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "unknown schema id %r" % (schema_id,),
            )
        return _deep_copy_state(self._schema_state[schema_id])

    def events(self) -> Tuple[UpgradeEvent, ...]:
        return tuple(self._events)

    def ledger_digest(self) -> str:
        return event_ledger_digest(tuple(self._events))

    def active_plan(self) -> Optional[UpgradePlan]:
        """The active (or last) plan, read-only."""
        return self._plan

    def plan_from_version(self) -> Optional[SoftwareVersion]:
        """The active plan's from_version (None when no plan exists)."""
        return self._plan.from_version if self._plan is not None else None

    def record_downgrade_block(self, at: str, target: SoftwareVersion) -> None:
        """Record a DOWNGRADE_BLOCKED audit event on this node (the
        coordinator's population-rollback rejection is auditable)."""
        validate_instant(at, "record_downgrade_block at")
        self._record(
            EventKind.DOWNGRADE_BLOCKED, at,
            "population rollback to %s blocked: below this node's "
            "minimum version floor %s" % (target, self._floor),
        )

    # -- internal bookkeeping ------------------------------------------

    def _record(self, kind: str, at: str, detail: str) -> None:
        stage = self._stage if self._stage is not None else UpgradeStage.PLANNED
        self._events.append(
            UpgradeEvent(
                kind=kind,
                plan_id=self._plan.plan_id if self._plan is not None else "upgrade:plan:none",
                node_id=self._node_id,
                stage=stage,
                at=at,
                detail=detail,
            )
        )

    def _require_active_plan(self) -> UpgradePlan:
        if self._plan is None:
            raise UpgradeError(
                UpgradeReasonCode.WRONG_STAGE,
                "node %s has no active plan" % self._node_id,
            )
        return self._plan

    # -- plan submission -----------------------------------------------

    def submit_plan(self, plan: UpgradePlan, at: str) -> None:
        """Accept a staged-upgrade plan for this node (PLANNED)."""
        validate_instant(at, "submit_plan at")
        if self._plan is not None and not UpgradeStage.is_terminal(self._stage or ""):
            self._record(EventKind.PLAN_REJECTED, at,
                         "another plan is active in stage %s" % self._stage)
            raise UpgradeError(
                UpgradeReasonCode.ACTIVE_PLAN_EXISTS,
                "node %s already has an active plan in stage %s"
                % (self._node_id, self._stage),
            )
        if plan.node_id != self._node_id:
            self._record(EventKind.PLAN_REJECTED, at,
                         "plan is for node %r, this node is %r" % (plan.node_id, self._node_id))
            raise UpgradeError(
                UpgradeReasonCode.PLAN_INVALID,
                "plan targets node %r but this manager is node %r"
                % (plan.node_id, self._node_id),
            )
        if plan.from_version != self._software_version:
            self._record(
                EventKind.PLAN_REJECTED, at,
                "plan from_version %s does not match current software %s"
                % (plan.from_version, self._software_version),
            )
            raise UpgradeError(
                UpgradeReasonCode.PLAN_VERSION_MISMATCH,
                "plan from_version %s does not match node %s current "
                "software version %s"
                % (plan.from_version, self._node_id, self._software_version),
            )
        if plan.from_version < self._floor:
            self._record(
                EventKind.DOWNGRADE_BLOCKED, at,
                "plan starts at %s, below the minimum version floor %s"
                % (plan.from_version, self._floor),
            )
            raise UpgradeError(
                UpgradeReasonCode.FLOOR_VIOLATION,
                "node %s refuses a plan from %s: the minimum version floor "
                "is %s (downgrade protection; bring the node up to the "
                "floor out-of-band, never through an in-band plan)"
                % (self._node_id, plan.from_version, self._floor),
            )
        # Target protocol major must be KNOWN to the WORK-003 artifact.
        from protocol.versioning import Classification, classify_major, protocol_metadata

        disposition = classify_major(
            plan.target_protocol_profile.major, protocol_metadata(),
        )
        if disposition != Classification.KNOWN_COMPATIBLE:
            self._record(
                EventKind.PLAN_REJECTED, at,
                "target protocol major %d is %s per the WORK-003 artifact"
                % (plan.target_protocol_profile.major, disposition),
            )
            raise UpgradeError(
                UpgradeReasonCode.MAJOR_UNKNOWN,
                "plan target protocol major %d is %s: unknown majors fail "
                "closed" % (plan.target_protocol_profile.major, disposition),
            )
        # Schema targets: same key set, reversible registered paths.
        if set(dict(plan.target_schema_versions)) != set(self._schema_versions):
            self._record(
                EventKind.PLAN_REJECTED, at,
                "plan targets schema ids %r but node has %r"
                % (sorted(dict(plan.target_schema_versions)), sorted(self._schema_versions)),
            )
            raise UpgradeError(
                UpgradeReasonCode.PLAN_INVALID,
                "plan target schema ids %r do not match the node's %r"
                % (sorted(dict(plan.target_schema_versions)), sorted(self._schema_versions)),
            )
        for schema_id in sorted(self._schema_versions):
            source = self._schema_versions[schema_id]
            target = dict(plan.target_schema_versions)[schema_id]
            if source == target:
                continue  # unchanged artifact: nothing to migrate
            try:
                path = self._registry.path(schema_id, source, target)
            except UpgradeError as error:
                self._record(EventKind.PLAN_REJECTED, at, error.detail)
                raise
            non_reversible = [d for d in path if not d.reversible]
            if non_reversible:
                self._record(
                    EventKind.PLAN_REJECTED, at,
                    "schema %s path %s -> %s crosses a non-reversible step "
                    "(%s -> %s): staged upgrades must be rollback-able"
                    % (schema_id, source, target,
                       non_reversible[0].from_version, non_reversible[0].to_version),
                )
                raise UpgradeError(
                    UpgradeReasonCode.MIGRATION_NOT_REVERSIBLE,
                    "plan rejected: schema %s chain %s -> %s is not fully "
                    "reversible (a staged upgrade that cannot be rolled "
                    "back is not a staged upgrade -- it is a flag day)"
                    % (schema_id, source, target),
                )
        self._plan = plan
        self._stage = UpgradeStage.PLANNED
        self._final_gate_passed = False
        self._record(
            EventKind.PLAN_ACCEPTED, at,
            "upgrade %s -> %s staged (target protocol %s, floor %s)"
            % (plan.from_version, plan.to_version,
               plan.target_protocol_profile, plan.minimum_version_floor or plan.from_version),
        )

    # -- staging (PREPARED) ---------------------------------------------

    def begin(self, at: str) -> None:
        """Rehearse the complete migration chain on a copy, then enter
        PREPARED (staged, not yet live)."""
        validate_instant(at, "begin at")
        plan = self._require_active_plan()
        if self._stage != UpgradeStage.PLANNED:
            raise UpgradeError(
                UpgradeReasonCode.WRONG_STAGE,
                "begin() requires stage PLANNED (node %s is in %s)"
                % (self._node_id, self._stage),
            )
        # Rehearsal: the complete forward chain must run on a copy.
        for schema_id in sorted(self._schema_versions):
            source = self._schema_versions[schema_id]
            target = dict(plan.target_schema_versions)[schema_id]
            if source == target:
                continue
            self._registry.migrate_forward(
                _deep_copy_state(self._schema_state[schema_id]),
                schema_id, source, target,
            )
        self._pre_plan = (
            self._software_version,
            self._protocol_profile,
            dict(self._schema_versions),
            {schema_id: _deep_copy_state(state) for schema_id, state in self._schema_state.items()},
        )
        self._stage = UpgradeStage.PREPARED
        self._record(
            EventKind.STAGE_ADVANCED, at,
            "rehearsal complete: migration chain runs and is fully "
            "reversible; new version staged, not yet live",
        )

    # -- gate evaluation --------------------------------------------------

    def evaluate_gate(
        self, spec: HealthGateSpec, observations: Sequence[Any], at: str,
    ) -> HealthGateResult:
        """Evaluate one health gate over REAL telemetry observations.

        Fail closed: no matching observation, or every matching
        observation stale (``freshness_until`` before ``at``), is
        INSUFFICIENT_EVIDENCE -- health is never assumed.  A usable
        observation exists => the deterministic LATEST one decides
        (max by (observed_at, sequence, observation_id)); PASS iff
        its value is within the gate's threshold.

        Evidence is SELF-SOURCED only (LOCK-008): a remote node's
        statement about this node is a claim by the reporting node,
        never this node's state, so only observations whose
        ``source_node_id`` is this node count as gate evidence.

        Evidence is PROVENANCE-VERIFIED against the node's own genuine
        WORK-026 ``TelemetryStore`` (PR #31 Architect review blocker
        1): every supplied observation must be a genuine
        (constructor-validated) ``TelemetryObservation`` that the
        telemetry authority has actually RECORDED -- the store is the
        only origin of gate evidence.  A duck-typed fake (however
        completely populated), a valid observation that was never
        recorded, or a tampered variant of a recorded id is rejected
        outright with INVALID_INPUT: a complete-content observation
        id is INTEGRITY, not authority provenance, and caller-supplied
        DATA is never turned into authoritative evidence.
        """
        if not isinstance(spec, HealthGateSpec):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "gate spec must be a HealthGateSpec",
            )
        validate_instant(at, "evaluate_gate at")
        from telemetry.model import TelemetryObservation

        matching = []
        stale = 0
        foreign = 0
        for observation in observations:
            if not isinstance(observation, TelemetryObservation):
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "gate evidence must be a genuine WORK-026 "
                    "TelemetryObservation (got %s): attribute-shaped "
                    "fakes are never telemetry, however completely "
                    "populated" % (type(observation).__name__,),
                )
            if not self._telemetry_store.is_recorded(observation):
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "gate evidence %s was never recorded by the "
                    "telemetry authority (the store is the only origin "
                    "of gate evidence: a caller-injected observation "
                    "with internally valid content and id is still not "
                    "authoritative -- record it through the WORK-026 "
                    "ingest discipline first)"
                    % (observation.observation_id[:56],),
                )
            if (
                observation.subject_kind == spec.subject_kind
                and observation.subject_ref == spec.subject_ref
                and observation.metric == spec.metric
            ):
                if observation.source_node_id != self._node_id:
                    foreign += 1  # a claim by another node: never gate evidence
                    continue
                if _observation_at_least(observation, at):
                    matching.append(observation)
                else:
                    stale += 1
        if not matching:
            details = []
            if foreign:
                details.append(
                    "%d foreign-sourced observation(s) ignored (LOCK-008: "
                    "claims about a node are never its own state)" % foreign
                )
            if stale:
                details.append("all %d self-sourced observation(s) stale" % stale)
            if not details:
                details.append(
                    "no self-sourced observation matches (%s, %s, %s)"
                    % (spec.subject_kind, spec.subject_ref, spec.metric)
                )
            return HealthGateResult(
                label=spec.label, verdict=GateVerdict.INSUFFICIENT_EVIDENCE,
                observed_value=None, observation_id="",
                observed_at="", freshness_until="",
                detail="%s: the gate fails closed, health is never assumed"
                       % "; ".join(details),
            )
        latest = max(
            matching,
            key=lambda o: (o.observed_at, o.sequence, o.observation_id),
        )
        passed = latest.value <= spec.max_value
        return HealthGateResult(
            label=spec.label,
            verdict=GateVerdict.PASS if passed else GateVerdict.FAIL,
            observed_value=latest.value,
            observation_id=latest.observation_id,
            observed_at=latest.observed_at,
            freshness_until=latest.freshness_until,
            detail=(
                "latest observation %d within threshold %d"
                % (latest.value, spec.max_value) if passed else
                "latest observation %d exceeds threshold %d"
                % (latest.value, spec.max_value)
            ),
        )

    # -- staged advance ---------------------------------------------------

    def advance(self, at: str, observations: Sequence[Any]) -> HealthGateResult:
        """Evaluate the current stage's gate and advance on PASS.

        PREPARED --(canary gate)--> CANARY (the new version goes live
        for this node: migrations applied, inventory switched);
        CANARY --(rollout gate)--> ROLLING; ROLLING --(final gate)-->
        commit-ready.  Any FAIL or INSUFFICIENT_EVIDENCE raises and
        leaves the stage unchanged.
        """
        validate_instant(at, "advance at")
        plan = self._require_active_plan()
        gate_by_stage = {
            UpgradeStage.PREPARED: plan.canary_gate,
            UpgradeStage.CANARY: plan.rollout_gate,
            UpgradeStage.ROLLING: plan.final_gate,
        }
        if self._stage not in gate_by_stage:
            if self._stage == UpgradeStage.ROLLING and self._final_gate_passed:
                raise UpgradeError(
                    UpgradeReasonCode.WRONG_STAGE,
                    "node %s is commit-ready (final gate passed): call "
                    "commit()" % self._node_id,
                )
            raise UpgradeError(
                UpgradeReasonCode.WRONG_STAGE,
                "advance() requires an active plan in PREPARED/CANARY/"
                "ROLLING (node %s is in %s)" % (self._node_id, self._stage),
            )
        gate = gate_by_stage[self._stage]
        assert gate is not None  # plan construction guarantees gates
        result = self.evaluate_gate(gate, observations, at)
        if result.verdict == GateVerdict.INSUFFICIENT_EVIDENCE:
            self._record(
                EventKind.GATE_INSUFFICIENT_EVIDENCE, at,
                "gate %r: %s" % (gate.label, result.detail),
            )
            raise UpgradeError(
                UpgradeReasonCode.GATE_INSUFFICIENT_EVIDENCE,
                "gate %r: %s (stage unchanged)" % (gate.label, result.detail),
            )
        if result.verdict == GateVerdict.FAIL:
            self._record(
                EventKind.GATE_FAIL, at,
                "gate %r: %s" % (gate.label, result.detail),
            )
            raise UpgradeError(
                UpgradeReasonCode.GATE_NOT_PASSED,
                "gate %r: %s (stage unchanged -- no advance on failure)"
                % (gate.label, result.detail),
            )
        self._record(
            EventKind.GATE_PASS, at,
            "gate %r: %s" % (gate.label, result.detail),
        )
        if self._stage == UpgradeStage.PREPARED:
            # Canary goes live -- TRANSACTIONALLY (PR #31 Architect
            # review blocker 2): the COMPLETE forward chain for EVERY
            # artifact runs on isolated deep copies first, and the
            # live schema state/versions are swapped only after the
            # entire chain succeeds.  A migration callable that
            # mutates its input and raises, or returns invalid DATA,
            # can never leave live state partially modified with stale
            # version metadata: the registry accepts arbitrary
            # callables, so the manager never hands it live state.
            new_state: Dict[str, Dict[str, Any]] = {}
            new_versions: Dict[str, str] = {}
            for schema_id in sorted(self._schema_versions):
                source = self._schema_versions[schema_id]
                target = dict(plan.target_schema_versions)[schema_id]
                if source == target:
                    continue  # unchanged artifact: nothing to migrate
                migrated = self._registry.migrate_forward(
                    _deep_copy_state(self._schema_state[schema_id]),
                    schema_id, source, target,
                )
                new_state[schema_id] = _deep_copy_state(migrated)
                new_versions[schema_id] = target
            # The entire chain succeeded: swap live state atomically.
            self._schema_state = {**self._schema_state, **new_state}
            self._schema_versions = {**self._schema_versions, **new_versions}
            self._software_version = plan.to_version
            self._protocol_profile = plan.target_protocol_profile
            self._stage = UpgradeStage.CANARY
            self._record(
                EventKind.STAGE_ADVANCED, at,
                "canary live at %s (protocol %s)"
                % (plan.to_version, plan.target_protocol_profile),
            )
        elif self._stage == UpgradeStage.CANARY:
            self._stage = UpgradeStage.ROLLING
            self._record(
                EventKind.STAGE_ADVANCED, at,
                "rollout confirmed at %s" % plan.to_version,
            )
        else:  # ROLLING
            self._final_gate_passed = True
            self._record(
                EventKind.GATE_PASS, at,
                "final gate passed: commit-ready",
            )
        return result

    # -- commit / rollback / abort ----------------------------------------

    def commit(self, at: str) -> None:
        """Terminal success: close the rollback window and ratchet the
        minimum-version floor."""
        validate_instant(at, "commit at")
        plan = self._require_active_plan()
        if self._stage != UpgradeStage.ROLLING or not self._final_gate_passed:
            raise UpgradeError(
                UpgradeReasonCode.WRONG_STAGE,
                "commit() requires stage ROLLING with the final gate "
                "passed (node %s is in %s, final gate %s)"
                % (self._node_id, self._stage,
                   "passed" if self._final_gate_passed else "not passed"),
            )
        new_floor = max(
            self._floor, plan.minimum_version_floor or plan.from_version,
        )
        self._floor = new_floor
        self._stage = UpgradeStage.COMMITTED
        self._record(
            EventKind.COMMITTED, at,
            "upgrade to %s committed; rollback window closed; floor "
            "ratcheted to %s" % (plan.to_version, new_floor),
        )

    def rollback(self, at: str) -> None:
        """Reverse the staged upgrade: restore the pre-plan version
        truth and reverse-migrate the schema state."""
        validate_instant(at, "rollback at")
        plan = self._require_active_plan()
        if self._stage in UpgradeStage.TERMINAL_VALUES:
            if self._stage == UpgradeStage.COMMITTED:
                self._record(
                    EventKind.PLAN_REJECTED, at,
                    "rollback attempted after COMMITTED",
                )
                raise UpgradeError(
                    UpgradeReasonCode.ROLLBACK_WINDOW_CLOSED,
                    "node %s committed %s: the rollback window is closed "
                    "(a further change is a new plan, never a silent "
                    "re-open)" % (self._node_id, plan.plan_id[:48]),
                )
            raise UpgradeError(
                UpgradeReasonCode.WRONG_STAGE,
                "node %s is in terminal stage %s (nothing to roll back)"
                % (self._node_id, self._stage),
            )
        if self._stage == UpgradeStage.PLANNED:
            raise UpgradeError(
                UpgradeReasonCode.WRONG_STAGE,
                "node %s is in PLANNED (nothing is staged; abort() is the "
                "exit)" % self._node_id,
            )
        if self._stage in (UpgradeStage.CANARY, UpgradeStage.ROLLING):
            # Live at the plan target: prove the reverse chain runs
            # from the LIVE version back to the PRE-PLAN ORIGIN -- on
            # ISOLATED COPIES (PR #31 Architect review blocker 2: the
            # registry accepts arbitrary callables, so a mutating or
            # raising backward migration must never corrupt live
            # state mid-rollback).  The walk is the reversibility
            # proof; the authoritative restore below is the
            # byte-identical pre-plan snapshot.  (Surfaced by the PR
            # #31 isolation regression: the previous walk compared
            # the live version against the plan TARGET -- equal by
            # construction once the canary is live -- so the
            # "reverse-migrate" loop never actually executed; the
            # proof now genuinely walks live -> origin.)
            assert self._pre_plan is not None
            origin_versions = self._pre_plan[2]
            for schema_id in sorted(self._schema_versions):
                live = self._schema_versions[schema_id]
                origin = origin_versions[schema_id]
                if live == origin:
                    continue
                self._registry.migrate_backward(
                    _deep_copy_state(self._schema_state[schema_id]),
                    schema_id, live, origin,
                )
        assert self._pre_plan is not None
        (software, profile, versions, state) = self._pre_plan
        self._software_version = software
        self._protocol_profile = profile
        self._schema_versions = dict(versions)
        self._schema_state = {
            schema_id: _deep_copy_state(artifact) for schema_id, artifact in state.items()
        }
        self._stage = UpgradeStage.ROLLED_BACK
        self._record(
            EventKind.ROLLBACK_COMPLETED, at,
            "rolled back to %s (schema state reverse-migrated, byte-identical)"
            % software,
        )

    def abort(self, at: str) -> None:
        """Exit a plan that never went live (PLANNED/PREPARED only)."""
        validate_instant(at, "abort at")
        self._require_active_plan()
        if self._stage not in (UpgradeStage.PLANNED, UpgradeStage.PREPARED):
            raise UpgradeError(
                UpgradeReasonCode.WRONG_STAGE,
                "abort() requires PLANNED/PREPARED (node %s is in %s; once "
                "staged changes are live, rollback() is the honest exit)"
                % (self._node_id, self._stage),
            )
        self._stage = UpgradeStage.ABORTED
        self._record(EventKind.ABORTED, at, "plan aborted before any live change")
