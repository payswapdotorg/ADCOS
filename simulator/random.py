"""The documented deterministic PRNG stream (WORK-031).

Where simulation semantics genuinely require stochastic variation, the
variation is generated ONLY from an explicit scenario seed through
this counter-based stream:

    digest_i = sha256("<seed>|<label>|<counter_i>")     (UTF-8)
    uint(bound) = rejection sampling over the first 8 bytes of
                  digest_i interpreted little-endian

The construction is fully documented, version-independent (no reliance
on any language-level PRNG), and byte-identical across processes and
machines.  ``digest()`` fingerprints the consumed stream so tests can
pin both seed and stream position.

The stream is SIMULATOR STATE ONLY: it influences simulated metric
variation (degradation severity, telemetry confidence jitter,
exhaustion magnitude).  It never influences any authority's internal
semantics -- authorities receive the produced values as ordinary DATA.
"""

from __future__ import annotations

import hashlib
from typing import Any, Sequence

from .model import SimulatorError, SimulatorReasonCode

_LABEL_OK = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
)


class DeterministicStream:
    """A counter-based sha256 PRNG stream bound to an explicit seed."""

    def __init__(self, seed: int, label: str = "") -> None:
        if not isinstance(seed, int) or seed < 0:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "seed must be a non-negative integer",
            )
        if not isinstance(label, str) or not set(label) <= _LABEL_OK:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "label %r must be ASCII letters/digits/-/_/. only" % (label,),
            )
        self._seed = seed
        self._label = label
        self._counter = 0

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def label(self) -> str:
        return self._label

    @property
    def consumed(self) -> int:
        """How many stream words have been consumed (the stream position)."""
        return self._counter

    def _next_bytes(self) -> bytes:
        material = ("%d|%s|%d" % (self._seed, self._label, self._counter)).encode(
            "utf-8"
        )
        self._counter += 1
        return hashlib.sha256(material).digest()

    def uint(self, bound: int) -> int:
        """Uniform integer in ``[0, bound)`` via rejection sampling."""
        if not isinstance(bound, int) or bound < 1:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "bound must be a positive integer",
            )
        if bound & (bound - 1) == 0:  # power of two: no rejection needed
            raw = int.from_bytes(self._next_bytes()[:8], "little")
            return raw & (bound - 1)
        limit = (1 << 64) - ((1 << 64) % bound)
        while True:
            raw = int.from_bytes(self._next_bytes()[:8], "little")
            if raw < limit:
                return raw % bound

    def choice(self, items: Sequence[Any]) -> Any:
        """Deterministic choice among ``items`` (index = uint(len))."""
        if not items:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "choice over an empty sequence",
            )
        return items[self.uint(len(items))]

    def digest(self) -> str:
        """Fingerprint of the stream identity AND position.

        Two streams with the same seed/label that consumed the same
        number of words produce identical digests; any divergence in
        seed, label, or consumption order changes it.
        """
        material = ("%d|%s|%d" % (self._seed, self._label, self._counter)).encode(
            "utf-8"
        )
        return "sha256:" + hashlib.sha256(material).hexdigest()
