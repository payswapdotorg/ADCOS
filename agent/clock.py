"""WORK-033 agent clock seam.

Every composed authority takes injected RFC 3339 UTC instants; the
agent's runtime loop is the ONE sanctioned place a real OS clock may be
read, and only through this seam.  ``SystemClock`` is the only
wall-clock site in the agent family (battery-audited); ``StepClock``
and ``FixedClock`` keep verification deterministic.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from .errors import AgentError, AgentReasonCode


def format_instant(moment: datetime) -> str:
    """RFC 3339 UTC text with second precision (WORK-003 style)."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AgentClock:
    """The injected time source of one agent runtime."""

    def now(self) -> str:
        raise NotImplementedError


class SystemClock(AgentClock):
    """The real wall clock (the sanctioned OS time site).

    Used by a live headless agent; never used by verification
    batteries, which inject deterministic clocks.
    """

    def now(self) -> str:
        return format_instant(datetime.now(timezone.utc))


class StepClock(AgentClock):
    """A deterministic clock advancing a fixed step per read.

    Reads are monotonic; the instant sequence depends only on the
    number of reads, so identical command sequences produce identical
    instant sequences (replay determinism).
    """

    def __init__(self, start_instant: str, step_seconds: int) -> None:
        try:
            base = datetime.strptime(start_instant, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError as error:
            raise AgentError(
                AgentReasonCode.INVALID_INPUT,
                "start_instant must be RFC 3339 UTC (YYYY-MM-DDTHH:MM:SSZ): %s" % error,
            ) from error
        if step_seconds <= 0:
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "step_seconds must be positive"
            )
        self._base = base
        self._step = timedelta(seconds=step_seconds)
        self._reads = 0

    def now(self) -> str:
        moment = self._base + self._step * self._reads
        self._reads += 1
        return format_instant(moment)


class FixedClock(AgentClock):
    """A constant clock (single-instant scenarios)."""

    def __init__(self, instant: str) -> None:
        try:
            datetime.strptime(instant, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as error:
            raise AgentError(
                AgentReasonCode.INVALID_INPUT,
                "instant must be RFC 3339 UTC (YYYY-MM-DDTHH:MM:SSZ): %s" % error,
            ) from error
        self._instant = instant

    def now(self) -> str:
        return self._instant


def parse_utc(instant: str) -> datetime:
    """Parse an RFC 3339 UTC instant (strict, second precision)."""
    try:
        return datetime.strptime(instant, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise AgentError(
            AgentReasonCode.INVALID_INPUT,
            "instant %r is not RFC 3339 UTC: %s" % (instant, error),
        ) from error


def add_seconds(instant: str, seconds: int) -> str:
    """Deterministic instant arithmetic (no wall clock involved)."""
    base = parse_utc(instant)
    return format_instant(base + timedelta(seconds=seconds))
