"""ADCOS upgrade / rollback / compatibility canonical model (WORK-029).

Frozen vocabularies and canonical records for the upgrade, rollback,
and compatibility manager:

- **VersionKind** -- the four governance version kinds (spec/governance.md
  section 3): Architecture, Protocol, Schema, Implementation.  They are
  independent lines that are never conflated or collapsed; the model
  enforces the separation STRUCTURALLY: an Implementation Version is a
  ``MAJOR.MINOR.PATCH`` :class:`SoftwareVersion`, a Protocol/Schema
  version is a ``MAJOR.MINOR`` pair, and neither parses where the
  other is required (fail closed, VERSION_KIND_CONFLATED /
  VERSION_MALFORMED).  The Architecture Version is a specification
  concern (ACR-governed) and is deliberately NOT a dimension of this
  model at all.
- **SoftwareVersion** -- one Implementation Version (Agent build line):
  tracked by the implementation, never evidence of conformance or of
  specification compatibility.
- **ProtocolProfile** -- one point on the WORK-003 Protocol Version
  line: a major version plus the highest minor this software speaks.
  The known-major truth stays ``spec/schemas/protocol.json``
  (WORK-003); this record only carries it.
- **VersionInventory** -- one node's complete version truth: its
  Implementation Version, its ProtocolProfile, and its per-artifact
  Schema Versions.
- **UpgradeStage** -- the frozen staged-upgrade ladder:
  ``PLANNED -> PREPARED -> CANARY -> ROLLING -> COMMITTED`` with the
  terminal exits ``ROLLED_BACK`` and ``ABORTED``.  A stage advance is
  earned ONLY by an explicit gate PASS (never assumed); COMMITTED is
  irreversible (the rollback window closes -- a further change is a
  new plan, never a silent re-open).
- **GateVerdict / HealthGateSpec / HealthGateResult** -- upgrade health
  gates.  A gate is a frozen (subject kind, subject ref, metric,
  threshold) quad validated against the REAL WORK-026 metric registry;
  its evidence is REAL telemetry observations consumed read-only as
  DATA.  No observation / stale observation => INSUFFICIENT_EVIDENCE:
  the gate fails closed, it never assumes health.
- **MigrationDescriptor** -- one reversible-or-not schema migration
  step on one Schema Version line, with the governance section-3
  discipline enforced at construction: an additive step bumps exactly
  one minor; a breaking step bumps exactly one major and resets the
  minor to 0.
- **UpgradePlan** -- one node's staged upgrade: from/to Implementation
  Versions, the target ProtocolProfile, the target Schema Versions,
  the post-commit minimum version floor (downgrade protection), and
  the canary/rollout/final health gates.  A plan is an upgrade plan BY
  CONSTRUCTION (to > from) -- a downgrade plan is not a constructible
  record.
- **UpgradeEvent** -- one auditable upgrade-lifecycle event (the plan
  ledger: accept/reject, gate verdicts, stage advances, commit,
  rollback, downgrade blocks, aborts).

TAMPER-EVIDENT COMPLETE-CONTENT IDENTITY (the PR #27 remediation-2
rule, applied from birth): every content-derived id in this family
(``VersionInventory``, ``MigrationDescriptor``, ``UpgradePlan``,
``UpgradeEvent``) is computed over the COMPLETE canonical record DATA
-- exactly ``to_dict()`` minus the id itself.  A record whose DATA
diverges in ANY field while retaining a previous id is rejected at
construction; there is no field whose mutation is invisible to the
identity.

Integer/ordering determinism discipline: versions are integer
triples/pairs, instants are injected RFC 3339 strings, schema-version
mappings are canonical sorted tuple-of-pairs, iteration is over sorted
containers, and no binary floating point, wall clock, randomness, or
dict-iteration-order dependence exists anywhere in the family.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from .errors import UpgradeError, UpgradeReasonCode
from .validation import (
    parse_dotted_pair,
    parse_software_version,
    validate_instant,
    validate_opaque_ref,
    validate_schema_version_map,
)

# ----------------------------------------------------------------------
# Identity prefixes (the WORK-029 family namespace)
# ----------------------------------------------------------------------

INVENTORY_ID_PREFIX = "upgrade:inventory:"
MIGRATION_ID_PREFIX = "upgrade:migration:"
PLAN_ID_PREFIX = "upgrade:plan:"
EVENT_ID_PREFIX = "upgrade:event:"


# ----------------------------------------------------------------------
# The four governance version kinds (never conflated)
# ----------------------------------------------------------------------

class VersionKind:
    """The frozen four-kind version taxonomy (spec/governance.md
    section 3).  Independent lines, never collapsed into one number.

    The ARCHITECTURE kind is listed for completeness of the taxonomy
    and is deliberately NOT a dimension of the upgrade model: the
    Architecture Version is declared only in ``spec/architecture.md``
    and changes only through an Architecture Change Request -- there
    is no runtime upgrade operation on it.
    """

    ARCHITECTURE = "architecture"
    PROTOCOL = "protocol"
    SCHEMA = "schema"
    IMPLEMENTATION = "implementation"

    ALL_VALUES = frozenset({ARCHITECTURE, PROTOCOL, SCHEMA, IMPLEMENTATION})


# ----------------------------------------------------------------------
# SoftwareVersion (the Implementation Version line)
# ----------------------------------------------------------------------

@dataclass(frozen=True, order=True)
class SoftwareVersion:
    """One Implementation Version: a canonical ``MAJOR.MINOR.PATCH``
    integer triple (governance section 3 kind 4).

    It is a DIFFERENT version kind from the Protocol Version and from
    every Schema Version: it parses only three-component strings and
    is never accepted where a ``MAJOR.MINOR`` line is required (the
    structural version-kind separation).
    """

    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        for name, value in (
            ("major", self.major), ("minor", self.minor), ("patch", self.patch),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise UpgradeError(
                    UpgradeReasonCode.VERSION_MALFORMED,
                    "SoftwareVersion %s must be a non-negative int (got %r)" % (name, value),
                )
        if (self.major, self.minor, self.patch) == (0, 0, 0):
            raise UpgradeError(
                UpgradeReasonCode.VERSION_MALFORMED,
                "SoftwareVersion 0.0.0 is not a real release version",
            )

    @classmethod
    def parse(cls, value: str) -> "SoftwareVersion":
        major, minor, patch = parse_software_version(value)
        return cls(major=major, minor=minor, patch=patch)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%d.%d.%d" % (self.major, self.minor, self.patch)


# ----------------------------------------------------------------------
# ProtocolProfile (a point on the WORK-003 Protocol Version line)
# ----------------------------------------------------------------------

@dataclass(frozen=True, order=True)
class ProtocolProfile:
    """One point on the Protocol Version line: a major version plus
    the highest minor this software speaks (the additive-evolution
    head; section 7 rule 5: additive changes use minor versions and
    feature negotiation).

    The known-major truth is WORK-003's ``spec/schemas/protocol.json``
    (``protocol.versioning.protocol_metadata()``); this record carries
    a profile, it never redefines the line.  ``major >= 1`` mirrors
    the envelope's own version bound.
    """

    major: int
    max_minor: int

    def __post_init__(self) -> None:
        if isinstance(self.major, bool) or not isinstance(self.major, int) or self.major < 1:
            raise UpgradeError(
                UpgradeReasonCode.VERSION_MALFORMED,
                "ProtocolProfile major must be an int >= 1 (got %r)" % (self.major,),
            )
        if isinstance(self.max_minor, bool) or not isinstance(self.max_minor, int) or self.max_minor < 0:
            raise UpgradeError(
                UpgradeReasonCode.VERSION_MALFORMED,
                "ProtocolProfile max_minor must be a non-negative int (got %r)" % (self.max_minor,),
            )

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%d.%d" % (self.major, self.max_minor)


# ----------------------------------------------------------------------
# VersionInventory (one node's complete version truth)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class VersionInventory:
    """One node's complete version truth: Implementation Version,
    ProtocolProfile, and per-artifact Schema Versions.

    The three version kinds ride one record but remain DISTINCT
    fields with DISTINCT grammars (``1.0.0`` software, ``1.1``
    protocol, ``1.0``-style per-artifact schema versions); they are
    never merged into one number.
    """

    node_id: str
    software_version: SoftwareVersion
    protocol_profile: ProtocolProfile
    schema_versions: Tuple[Tuple[str, str], ...] = ()
    inventory_id: str = ""

    def __post_init__(self) -> None:
        validate_opaque_ref(self.node_id, "inventory node_id")
        if not isinstance(self.software_version, SoftwareVersion):
            raise UpgradeError(
                UpgradeReasonCode.VERSION_KIND_CONFLATED,
                "software_version must be a SoftwareVersion (Implementation "
                "Version line), got %s" % (type(self.software_version).__name__,),
            )
        if not isinstance(self.protocol_profile, ProtocolProfile):
            raise UpgradeError(
                UpgradeReasonCode.VERSION_KIND_CONFLATED,
                "protocol_profile must be a ProtocolProfile (Protocol Version "
                "line), got %s" % (type(self.protocol_profile).__name__,),
            )
        if not isinstance(self.schema_versions, tuple):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "schema_versions must be a tuple of (schema_id, version) pairs",
            )
        canonical = validate_schema_version_map(
            {schema_id: version for schema_id, version in self.schema_versions},
            "inventory schema_versions",
        )
        object.__setattr__(self, "schema_versions", canonical)
        expected_id = derive_inventory_id(
            self.node_id, self.software_version, self.protocol_profile, canonical,
        )
        if self.inventory_id == "":
            object.__setattr__(self, "inventory_id", expected_id)
        elif self.inventory_id != expected_id:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "inventory_id %r does not match the complete-content derivation "
                "%r (tampered or misbound inventory id rejected)"
                % (self.inventory_id[:80], expected_id[:80]),
            )

    def content_dict(self) -> Dict[str, Any]:
        """The canonical content dict EXCLUDING ``inventory_id`` itself."""
        return {
            "node_id": self.node_id,
            "software_version": str(self.software_version),
            "protocol_profile": [self.protocol_profile.major, self.protocol_profile.max_minor],
            "schema_versions": [list(pair) for pair in self.schema_versions],
        }

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"inventory_id": self.inventory_id}
        out.update(self.content_dict())
        return out


def derive_inventory_id(
    node_id: str,
    software_version: SoftwareVersion,
    protocol_profile: ProtocolProfile,
    schema_versions: Tuple[Tuple[str, str], ...],
) -> str:
    """The tamper-evident, content-derived inventory id (COMPLETE
    content: exactly ``VersionInventory.to_dict()`` minus the id)."""
    material = canonical_json_bytes(
        {
            "node_id": node_id,
            "software_version": str(software_version),
            "protocol_profile": [protocol_profile.major, protocol_profile.max_minor],
            "schema_versions": [list(pair) for pair in schema_versions],
        }
    )
    return INVENTORY_ID_PREFIX + hashlib.sha256(material).hexdigest()


# ----------------------------------------------------------------------
# The frozen staged-upgrade ladder
# ----------------------------------------------------------------------

class UpgradeStage:
    """The frozen staged-upgrade ladder (spec/architecture.md P12 --
    protocol evolution without flag days; section 25 rule 13 -- no
    flag-day upgrade).

    ``PLANNED -> PREPARED -> CANARY -> ROLLING -> COMMITTED`` with the
    terminal exits ``ROLLED_BACK`` and ``ABORTED``.  Every forward
    transition is EARNED by an explicit health-gate PASS over real
    telemetry evidence; nothing is ever assumed healthy.
    ``COMMITTED`` is terminal and irreversible (the rollback window
    closes); ``ROLLED_BACK`` and ``ABORTED`` are terminal.
    """

    PLANNED = "PLANNED"
    PREPARED = "PREPARED"
    CANARY = "CANARY"
    ROLLING = "ROLLING"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    ABORTED = "ABORTED"

    TERMINAL_VALUES = frozenset({COMMITTED, ROLLED_BACK, ABORTED})
    ALL_VALUES = frozenset(
        {PLANNED, PREPARED, CANARY, ROLLING} | TERMINAL_VALUES
    )

    @classmethod
    def is_terminal(cls, stage: str) -> bool:
        return stage in cls.TERMINAL_VALUES


class EventKind:
    """The frozen upgrade-event vocabulary (the auditable plan ledger:
    privileged upgrade operations are auditable, in the WORK-028
    spirit -- every accept, reject, gate verdict, stage advance,
    commit, rollback, downgrade block, and abort leaves an event)."""

    PLAN_ACCEPTED = "plan-accepted"
    PLAN_REJECTED = "plan-rejected"
    STAGE_ADVANCED = "stage-advanced"
    GATE_PASS = "gate-pass"
    GATE_FAIL = "gate-fail"
    GATE_INSUFFICIENT_EVIDENCE = "gate-insufficient-evidence"
    COMMITTED = "committed"
    ROLLBACK_COMPLETED = "rollback-completed"
    DOWNGRADE_BLOCKED = "downgrade-blocked"
    ABORTED = "aborted"

    ALL_VALUES = frozenset(
        {
            PLAN_ACCEPTED, PLAN_REJECTED, STAGE_ADVANCED, GATE_PASS,
            GATE_FAIL, GATE_INSUFFICIENT_EVIDENCE, COMMITTED,
            ROLLBACK_COMPLETED, DOWNGRADE_BLOCKED, ABORTED,
        }
    )


# ----------------------------------------------------------------------
# Health gates (real WORK-026 evidence, fail closed)
# ----------------------------------------------------------------------

class GateVerdict:
    """The frozen gate-verdict vocabulary."""

    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

    ALL_VALUES = frozenset({PASS, FAIL, INSUFFICIENT_EVIDENCE})


@dataclass(frozen=True)
class HealthGateSpec:
    """One upgrade health gate: a frozen (subject kind, subject ref,
    metric, max accepted value) quad over REAL telemetry observations.

    The (subject kind, metric) pair must exist in the WORK-026 frozen
    metric registry, and the threshold must lie inside the metric's
    legal value range -- a gate that could never fire (or always
    fires) is a construction error, never a runtime surprise.
    """

    label: str
    subject_kind: str
    subject_ref: str
    metric: str
    max_value: int

    def __post_init__(self) -> None:
        validate_opaque_ref(self.label, "gate label")
        validate_opaque_ref(self.subject_ref, "gate subject_ref")
        # The telemetry vocabularies and metric registry are the
        # WORK-026 authority; consumed read-only (lazy import keeps
        # the module import surface minimal).
        from telemetry.model import (
            TELEMETRY_METRIC_REGISTRY,
            TelemetrySubjectKind,
            metric_max_value,
        )

        if self.subject_kind not in TelemetrySubjectKind.values():
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "gate subject_kind %r is not a frozen WORK-026 subject kind"
                % (self.subject_kind,),
            )
        registered = {m.name for m in TELEMETRY_METRIC_REGISTRY.get(self.subject_kind, ())}
        if self.metric not in registered:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "gate metric %r is not a registered WORK-026 metric for "
                "subject kind %r" % (self.metric, self.subject_kind),
            )
        if isinstance(self.max_value, bool) or not isinstance(self.max_value, int):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "gate max_value must be an int (got %s)" % (type(self.max_value).__name__,),
            )
        ceiling = metric_max_value(self.subject_kind, self.metric)
        if self.max_value < 0 or self.max_value > ceiling:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "gate max_value %d is outside the legal range 0..%d for "
                "(%s, %s)" % (self.max_value, ceiling, self.subject_kind, self.metric),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "subject_kind": self.subject_kind,
            "subject_ref": self.subject_ref,
            "metric": self.metric,
            "max_value": self.max_value,
        }


@dataclass(frozen=True)
class HealthGateResult:
    """One evaluated gate verdict with its evidence binding.

    ``observation_id`` is empty exactly when the verdict is
    INSUFFICIENT_EVIDENCE (no usable observation); a PASS/FAIL always
    names the real observation it was computed from.
    """

    label: str
    verdict: str
    observed_value: Optional[int]
    observation_id: str
    observed_at: str
    freshness_until: str
    detail: str

    def __post_init__(self) -> None:
        if self.verdict not in GateVerdict.ALL_VALUES:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "gate verdict %r is not a frozen verdict value" % (self.verdict,),
            )
        if self.verdict == GateVerdict.INSUFFICIENT_EVIDENCE:
            if self.observation_id != "" or self.observed_value is not None:
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "INSUFFICIENT_EVIDENCE carries no observation binding",
                )
        else:
            if not self.observation_id or self.observed_value is None:
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "a %s verdict must bind the observation it was computed "
                    "from" % (self.verdict,),
                )
            for label, value in (
                ("observed_at", self.observed_at),
                ("freshness_until", self.freshness_until),
            ):
                try:
                    parse_instant(value)
                except TemporalError as error:
                    raise UpgradeError(
                        UpgradeReasonCode.INVALID_INPUT,
                        "gate result %s: %s" % (label, error),
                    ) from error

    def passed(self) -> bool:
        return self.verdict == GateVerdict.PASS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "verdict": self.verdict,
            "observed_value": self.observed_value,
            "observation_id": self.observation_id,
            "observed_at": self.observed_at,
            "freshness_until": self.freshness_until,
            "detail": self.detail,
        }


# ----------------------------------------------------------------------
# MigrationDescriptor (one schema-migration step)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class MigrationDescriptor:
    """One schema-migration step on one Schema Version line, with the
    governance section-3 discipline enforced at construction:

    - an ADDITIVE step (``breaking=False``) bumps exactly ONE minor
      (``1.0 -> 1.1``); adding fields is additive evolution;
    - a BREAKING step (``breaking=True``) bumps exactly ONE major and
      resets the minor to zero (``1.2 -> 2.0``); removing, renaming,
      or reinterpreting entries is a breaking change.

    ``reversible`` is an honest declaration, not a promise the
    registry believes blindly: the manager only accepts upgrade plans
    whose COMPLETE migration chain is reversible (a staged upgrade
    that cannot be rolled back is not a staged upgrade -- it is a
    flag day), and the registry still refuses to reverse a declared
    non-reversible step when asked directly.
    """

    schema_id: str
    from_version: str
    to_version: str
    reversible: bool
    breaking: bool
    migration_id: str = ""

    def __post_init__(self) -> None:
        validate_opaque_ref(self.schema_id, "migration schema_id")
        if not isinstance(self.reversible, bool) or not isinstance(self.breaking, bool):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "migration reversible/breaking must be bools",
            )
        source = parse_dotted_pair(self.from_version, "migration from_version")
        target = parse_dotted_pair(self.to_version, "migration to_version")
        if not self.breaking:
            if target[0] != source[0] or target[1] != source[1] + 1:
                raise UpgradeError(
                    UpgradeReasonCode.MIGRATION_INVALID_STEP,
                    "additive migration %s %s -> %s must bump exactly one minor"
                    % (self.schema_id, self.from_version, self.to_version),
                )
        else:
            if target[0] != source[0] + 1 or target[1] != 0:
                raise UpgradeError(
                    UpgradeReasonCode.MIGRATION_INVALID_STEP,
                    "breaking migration %s %s -> %s must bump exactly one "
                    "major and reset the minor to 0"
                    % (self.schema_id, self.from_version, self.to_version),
                )
        expected_id = derive_migration_id(
            self.schema_id, self.from_version, self.to_version,
            self.reversible, self.breaking,
        )
        if self.migration_id == "":
            object.__setattr__(self, "migration_id", expected_id)
        elif self.migration_id != expected_id:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "migration_id %r does not match the complete-content "
                "derivation %r (tampered or misbound migration id rejected)"
                % (self.migration_id[:80], expected_id[:80]),
            )

    def content_dict(self) -> Dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "reversible": self.reversible,
            "breaking": self.breaking,
        }

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"migration_id": self.migration_id}
        out.update(self.content_dict())
        return out


def derive_migration_id(
    schema_id: str, from_version: str, to_version: str,
    reversible: bool, breaking: bool,
) -> str:
    """The tamper-evident, content-derived migration id (COMPLETE
    content: exactly ``MigrationDescriptor.to_dict()`` minus the id)."""
    material = canonical_json_bytes(
        {
            "schema_id": schema_id,
            "from_version": from_version,
            "to_version": to_version,
            "reversible": reversible,
            "breaking": breaking,
        }
    )
    return MIGRATION_ID_PREFIX + hashlib.sha256(material).hexdigest()


# ----------------------------------------------------------------------
# UpgradePlan (one node's staged upgrade)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class UpgradePlan:
    """One node's staged upgrade.

    A plan is an upgrade plan BY CONSTRUCTION: ``to_version >
    from_version`` (NOT_AN_UPGRADE otherwise -- a downgrade is not a
    plan, it is a rollback of an existing plan or a fresh deployment
    decision outside this model).  The minimum version floor obeys
    ``from_version <= floor <= to_version``: the floor is the new
    population minimum AFTER this upgrade commits (downgrade
    protection ratchets up on commit and never moves down).
    """

    node_id: str
    from_version: SoftwareVersion
    to_version: SoftwareVersion
    target_protocol_profile: ProtocolProfile
    target_schema_versions: Tuple[Tuple[str, str], ...] = ()
    minimum_version_floor: Optional[SoftwareVersion] = None
    canary_gate: Optional[HealthGateSpec] = None
    rollout_gate: Optional[HealthGateSpec] = None
    final_gate: Optional[HealthGateSpec] = None
    plan_id: str = ""

    def __post_init__(self) -> None:
        validate_opaque_ref(self.node_id, "plan node_id")
        for name, value in (
            ("from_version", self.from_version), ("to_version", self.to_version),
        ):
            if not isinstance(value, SoftwareVersion):
                raise UpgradeError(
                    UpgradeReasonCode.VERSION_KIND_CONFLATED,
                    "plan %s must be a SoftwareVersion (Implementation "
                    "Version line), got %s" % (name, type(value).__name__),
                )
        if not isinstance(self.target_protocol_profile, ProtocolProfile):
            raise UpgradeError(
                UpgradeReasonCode.VERSION_KIND_CONFLATED,
                "plan target_protocol_profile must be a ProtocolProfile, "
                "got %s" % (type(self.target_protocol_profile).__name__,),
            )
        if self.to_version <= self.from_version:
            raise UpgradeError(
                UpgradeReasonCode.NOT_AN_UPGRADE,
                "plan to_version %s must be greater than from_version %s "
                "(downgrades are rollbacks, never plans)"
                % (self.to_version, self.from_version),
            )
        floor = self.minimum_version_floor or self.from_version
        if not isinstance(floor, SoftwareVersion):
            raise UpgradeError(
                UpgradeReasonCode.VERSION_KIND_CONFLATED,
                "plan minimum_version_floor must be a SoftwareVersion",
            )
        if not (self.from_version <= floor <= self.to_version):
            raise UpgradeError(
                UpgradeReasonCode.PLAN_INVALID,
                "plan floor %s must satisfy from_version %s <= floor <= "
                "to_version %s" % (floor, self.from_version, self.to_version),
            )
        canonical_targets = validate_schema_version_map(
            {schema_id: version for schema_id, version in self.target_schema_versions},
            "plan target_schema_versions",
        )
        object.__setattr__(self, "target_schema_versions", canonical_targets)
        labels = set()
        for name, gate in (
            ("canary_gate", self.canary_gate),
            ("rollout_gate", self.rollout_gate),
            ("final_gate", self.final_gate),
        ):
            if gate is None:
                raise UpgradeError(
                    UpgradeReasonCode.PLAN_INVALID,
                    "plan %s is required (no gate, no advance)" % name,
                )
            if not isinstance(gate, HealthGateSpec):
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "plan %s must be a HealthGateSpec" % name,
                )
            if gate.label in labels:
                raise UpgradeError(
                    UpgradeReasonCode.PLAN_INVALID,
                    "gate labels must be distinct (%r repeated)" % (gate.label,),
                )
            labels.add(gate.label)
        expected_id = derive_plan_id(
            self.node_id, self.from_version, self.to_version,
            self.target_protocol_profile, canonical_targets, floor,
            self.canary_gate, self.rollout_gate, self.final_gate,
        )
        if self.plan_id == "":
            object.__setattr__(self, "plan_id", expected_id)
        elif self.plan_id != expected_id:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "plan_id %r does not match the complete-content derivation "
                "%r (tampered or misbound plan id rejected)"
                % (self.plan_id[:80], expected_id[:80]),
            )

    def content_dict(self) -> Dict[str, Any]:
        floor = self.minimum_version_floor or self.from_version
        return {
            "node_id": self.node_id,
            "from_version": str(self.from_version),
            "to_version": str(self.to_version),
            "target_protocol_profile": [
                self.target_protocol_profile.major,
                self.target_protocol_profile.max_minor,
            ],
            "target_schema_versions": [list(pair) for pair in self.target_schema_versions],
            "minimum_version_floor": str(floor),
            "canary_gate": self.canary_gate.to_dict() if self.canary_gate else None,
            "rollout_gate": self.rollout_gate.to_dict() if self.rollout_gate else None,
            "final_gate": self.final_gate.to_dict() if self.final_gate else None,
        }

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"plan_id": self.plan_id}
        out.update(self.content_dict())
        return out


def derive_plan_id(
    node_id: str,
    from_version: SoftwareVersion,
    to_version: SoftwareVersion,
    target_protocol_profile: ProtocolProfile,
    target_schema_versions: Tuple[Tuple[str, str], ...],
    minimum_version_floor: SoftwareVersion,
    canary_gate: Optional[HealthGateSpec],
    rollout_gate: Optional[HealthGateSpec],
    final_gate: Optional[HealthGateSpec],
) -> str:
    """The tamper-evident, content-derived plan id (COMPLETE content:
    exactly ``UpgradePlan.to_dict()`` minus the id)."""
    material = canonical_json_bytes(
        {
            "node_id": node_id,
            "from_version": str(from_version),
            "to_version": str(to_version),
            "target_protocol_profile": [
                target_protocol_profile.major, target_protocol_profile.max_minor,
            ],
            "target_schema_versions": [list(pair) for pair in target_schema_versions],
            "minimum_version_floor": str(minimum_version_floor),
            "canary_gate": canary_gate.to_dict() if canary_gate else None,
            "rollout_gate": rollout_gate.to_dict() if rollout_gate else None,
            "final_gate": final_gate.to_dict() if final_gate else None,
        }
    )
    return PLAN_ID_PREFIX + hashlib.sha256(material).hexdigest()


# ----------------------------------------------------------------------
# UpgradeEvent (the auditable plan ledger)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class UpgradeEvent:
    """One auditable upgrade-lifecycle event.

    COMPLETE-CONTENT identity: the event id covers the kind, the plan,
    the node, the stage, the instant, and the detail -- an event whose
    content is edited is a different event, full stop.
    """

    kind: str
    plan_id: str
    node_id: str
    stage: str
    at: str
    detail: str = ""
    event_id: str = ""

    def __post_init__(self) -> None:
        if self.kind not in EventKind.ALL_VALUES:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "event kind %r is not a frozen event kind" % (self.kind,),
            )
        if self.stage not in UpgradeStage.ALL_VALUES:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "event stage %r is not a frozen stage value" % (self.stage,),
            )
        validate_opaque_ref(self.node_id, "event node_id")
        validate_opaque_ref(self.plan_id, "event plan_id")
        validate_instant(self.at, "event at")
        validate_opaque_ref(self.detail, "event detail")
        expected_id = derive_event_id(
            self.kind, self.plan_id, self.node_id, self.stage, self.at, self.detail,
        )
        if self.event_id == "":
            object.__setattr__(self, "event_id", expected_id)
        elif self.event_id != expected_id:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "event_id %r does not match the complete-content derivation "
                "%r (tampered or misbound event id rejected)"
                % (self.event_id[:80], expected_id[:80]),
            )

    def content_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "plan_id": self.plan_id,
            "node_id": self.node_id,
            "stage": self.stage,
            "at": self.at,
            "detail": self.detail,
        }

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"event_id": self.event_id}
        out.update(self.content_dict())
        return out


def derive_event_id(
    kind: str, plan_id: str, node_id: str, stage: str, at: str, detail: str,
) -> str:
    """The tamper-evident, content-derived event id (COMPLETE content:
    exactly ``UpgradeEvent.to_dict()`` minus the id)."""
    material = canonical_json_bytes(
        {
            "kind": kind,
            "plan_id": plan_id,
            "node_id": node_id,
            "stage": stage,
            "at": at,
            "detail": detail,
        }
    )
    return EVENT_ID_PREFIX + hashlib.sha256(material).hexdigest()


def event_ledger_digest(events: Tuple[UpgradeEvent, ...]) -> str:
    """A deterministic digest over the COMPLETE ordered event ledger
    (used by the determinism battery and audit)."""
    material = canonical_json_bytes([event.to_dict() for event in events])
    return hashlib.sha256(material).hexdigest()
