"""Canonical serialization for the upgrade family's records (WORK-029).

Every ``*_from_dict`` fails closed: a missing key, an extra key, a
wrong type, or a value that fails the record's own construction
validation raises :class:`upgrade.errors.UpgradeError` -- there is no
lenient/defaulting parse anywhere.  Round-trips are byte-identical
(``to_dict(from_dict(to_dict(record))) == to_dict(record)``).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from .errors import UpgradeError, UpgradeReasonCode
from .model import (
    GateVerdict,
    HealthGateResult,
    HealthGateSpec,
    MigrationDescriptor,
    ProtocolProfile,
    SoftwareVersion,
    UpgradeEvent,
    UpgradePlan,
    VersionInventory,
)
from .validation import parse_dotted_pair, parse_software_version


def _require_mapping(data: object, label: str) -> Dict[str, Any]:
    if not isinstance(data, Mapping):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s must be a mapping (got %s)" % (label, type(data).__name__),
        )
    return dict(data)


def _require_keys(data: Mapping[str, Any], keys: Tuple[str, ...], label: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s is missing required key(s) %r" % (label, missing),
        )


def _require_str(data: Mapping[str, Any], key: str, label: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s.%s must be a str (got %s)" % (label, key, type(value).__name__),
        )
    return value


def _require_int(data: Mapping[str, Any], key: str, label: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s.%s must be an int (got %s)" % (label, key, type(value).__name__),
        )
    return value


def _require_bool(data: Mapping[str, Any], key: str, label: str) -> bool:
    value = data[key]
    if not isinstance(value, bool):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s.%s must be a bool (got %s)" % (label, key, type(value).__name__),
        )
    return value


def _require_pairs(data: Any, label: str) -> Tuple[Tuple[str, str], ...]:
    if not isinstance(data, list):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s must be a list of [schema_id, version] pairs" % label,
        )
    pairs = []
    for entry in data:
        if not isinstance(entry, list) or len(entry) != 2:
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "%s entries must be [schema_id, version] pairs" % label,
            )
        schema_id = entry[0]
        version = entry[1]
        if not isinstance(schema_id, str) or not isinstance(version, str):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "%s pair entries must be strings" % label,
            )
        parse_dotted_pair(version, "%s version" % label)
        pairs.append((schema_id, version))
    return tuple(sorted(pairs))


# ----------------------------------------------------------------------
# SoftwareVersion / ProtocolProfile (canonical wire forms: the
# version as "MAJOR.MINOR.PATCH" text, the profile as [major, minor])
# ----------------------------------------------------------------------

def software_version_from_dict(data: object) -> SoftwareVersion:
    if not isinstance(data, str):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "software version must be a MAJOR.MINOR.PATCH string (got %s)"
            % (type(data).__name__,),
        )
    major, minor, patch = parse_software_version(data)
    return SoftwareVersion(major=major, minor=minor, patch=patch)


def protocol_profile_from_dict(data: object) -> ProtocolProfile:
    if not isinstance(data, list) or len(data) != 2:
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "protocol profile must be a [major, max_minor] pair",
        )
    major, max_minor = data[0], data[1]
    if isinstance(major, bool) or not isinstance(major, int):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT, "protocol profile major must be an int"
        )
    if isinstance(max_minor, bool) or not isinstance(max_minor, int):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT, "protocol profile max_minor must be an int"
        )
    return ProtocolProfile(major=major, max_minor=max_minor)


# ----------------------------------------------------------------------
# VersionInventory
# ----------------------------------------------------------------------

def version_inventory_from_dict(data: object) -> VersionInventory:
    mapping = _require_mapping(data, "inventory")
    _require_keys(
        mapping,
        ("inventory_id", "node_id", "software_version", "protocol_profile",
         "schema_versions"),
        "inventory",
    )
    software = software_version_from_dict(mapping["software_version"])
    profile = protocol_profile_from_dict(mapping["protocol_profile"])
    return VersionInventory(
        node_id=_require_str(mapping, "node_id", "inventory"),
        software_version=software,
        protocol_profile=profile,
        schema_versions=_require_pairs(mapping["schema_versions"], "inventory schema_versions"),
        inventory_id=_require_str(mapping, "inventory_id", "inventory"),
    )


# ----------------------------------------------------------------------
# HealthGateSpec / HealthGateResult
# ----------------------------------------------------------------------

def health_gate_spec_from_dict(data: object) -> HealthGateSpec:
    mapping = _require_mapping(data, "gate spec")
    _require_keys(
        mapping, ("label", "subject_kind", "subject_ref", "metric", "max_value"),
        "gate spec",
    )
    return HealthGateSpec(
        label=_require_str(mapping, "label", "gate spec"),
        subject_kind=_require_str(mapping, "subject_kind", "gate spec"),
        subject_ref=_require_str(mapping, "subject_ref", "gate spec"),
        metric=_require_str(mapping, "metric", "gate spec"),
        max_value=_require_int(mapping, "max_value", "gate spec"),
    )


def health_gate_result_from_dict(data: object) -> HealthGateResult:
    mapping = _require_mapping(data, "gate result")
    _require_keys(
        mapping,
        ("label", "verdict", "observed_value", "observation_id",
         "observed_at", "freshness_until", "detail"),
        "gate result",
    )
    verdict = _require_str(mapping, "verdict", "gate result")
    if verdict not in GateVerdict.ALL_VALUES:
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "gate result verdict %r is not frozen" % (verdict,),
        )
    observed = mapping["observed_value"]
    if observed is not None and (isinstance(observed, bool) or not isinstance(observed, int)):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "gate result observed_value must be an int or null",
        )
    return HealthGateResult(
        label=_require_str(mapping, "label", "gate result"),
        verdict=verdict,
        observed_value=observed,
        observation_id=_require_str(mapping, "observation_id", "gate result"),
        observed_at=_require_str(mapping, "observed_at", "gate result"),
        freshness_until=_require_str(mapping, "freshness_until", "gate result"),
        detail=_require_str(mapping, "detail", "gate result"),
    )


# ----------------------------------------------------------------------
# MigrationDescriptor
# ----------------------------------------------------------------------

def migration_descriptor_from_dict(data: object) -> MigrationDescriptor:
    mapping = _require_mapping(data, "migration")
    _require_keys(
        mapping,
        ("migration_id", "schema_id", "from_version", "to_version",
         "reversible", "breaking"),
        "migration",
    )
    return MigrationDescriptor(
        schema_id=_require_str(mapping, "schema_id", "migration"),
        from_version=_require_str(mapping, "from_version", "migration"),
        to_version=_require_str(mapping, "to_version", "migration"),
        reversible=_require_bool(mapping, "reversible", "migration"),
        breaking=_require_bool(mapping, "breaking", "migration"),
        migration_id=_require_str(mapping, "migration_id", "migration"),
    )


# ----------------------------------------------------------------------
# UpgradePlan
# ----------------------------------------------------------------------

def upgrade_plan_from_dict(data: object) -> UpgradePlan:
    mapping = _require_mapping(data, "plan")
    _require_keys(
        mapping,
        ("plan_id", "node_id", "from_version", "to_version",
         "target_protocol_profile", "target_schema_versions",
         "minimum_version_floor", "canary_gate", "rollout_gate", "final_gate"),
        "plan",
    )
    return UpgradePlan(
        node_id=_require_str(mapping, "node_id", "plan"),
        from_version=software_version_from_dict(mapping["from_version"]),
        to_version=software_version_from_dict(mapping["to_version"]),
        target_protocol_profile=protocol_profile_from_dict(
            mapping["target_protocol_profile"]
        ),
        target_schema_versions=_require_pairs(
            mapping["target_schema_versions"], "plan target_schema_versions"
        ),
        minimum_version_floor=software_version_from_dict(
            mapping["minimum_version_floor"]
        ),
        canary_gate=health_gate_spec_from_dict(mapping["canary_gate"]),
        rollout_gate=health_gate_spec_from_dict(mapping["rollout_gate"]),
        final_gate=health_gate_spec_from_dict(mapping["final_gate"]),
        plan_id=_require_str(mapping, "plan_id", "plan"),
    )


# ----------------------------------------------------------------------
# UpgradeEvent
# ----------------------------------------------------------------------

def upgrade_event_from_dict(data: object) -> UpgradeEvent:
    mapping = _require_mapping(data, "event")
    _require_keys(
        mapping, ("event_id", "kind", "plan_id", "node_id", "stage", "at", "detail"),
        "event",
    )
    return UpgradeEvent(
        kind=_require_str(mapping, "kind", "event"),
        plan_id=_require_str(mapping, "plan_id", "event"),
        node_id=_require_str(mapping, "node_id", "event"),
        stage=_require_str(mapping, "stage", "event"),
        at=_require_str(mapping, "at", "event"),
        detail=_require_str(mapping, "detail", "event"),
        event_id=_require_str(mapping, "event_id", "event"),
    )
