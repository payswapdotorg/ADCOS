"""WORK-033 agent serialization helpers.

Canonical, fail-closed round-trips for the agent's public DATA:
interface snapshots and agent events (configuration and run results
serialize through their own ``to_dict`` methods).  All bytes flow
through the WORK-003 canonical JSON machinery.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from protocol import CanonicalizationError, canonical_json_bytes

from .errors import AgentError, AgentReasonCode
from .model import AgentEvent, InterfaceSnapshot


def interface_snapshot_from_mapping(data: object) -> InterfaceSnapshot:
    try:
        return InterfaceSnapshot.from_dict(data)  # type: ignore[arg-type]
    except AgentError as error:
        raise AgentError(
            AgentReasonCode.SERIALIZATION_INVALID,
            "interface snapshot round-trip failed: %s" % error.detail,
        ) from error


def agent_event_from_mapping(data: object) -> AgentEvent:
    if not isinstance(data, Mapping):
        raise AgentError(
            AgentReasonCode.SERIALIZATION_INVALID, "agent event must be a mapping"
        )
    try:
        return AgentEvent.from_dict(data)
    except AgentError as error:
        raise AgentError(
            AgentReasonCode.SERIALIZATION_INVALID,
            "agent event round-trip failed: %s" % error.detail,
        ) from error


def agent_events_from_mapping(data: object) -> Tuple[AgentEvent, ...]:
    if not isinstance(data, list):
        raise AgentError(
            AgentReasonCode.SERIALIZATION_INVALID, "event list must be a list"
        )
    return tuple(agent_event_from_mapping(item) for item in data)


def snapshot_canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    try:
        return canonical_json_bytes(dict(payload))
    except CanonicalizationError as error:
        raise AgentError(
            AgentReasonCode.SERIALIZATION_INVALID,
            "payload is not canonicalizable: %s" % error,
        ) from error


def event_list_digest(events: List[AgentEvent]) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(
        canonical_json_bytes([event.to_dict() for event in events])
    ).hexdigest()
