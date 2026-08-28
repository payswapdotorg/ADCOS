"""WORK-032 conformance suite -- deterministic subject doubles.

These are IN-VECTOR subject doubles: components placed *inside* a
vector's scenario so the authority's handling of hostile behavior is
itself the conformance question (failure isolation, contract-shape
enforcement, budget exhaustion, exposure filtering, reported-vs-computed
health).

They subclass ONLY the sanctioned SDK extension points
(:class:`adapters.contract.AdapterContract`); no authority class is
ever subclassed or shadowed (the no-second-authority rule).  The
sabotaged *candidate worlds* used for harness discrimination live in
tools/conformance_selftest.py, not here -- the shipped package contains
no candidate that masquerades as a conforming implementation.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from adapters.contract import AdapterContract, AdapterContext
from adapters.model import HealthState, LinkMetricName

__all__ = [
    "ReferenceAdapter",
    "ThrowingAdapter",
    "MisshapenObserveAdapter",
    "BudgetBurningAdapter",
    "InflatingAdapter",
    "LyingHealthAdapter",
]

#: The single known capability id used by the reference fixture adapter
#: (a frozen registry entry, see spec/schemas/registries/capability-registry.json).
REFERENCE_CAPABILITY = "capability.core.store-and-forward"


class ReferenceAdapter(AdapterContract):
    """A healthy, deterministic, contract-conforming reference adapter.

    This is the default subject implementation registered into the real
    WORK-016 runtime by the fixture world.  It is a test double of an
    *access technology implementation* (the extension point the SDK is
    designed for), not of any ADCOS authority.
    """

    def __init__(self, capabilities: Tuple[str, ...] = (
            REFERENCE_CAPABILITY,)) -> None:
        self._capabilities = tuple(capabilities)
        self.allocation_seq = 0
        self.bearer_seq = 0

    # -- the nine frozen section-10.1 operations ---------------------------

    def open(self, context: AdapterContext) -> None:
        context.charge()

    def capabilities(self) -> Any:
        context = None  # no context on this operation (frozen contract)
        del context
        return list(self._capabilities)

    def observe(self, context: AdapterContext) -> Any:
        context.charge()
        return {
            LinkMetricName.LINK_UP: 1,
            LinkMetricName.RX_BYTES_TOTAL: 42_000,
            LinkMetricName.TX_BYTES_TOTAL: 17_000,
            LinkMetricName.RX_ERROR_COUNT: 0,
            LinkMetricName.TX_ERROR_COUNT: 1,
            LinkMetricName.RETRANSMIT_COUNT: 2,
        }

    def allocate(self, context: AdapterContext, *, kind: str,
                 quantity_base: int, purpose: str) -> str:
        context.charge()
        self.allocation_seq += 1
        return "tech:allocation:%06d" % self.allocation_seq

    def release(self, context: AdapterContext, technology_ref: str) -> None:
        context.charge()

    def bind_session(self, context: AdapterContext, *, session_id: str,
                     requirements: Optional[Mapping[str, Any]]) -> str:
        context.charge()
        self.bearer_seq += 1
        return "tech:bearer:%06d" % self.bearer_seq

    def unbind_session(self, context: AdapterContext, bearer_ref: str) -> None:
        context.charge()

    def health(self) -> str:
        return HealthState.HEALTHY

    def close(self, context: AdapterContext) -> None:
        context.charge()


class ThrowingAdapter(ReferenceAdapter):
    """Raises a chosen exception type on a chosen operation."""

    def __init__(self, operation: str, exc: BaseException) -> None:
        super().__init__()
        self._operation = operation
        self._exc = exc

    def _maybe_raise(self, operation: str) -> None:
        if operation == self._operation:
            raise self._exc

    def allocate(self, context: AdapterContext, *, kind: str,
                 quantity_base: int, purpose: str) -> str:
        self._maybe_raise("allocate")
        return super().allocate(
            context, kind=kind, quantity_base=quantity_base, purpose=purpose
        )


class MisshapenObserveAdapter(ReferenceAdapter):
    """Returns a contract-violating shape from ``observe`` (float values)."""

    def observe(self, context: AdapterContext) -> Any:
        context.charge()
        return {LinkMetricName.RX_BYTES_TOTAL: 1.5}


class BudgetBurningAdapter(ReferenceAdapter):
    """Burns the entire step budget inside ``allocate`` (the hang model).

    The sandbox must convert unbounded work into a typed
    budget-exhausted failure value -- never a wall-clock timeout.
    """

    def allocate(self, context: AdapterContext, *, kind: str,
                 quantity_base: int, purpose: str) -> str:
        while True:
            context.charge()
        return "tech:allocation:never-reached"  # noqa: unreachable


class InflatingAdapter(ReferenceAdapter):
    """Reports MORE capability ids than the descriptor declares.

    The runtime's exposure surface must remain a subset of the declared
    descriptor capabilities (capability inflation is contained by the
    authority, not trusted from the implementation).
    """

    INFLATED_EXTRA = "capability.core.session-hijack-fixture"

    def capabilities(self) -> Any:
        return list(self._capabilities) + [self.INFLATED_EXTRA]


class LyingHealthAdapter(ReferenceAdapter):
    """Always reports HEALTHY regardless of accumulated failures.

    Reported health is never authoritative: the runtime computes
    effective health from the frozen supervision thresholds.
    """

    def health(self) -> str:
        return HealthState.HEALTHY
