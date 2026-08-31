"""WORK-042 platform-event ingestion boundary.

The isolated seam through which authoritative platform observations
become ordered, content-addressed :class:`PlatformEvent` values --
and NOTHING else:

    platform authority (the OS / host platform, read through the
    ACCEPTED existing seams)
            |
            |  push: a platform change callback reports one
            |  observation (EVENT-FIRST -- the normative primary
            |  path of ACR-006 section 1)
            v
    PlatformEventBoundary (this module: typed validation,
    provenance preservation, content-derived identity)
            |
            v
    PlatformEvent  (DATA + evidence: kind, source, platform_ref,
                    payload, observed_at, event_id)

The boundary is deliberately PUSH-shaped: hosts deliver one
observation at a time with its observation instant and provenance
label.  A polling FALLBACK (:func:`events_from_sources`) exists --
ACR-006 section 1 explicitly permits polling "as a fallback" -- and
performs CHANGE DETECTION against a reconciled state, so even the
fallback emits events only for actual changes (never a polling-only
semantic).

Authority discipline:

- observation is EVIDENCE, never protocol truth: nothing here
  converts an observation into session, route, policy, or transport
  state;
- observations are kept distinct from DECISIONS: the boundary
  produces observation events only (recovery outcomes such as
  session-loss records live in the journal module, clearly
  discriminated by record kind);
- the boundary composes the ACCEPTED seams (WORK-033
  ``InterfaceSource``, WORK-035 ``MobilePlatformSource``) and
  creates no competing discovery or platform authority;
- technology-neutral at the ADCOS boundary: no vendor/platform API
  is imported; the payload models are the accepted
  technology-neutral snapshots.

Fail-closed discipline:

- a source that raises surfaces as a typed
  ``OBSERVATION_SOURCE_FAILED`` error (an OS exception never crosses
  the composition boundary);
- malformed observations (not genuine snapshots, wrong family for
  the ingest method, non-mapping payloads) are rejected with typed
  ``OBSERVATION_INVALID`` / ``EVENT_INVALID`` errors;
- every event is content-identity-bound at construction (tampered
  ids rejected before anything is journaled).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes

from agent.interfaces import InterfaceSource
from agent.model import InterfaceSnapshot

from mobile.model import PlatformSnapshot
from mobile.platform import MobilePlatformSource

from .errors import PlatformError, PlatformReasonCode
from .model import (
    DEFAULT_INTERFACE_SOURCE,
    DEFAULT_PLATFORM_SOURCE,
    PLATFORM_STATE_REF,
    EventKind,
    PlatformEvent,
    platform_event_content,
)
from .state import ObservationRecord, ReconciledState


def _require_instant(observed_at: object) -> str:
    if not isinstance(observed_at, str) or not observed_at:
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "observed_at must be an RFC 3339 UTC instant string "
            "(the host-supplied observation instant, never a wall clock)",
        )
    return observed_at


def _require_source(source: object) -> str:
    if not isinstance(source, str) or not source:
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "source must be a non-empty provenance label",
        )
    return source


def _require_platform_snapshot(snapshot: object) -> PlatformSnapshot:
    if not isinstance(snapshot, PlatformSnapshot):
        raise PlatformError(
            PlatformReasonCode.OBSERVATION_INVALID,
            "platform-state observation requires a genuine "
            "PlatformSnapshot (the accepted WORK-035 model)",
        )
    return snapshot


def _require_interface_snapshot(snapshot: object) -> InterfaceSnapshot:
    if not isinstance(snapshot, InterfaceSnapshot):
        raise PlatformError(
            PlatformReasonCode.OBSERVATION_INVALID,
            "interface observation requires a genuine "
            "InterfaceSnapshot (the accepted WORK-033 model)",
        )
    return snapshot


# ---------------------------------------------------------------------------
# The event-first primary path (push; one observation at a time)
# ---------------------------------------------------------------------------


def interface_event(
    snapshot: InterfaceSnapshot,
    *,
    observed_at: str,
    source: str = DEFAULT_INTERFACE_SOURCE,
) -> PlatformEvent:
    """One host-pushed interface observation as a PlatformEvent."""
    _require_interface_snapshot(snapshot)
    _require_instant(observed_at)
    _require_source(source)
    return PlatformEvent(
        event_id="",
        kind=EventKind.INTERFACE_OBSERVATION,
        source=source,
        platform_ref=snapshot.name,
        payload=snapshot.to_dict(),
        observed_at=observed_at,
    )


def interface_removal_event(
    interface_name: str,
    *,
    observed_at: str,
    source: str = DEFAULT_INTERFACE_SOURCE,
) -> PlatformEvent:
    """One host-pushed interface-removal notification.

    An interface disappearing from the platform is an OBSERVATION
    (the platform's own removal callback), so the disappearance is
    journaled like every other change notification -- never an
    ambient side effect inferred from a missing poll result.
    """
    if not isinstance(interface_name, str) or not interface_name:
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "interface_name must be a non-empty string",
        )
    _require_instant(observed_at)
    _require_source(source)
    return PlatformEvent(
        event_id="",
        kind=EventKind.INTERFACE_REMOVAL,
        source=source,
        platform_ref=interface_name,
        payload={"interface_name": interface_name},
        observed_at=observed_at,
    )


def platform_state_event(
    snapshot: PlatformSnapshot,
    *,
    observed_at: str,
    source: str = DEFAULT_PLATFORM_SOURCE,
) -> PlatformEvent:
    """One host-pushed OS platform-state observation as a
    PlatformEvent."""
    _require_platform_snapshot(snapshot)
    _require_instant(observed_at)
    _require_source(source)
    return PlatformEvent(
        event_id="",
        kind=EventKind.PLATFORM_STATE_OBSERVATION,
        source=source,
        platform_ref=PLATFORM_STATE_REF,
        payload=snapshot.to_dict(),
        observed_at=observed_at,
    )


def event_from_redelivery(data: object) -> PlatformEvent:
    """Rebuild one event from serialized DATA (replay/redelivery).

    Round-trips through the same tamper-evident constructor: a
    hand-edited ``event_id``, a mutated payload, or a mismatched
    family all fail closed here, BEFORE any journal append.
    """
    return PlatformEvent.from_dict(data)


# ---------------------------------------------------------------------------
# The polling fallback (change-detected; never polling-ONLY)
# ---------------------------------------------------------------------------


def _payload_bytes(payload: Dict[str, Any]) -> bytes:
    return canonical_json_bytes(payload)


def events_from_sources(
    *,
    state: ReconciledState,
    interface_source: Optional[InterfaceSource] = None,
    platform_source: Optional[MobilePlatformSource] = None,
    observed_at: str,
    interface_source_label: str = DEFAULT_INTERFACE_SOURCE,
    platform_source_label: str = DEFAULT_PLATFORM_SOURCE,
) -> Tuple[PlatformEvent, ...]:
    """The polling FALLBACK (ACR-006 section 1).

    Reads the CURRENT observation sets through the accepted seams
    and emits change events ONLY where the fresh observation differs
    from the reconciled state:

    - a fresh interface observation differs from the reconciled
      record (payload change) -> ``interface-observation`` event;
    - a fresh interface is absent from the reconciled state ->
      ``interface-observation`` event (new reference);
    - a reconciled interface is ABSENT from the fresh set -> an
      ``interface-removal`` event (the disappearance is journaled);
    - the fresh platform-state snapshot differs from the reconciled
      record -> one ``platform-state-observation`` event.

    The returned tuple is sorted by (kind, platform_ref) so the
    emission order is deterministic.  Sources are optional per
    family; a source that raises is isolated into the typed
    ``OBSERVATION_SOURCE_FAILED`` error (fail closed -- an
    ambiguous partial sweep is never silently emitted).
    """
    _require_instant(observed_at)
    _require_source(interface_source_label)
    _require_source(platform_source_label)
    if not isinstance(state, ReconciledState):
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "state must be a ReconciledState (the change-detection "
            "baseline)",
        )
    events: List[PlatformEvent] = []

    if interface_source is not None:
        if not isinstance(interface_source, InterfaceSource):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "interface_source must be an InterfaceSource (the "
                "accepted WORK-033 seam)",
            )
        try:
            snapshots = interface_source.discover()
        except Exception as error:  # isolation: typed, never OS-crossing
            raise PlatformError(
                PlatformReasonCode.OBSERVATION_SOURCE_FAILED,
                "interface discovery failed (%s)" % type(error).__name__,
            ) from error
        if not isinstance(snapshots, tuple):
            raise PlatformError(
                PlatformReasonCode.OBSERVATION_SOURCE_FAILED,
                "interface source returned a non-tuple result (%s)"
                % type(snapshots).__name__,
            )
        fresh: Dict[str, InterfaceSnapshot] = {}
        for snapshot in snapshots:
            if not isinstance(snapshot, InterfaceSnapshot):
                raise PlatformError(
                    PlatformReasonCode.OBSERVATION_INVALID,
                    "interface source returned a non-InterfaceSnapshot "
                    "value (%s)" % type(snapshot).__name__,
                )
            if snapshot.name in fresh:
                raise PlatformError(
                    PlatformReasonCode.OBSERVATION_INVALID,
                    "ambiguous observation set: interface %r reported "
                    "more than once in one discovery cycle (fail closed)"
                    % snapshot.name,
                )
            fresh[snapshot.name] = snapshot
        for name in sorted(fresh):
            snapshot = fresh[name]
            record = state.interface_map().get(name)
            changed = (
                record is None
                or record.kind != EventKind.INTERFACE_OBSERVATION
                or _payload_bytes(record.payload)
                != _payload_bytes(snapshot.to_dict())
            )
            if changed:
                events.append(
                    interface_event(
                        snapshot,
                        observed_at=observed_at,
                        source=interface_source_label,
                    )
                )
        for name in sorted(state.interface_map()):
            if name not in fresh:
                events.append(
                    interface_removal_event(
                        name,
                        observed_at=observed_at,
                        source=interface_source_label,
                    )
                )

    if platform_source is not None:
        if not isinstance(platform_source, MobilePlatformSource):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "platform_source must be a MobilePlatformSource (the "
                "accepted WORK-035 seam)",
            )
        try:
            snapshot = platform_source.read()
        except Exception as error:  # isolation: typed, never OS-crossing
            raise PlatformError(
                PlatformReasonCode.OBSERVATION_SOURCE_FAILED,
                "platform-state read failed (%s)" % type(error).__name__,
            ) from error
        _require_platform_snapshot(snapshot)
        record = state.platform_record
        changed = (
            record is None
            or record.kind != EventKind.PLATFORM_STATE_OBSERVATION
            or _payload_bytes(record.payload)
            != _payload_bytes(snapshot.to_dict())
        )
        if changed:
            events.append(
                platform_state_event(
                    snapshot,
                    observed_at=observed_at,
                    source=platform_source_label,
                )
            )

    return tuple(
        sorted(events, key=lambda item: (item.kind, item.platform_ref))
    )


__all__ = [
    "event_from_redelivery",
    "events_from_sources",
    "interface_event",
    "interface_removal_event",
    "platform_state_event",
]
