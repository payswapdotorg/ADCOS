"""Injected deterministic scenario time (WORK-031).

Scenario time is ALWAYS injected: a :class:`ScenarioClock` maps integer
ticks to RFC 3339 UTC instants from an explicit ``start_instant`` and
``tick_seconds``.  No wall clock is ever read anywhere in the simulator
family (the self-test enforces this structurally).

Determinism: ``instant_at`` is a pure function of the constructor
arguments and the tick; identical scenarios produce identical instant
sequences byte-for-byte.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from protocol.temporal import TemporalError, parse_instant

from .model import SimulatorError, SimulatorReasonCode


class ScenarioClock:
    """The injected deterministic scenario clock.

    Usage::

        clock = ScenarioClock("2026-06-01T00:00:00Z", tick_seconds=60)
        clock.instant_at(3)   # "2026-06-01T00:03:00Z"
    """

    def __init__(self, start_instant: str, tick_seconds: int) -> None:
        try:
            parsed = parse_instant(start_instant)
        except TemporalError as error:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "start_instant must be an RFC 3339 UTC instant: %s" % error,
            ) from error
        if not isinstance(tick_seconds, int) or tick_seconds < 1:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "tick_seconds must be an int >= 1",
            )
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "start_instant must carry a UTC (Z) offset",
            )
        self._start = parsed
        self._tick_seconds = tick_seconds

    @property
    def start_instant(self) -> str:
        return _format_instant(self._start)

    @property
    def tick_seconds(self) -> int:
        return self._tick_seconds

    def instant_at(self, tick: int) -> str:
        """The scenario instant for ``tick`` (pure, deterministic)."""
        if not isinstance(tick, int) or tick < 0:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "tick must be a non-negative integer",
            )
        return _format_instant(self._start + timedelta(seconds=tick * self._tick_seconds))

    def horizon_instant(self, horizon_ticks: int) -> str:
        """The freshness horizon used for scenario-issued claims."""
        return self.instant_at(horizon_ticks + 1)


def _format_instant(moment: datetime) -> str:
    """Format a UTC datetime in the canonical ADCOS RFC 3339 form."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
