"""ADCOS access-technology capability envelopes (M020 — Access
Technology Capability Envelope, R9-CORE-001, DEC-0120).

The typed, deterministic capability-envelope declarations per
technology class of the R9 charter M020 scope: declared deterministic
ranges over the four capability dimensions — **bandwidth**, **latency**,
**jitter**, **availability windows** — canonical-JSON serializable with
content-derived identities (the LOCK-106 discipline: identities are
derived from the canonical bytes of the declaration's content, never
from the wall clock, never from randomness; tamper-evident at
reconstruction).

The envelope is DECLARED DATA about a technology class — a typed
declaration of what the technology can deterministically commit to.
It is NOT:

* a contract authority (LOCK-101/LOCK-117: ``ConnectivityContract`` in
  the accepted ``contracts/`` domain stays the sole authority for
  acquired connectivity; an envelope never carries constraint
  material, never names a contract, never becomes a second authority);
* a topology claim (LOCK-105: no provider infrastructure facts — the
  availability windows are the technology class's OWN declared
  operating intervals, never a global-availability assertion);
* an adapter mechanism (LOCK-110: the mechanism surface is the
  accepted ``adapters/capability.py`` seam — the envelope rides as
  declaration data AROUND that boundary, consumed by the registration
  surface in :mod:`accesstech.registry`);
* a secret carrier (LOCK-119: secret-shaped values are rejected at
  construction time).

Technology identity: the ``technology_class`` is validated through the
ACCEPTED open-world classifier (``adapters.validation.\
validate_access_technology_id``) — KNOWN ids register verbatim and
future UNKNOWN_BUT_WELL_FORMED ids enter as data (a technology the
architecture never named declares the same envelope grammar; the
extension proof of the registration surface).  Malformed ids are
rejected fail-closed with the accepted seam's own typed rejection.

Determinism (LOCK-119): integer base units only (bps / milliseconds —
the canonical JSON subset rejects floats), injected RFC 3339 UTC
instants only (validated through ``protocol.temporal``), no wall clock,
no randomness, no network, no secrets; sorted/normalized availability
windows; canonical-JSON round-trips byte-identical.

Fail-closed validation (every malformed class a TYPED rejection,
never a warning):

* **empty ranges** — a bandwidth dimension promising nothing, a
  latency/jitter dimension declaring a zero-width unphysical range, an
  availability-window sequence with no windows
  (:data:`AccessTechReason.ENVELOPE_DEGENERATE`);
* **inverted bounds** — floor above ceiling, latency/jitter minimum
  above maximum, a window ending at or before its start
  (:data:`AccessTechReason.ENVELOPE_INCONSISTENT`);
* **contradictory content** — disordered or overlapping availability
  windows, a reconstructed identity that does not match the derived
  content (:data:`AccessTechReason.ENVELOPE_INCONSISTENT` /
  :data:`AccessTechReason.IDENTITY_MISMATCH`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from adapters.validation import validate_access_technology_id

from .errors import AccessTechError, AccessTechReason

__all__ = [
    "BpsRange",
    "LatencyMilliRange",
    "JitterMilliRange",
    "AvailabilityWindow",
    "AvailabilityWindows",
    "CapabilityEnvelope",
    "derive_envelope_id",
    "envelope_from_mapping",
]

#: Identity namespace (WORK-003 canonical-JSON SHA-256 convention).
_ENVELOPE_NAMESPACE = "adcos.accesstech.envelope"

#: Maximum number of declared availability windows in one envelope
#: (fail-closed bound; declared windows are deterministic intervals,
#: never an unbounded stream).
MAX_AVAILABILITY_WINDOWS = 32

#: Maximum technology-class id length (the accepted seam's grammar
#: bound; kept local so the rejection stays typed on this vocabulary).
_MAX_TECHNOLOGY_CLASS_LEN = 128


# ----------------------------------------------------------------------
# Internal helpers (the consumed conventions, by reference)
# ----------------------------------------------------------------------


def _require_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s must be an integer (canonical base units; floats are "
            "outside the canonical JSON subset)" % label,
        )
    return value


def _require_instant(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s must be an RFC 3339 UTC instant string" % label,
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s is not an injected RFC 3339 UTC instant: %s" % (label, error),
        ) from None
    return value


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_id(namespace: str, document: Mapping[str, Any], label: str) -> str:
    payload = dict(document)
    payload["namespace"] = namespace
    return "sha256:" + hashlib.sha256(_canonical_bytes(payload, label)).hexdigest()


# ----------------------------------------------------------------------
# The capability dimensions (typed deterministic ranges)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class BpsRange:
    """The bandwidth dimension: a declared deterministic range in
    integer bits-per-second base units (floor <= achievable <=
    ceiling).

    Fail-closed: both bounds are integers; the ceiling promises at
    least one bit per second (an empty bandwidth range is degenerate);
    the floor declares at least one bit per second (a zero floor
    promises nothing — best-effort semantics are a declared low floor,
    never a zero floor); the floor never exceeds the ceiling (inverted
    bounds).
    """

    floor_bps: int
    ceiling_bps: int

    def __post_init__(self) -> None:
        floor = _require_int(self.floor_bps, "bandwidth.floor_bps")
        ceiling = _require_int(self.ceiling_bps, "bandwidth.ceiling_bps")
        object.__setattr__(self, "floor_bps", floor)
        object.__setattr__(self, "ceiling_bps", ceiling)
        if ceiling < 1:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_DEGENERATE,
                "bandwidth ceiling %d bps is an empty range (a declared "
                "bandwidth dimension must promise at least 1 bps)" % ceiling,
            )
        if floor < 1:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_DEGENERATE,
                "bandwidth floor %d bps promises nothing (a declared floor "
                "must be at least 1 bps; best-effort semantics are a "
                "declared low floor, never a zero floor)" % floor,
            )
        if floor > ceiling:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_INCONSISTENT,
                "bandwidth range is inverted: floor %d bps > ceiling %d bps"
                % (floor, ceiling),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {"floor_bps": self.floor_bps, "ceiling_bps": self.ceiling_bps}


@dataclass(frozen=True)
class LatencyMilliRange:
    """The latency dimension: a declared deterministic range in integer
    milliseconds (the achievable one-way latency stays within
    [min_ms, max_ms]).

    Fail-closed: integer bounds; the maximum is at least 1 ms (a
    zero-latency range is unphysical for any real access technology —
    degenerate); the minimum never exceeds the maximum (inverted).
    """

    min_ms: int
    max_ms: int

    def __post_init__(self) -> None:
        low = _require_int(self.min_ms, "latency.min_ms")
        high = _require_int(self.max_ms, "latency.max_ms")
        object.__setattr__(self, "min_ms", low)
        object.__setattr__(self, "max_ms", high)
        if high < 1:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_DEGENERATE,
                "latency maximum %d ms is an unphysical zero-width range "
                "(a declared latency dimension must admit at least 1 ms)" % high,
            )
        if low > high:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_INCONSISTENT,
                "latency range is inverted: min %d ms > max %d ms"
                % (low, high),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {"min_ms": self.min_ms, "max_ms": self.max_ms}


@dataclass(frozen=True)
class JitterMilliRange:
    """The jitter dimension: a declared deterministic range in integer
    milliseconds (the packet-delay variation stays within
    [min_ms, max_ms]).

    Fail-closed: integer bounds; the maximum is at least 1 ms (a
    perfectly-constant zero-jitter declaration is unphysical for a
    real access technology — degenerate); the minimum never exceeds
    the maximum (inverted).
    """

    min_ms: int
    max_ms: int

    def __post_init__(self) -> None:
        low = _require_int(self.min_ms, "jitter.min_ms")
        high = _require_int(self.max_ms, "jitter.max_ms")
        object.__setattr__(self, "min_ms", low)
        object.__setattr__(self, "max_ms", high)
        if high < 1:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_DEGENERATE,
                "jitter maximum %d ms is an unphysical zero-width range (a "
                "declared jitter dimension must admit at least 1 ms)" % high,
            )
        if low > high:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_INCONSISTENT,
                "jitter range is inverted: min %d ms > max %d ms" % (low, high),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {"min_ms": self.min_ms, "max_ms": self.max_ms}


@dataclass(frozen=True)
class AvailabilityWindow:
    """One declared availability interval: the technology class's own
    deterministic operating window, [start, end) over injected RFC 3339
    UTC instants (LOCK-105: a technology-local declaration, never a
    global-availability or topology assertion).

    Fail-closed: both instants parse (typed rejection otherwise); the
    window is strictly non-empty (end > start — an inverted or
    zero-width window is inconsistent).
    """

    start: str
    end: str

    def __post_init__(self) -> None:
        start = _require_instant(self.start, "availability window start")
        end = _require_instant(self.end, "availability window end")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if parse_instant(end) <= parse_instant(start):
            raise AccessTechError(
                AccessTechReason.ENVELOPE_INCONSISTENT,
                "availability window is inverted or empty: end %s <= start %s"
                % (end, start),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {"start": self.start, "end": self.end}


@dataclass(frozen=True)
class AvailabilityWindows:
    """The availability-windows dimension: the declared deterministic
    sequence of the technology class's operating intervals.

    Fail-closed: at least one window (an empty availability dimension
    is a degenerate envelope — the technology declares when it can
    operate); at most :data:`MAX_AVAILABILITY_WINDOWS` windows; the
    windows are strictly ordered and pairwise non-overlapping
    (disordered or overlapping windows are contradictory content —
    deterministic declaration means exactly one canonical order).
    """

    windows: Tuple[AvailabilityWindow, ...]

    def __post_init__(self) -> None:
        if isinstance(self.windows, (str, bytes)) or not isinstance(
            self.windows, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "availability windows must be a sequence of "
                "AvailabilityWindow records",
            )
        normalized: List[AvailabilityWindow] = []
        for index, item in enumerate(self.windows):
            if not isinstance(item, AvailabilityWindow):
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "availability window %d must be an AvailabilityWindow "
                    "record (got %s)" % (index, type(item).__name__),
                )
            normalized.append(item)
        windows = tuple(normalized)
        if not windows:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_DEGENERATE,
                "the availability-windows dimension is empty (a declared "
                "envelope must carry at least one operating window)",
            )
        if len(windows) > MAX_AVAILABILITY_WINDOWS:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "at most %d availability windows are declarable (found %d)"
                % (MAX_AVAILABILITY_WINDOWS, len(windows)),
            )
        previous: AvailabilityWindow = windows[0]
        for window in windows[1:]:
            if parse_instant(window.start) < parse_instant(previous.start):
                raise AccessTechError(
                    AccessTechReason.ENVELOPE_INCONSISTENT,
                    "availability windows are disordered: %s starts before "
                    "%s (deterministic declaration requires ascending order)"
                    % (window.start, previous.start),
                )
            if parse_instant(window.start) < parse_instant(previous.end):
                raise AccessTechError(
                    AccessTechReason.ENVELOPE_INCONSISTENT,
                    "availability windows overlap: %s starts before %s ends "
                    "(contradictory declared intervals)" % (window.start, previous.end),
                )
            previous = window
        object.__setattr__(self, "windows", windows)

    def to_dict(self) -> Dict[str, Any]:
        return {"windows": [window.to_dict() for window in self.windows]}


# ----------------------------------------------------------------------
# The capability envelope
# ----------------------------------------------------------------------


def derive_envelope_id(
    technology_class: str,
    bandwidth: BpsRange,
    latency: LatencyMilliRange,
    jitter: JitterMilliRange,
    availability: AvailabilityWindows,
) -> str:
    """The content-derived envelope identity (LOCK-106 discipline:
    sha256 over the canonical JSON of the declaration's content; no
    wall clock, no randomness)."""
    document = {
        "kind": "adcos.accesstech.envelope",
        "technology_class": technology_class,
        "bandwidth": bandwidth.to_dict(),
        "latency": latency.to_dict(),
        "jitter": jitter.to_dict(),
        "availability": availability.to_dict(),
    }
    return _derive_id(_ENVELOPE_NAMESPACE, document, "the capability envelope")


@dataclass(frozen=True)
class CapabilityEnvelope:
    """The declared capability envelope of ONE technology class: typed
    deterministic ranges over the four capability dimensions, with a
    content-derived identity.

    ``technology_class`` is validated through the accepted open-world
    classifier (KNOWN or UNKNOWN_BUT_WELL_FORMED preserved verbatim;
    malformed ids rejected with the accepted seam's typed rejection —
    future access technologies enter as data, exactly as the R9 gate
    objective requires).  The envelope is declaration DATA around the
    accepted adapter boundary: never a contract authority (LOCK-101/
    LOCK-117), never a topology claim (LOCK-105), never a mechanism
    (LOCK-110 — the mechanism surface is the accepted
    ``adapters/capability.py`` seam the registration drives).
    """

    technology_class: str
    bandwidth: BpsRange
    latency: LatencyMilliRange
    jitter: JitterMilliRange
    availability: AvailabilityWindows
    envelope_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.technology_class, str):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "technology_class must be a string",
            )
        if len(self.technology_class) > _MAX_TECHNOLOGY_CLASS_LEN:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "technology_class exceeds %d characters"
                % _MAX_TECHNOLOGY_CLASS_LEN,
            )
        try:
            technology_class = validate_access_technology_id(self.technology_class)
        except Exception as error:  # the accepted seam's typed rejection
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "technology_class rejected by the accepted open-world "
                "classifier: %s" % (getattr(error, "detail", None) or error),
            ) from None
        object.__setattr__(self, "technology_class", technology_class)
        for label, value in (
            ("bandwidth", self.bandwidth),
            ("latency", self.latency),
            ("jitter", self.jitter),
            ("availability", self.availability),
        ):
            expected_type = {
                "bandwidth": BpsRange,
                "latency": LatencyMilliRange,
                "jitter": JitterMilliRange,
                "availability": AvailabilityWindows,
            }[label]
            if not isinstance(value, expected_type):
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "%s must be a typed %s record (got %s)"
                    % (label, expected_type.__name__, type(value).__name__),
                )
        derived = derive_envelope_id(
            self.technology_class,
            self.bandwidth,
            self.latency,
            self.jitter,
            self.availability,
        )
        if not isinstance(self.envelope_id, str) or not self.envelope_id:
            # construction path: derive (the identity IS the content)
            object.__setattr__(self, "envelope_id", derived)
        elif self.envelope_id != derived:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "envelope_id does not match the content-derived identity "
                "(tamper evidence): declared %s, derived %s"
                % (self.envelope_id, derived),
            )

    def content_dict(self) -> Dict[str, Any]:
        return {
            "technology_class": self.technology_class,
            "bandwidth": self.bandwidth.to_dict(),
            "latency": self.latency.to_dict(),
            "jitter": self.jitter.to_dict(),
            "availability": self.availability.to_dict(),
            "envelope_id": self.envelope_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content_dict()

    def to_canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.content_dict(), "the capability envelope")


def _range_from_mapping(
    data: Mapping[str, Any],
    label: str,
    record_class: Any,
    members: Tuple[str, ...],
) -> Any:
    if not isinstance(data, Mapping):
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "%s must be a mapping" % label,
        )
    values = []
    for member in members:
        if member not in data:
            raise AccessTechError(
                AccessTechReason.SERIALIZATION_INVALID,
                "%s lacks the %r member" % (label, member),
            )
        values.append(data[member])
    return record_class(*values)


def envelope_from_mapping(value: object) -> CapabilityEnvelope:
    """Reconstruct a :class:`CapabilityEnvelope` from its canonical
    mapping.

    Fail-closed on every grammar drift (typed SERIALIZATION_INVALID
    rejections), on degenerate/inverted/contradictory dimension
    content (the construction-time typed rejections fire identically
    at load), and on identity tampering (the content-derived id is
    recomputed and compared — LOCK-106 tamper evidence at
    reconstruction).
    """
    if not isinstance(value, Mapping):
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "the capability envelope must be a mapping",
        )
    data = dict(value)
    envelope_id = data.get("envelope_id")
    if not isinstance(envelope_id, str) or not envelope_id:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "the capability envelope lacks its content-derived envelope_id",
        )
    for member in ("technology_class", "bandwidth", "latency", "jitter", "availability"):
        if member not in data:
            raise AccessTechError(
                AccessTechReason.SERIALIZATION_INVALID,
                "the capability envelope lacks the %r member" % member,
            )
    bandwidth = _range_from_mapping(
        data["bandwidth"], "bandwidth", BpsRange, ("floor_bps", "ceiling_bps")
    )
    latency = _range_from_mapping(
        data["latency"], "latency", LatencyMilliRange, ("min_ms", "max_ms")
    )
    jitter = _range_from_mapping(
        data["jitter"], "jitter", JitterMilliRange, ("min_ms", "max_ms")
    )
    availability_data = data["availability"]
    if not isinstance(availability_data, Mapping) or "windows" not in availability_data:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "availability must be a mapping carrying 'windows'",
        )
    windows_raw = availability_data["windows"]
    if isinstance(windows_raw, (str, bytes)) or not isinstance(
        windows_raw, (tuple, list)
    ):
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "availability windows must be a sequence of window mappings",
        )
    windows = AvailabilityWindows(
        tuple(
            _range_from_mapping(window, "availability window", AvailabilityWindow,
                                ("start", "end"))
            for window in windows_raw
        )
    )
    return CapabilityEnvelope(
        technology_class=data["technology_class"],
        bandwidth=bandwidth,
        latency=latency,
        jitter=jitter,
        availability=windows,
        envelope_id=envelope_id,
    )
