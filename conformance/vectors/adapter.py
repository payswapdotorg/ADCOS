"""WORK-032 conformance vectors -- Adapter SDK / runtime (WORK-016).

Covers: adapter lifecycle, capability exposure filtering (inflation
containment), allocation/release discipline, session binding through
the read-only W012 verification, failure isolation (provider
exceptions become typed failure values, never propagating
exceptions), contract-shape enforcement, the deterministic step
budget hang model, supervision thresholds with reported-vs-computed
health, cleanup fail-closed behavior, and state-envelope recovery.
"""

from __future__ import annotations

from typing import Any, Callable, FrozenSet, Tuple

from conformance.doubles import (
    BudgetBurningAdapter,
    InflatingAdapter,
    LyingHealthAdapter,
    MisshapenObserveAdapter,
    ReferenceAdapter,
    ThrowingAdapter,
)
from conformance.model import ConformanceVector, ExpectedOutcome, ObservedOutcome
from conformance.world import EVEN_LATER, LATER, NOW, T0, ConformanceWorld

__all__ = ["vectors"]

_AREA = "adapter"
_AUTHORITY = "WORK-016"
_CONTRACT = "spec/architecture.md section 18 (adapter SDK) / WORK-016"

_KNOWN_CAP = "capability.core.store-and-forward"


def _vector(number: str, polarity: str, invariant: str,
            description: str, expected: ExpectedOutcome,
            execute: Callable[[ConformanceWorld], ObservedOutcome],
            tags: FrozenSet[str] = frozenset()) -> ConformanceVector:
    return ConformanceVector(
        vector_id="W032-CNF-ADP-%s" % number,
        area=_AREA,
        polarity=polarity,
        authority=_AUTHORITY,
        contract=_CONTRACT,
        invariant=invariant,
        description=description,
        expected=expected,
        execute=execute,
        tags=tags,
    )


def _outcome(result: Any) -> ObservedOutcome:
    failure = getattr(result, "failure", None)
    reason = getattr(result, "reason", None)
    if not result.ok:
        if failure is not None and getattr(failure, "reason", None):
            return ObservedOutcome(
                False, failure.reason, failure.detail
            )
        if reason:
            return ObservedOutcome(False, reason, result.detail)
    return ObservedOutcome(
        bool(result.ok), reason or ("ok" if result.ok else "failed"),
        result.detail if hasattr(result, "detail") else "",
    )


def vectors() -> Tuple[ConformanceVector, ...]:
    out = []

    # -- ADP-001: lifecycle + declared exposure ------------------------------------
    def _adp001(world: ConformanceWorld) -> ObservedOutcome:
        adapter = world.adapter
        exposed = adapter.capabilities()
        if tuple(exposed) == (_KNOWN_CAP,):
            return ObservedOutcome(
                True, "declared-exposure",
                "open adapter exposes exactly its declared capabilities",
            )
        return ObservedOutcome(
            False, "exposure-mismatch",
            "exposure %r != declared %r" % (exposed, (_KNOWN_CAP,)),
        )

    out.append(_vector(
        "001", "positive",
        "capability exposure equals the declared descriptor set",
        "An opened adapter with a declared capability exposes exactly it.",
        ExpectedOutcome(True, frozenset({"declared-exposure"})),
        _adp001,
        frozenset({"positive:core-behavior"}),
    ))

    # -- ADP-002: inflation containment -----------------------------------------------
    def _adp002(world: ConformanceWorld) -> ObservedOutcome:
        adapter = world.adapter
        runtime, adapter_id = adapter.runtime_with(InflatingAdapter())
        exposed = runtime.capabilities(adapter_id, now=NOW)
        if InflatingAdapter.INFLATED_EXTRA in exposed:
            return ObservedOutcome(
                True, "inflation-leaked",
                "undeclared capability leaked into the exposure surface",
            )
        return ObservedOutcome(
            False, "inflation-contained",
            "implementation inflation filtered to the declared set",
        )

    out.append(_vector(
        "002", "negative",
        "an implementation can never inflate exposure beyond its descriptor",
        "An adapter reporting extra capability ids is filtered by the "
        "runtime.",
        ExpectedOutcome(False, frozenset({"inflation-contained"})),
        _adp002,
        frozenset({"negative:capability-inflation",
                   "discriminating:capability-inflation"}),
    ))

    # -- ADP-003: allocate -> release lifecycle -----------------------------------------
    def _adp003(world: ConformanceWorld) -> ObservedOutcome:
        adapter = world.adapter
        allocated = adapter.allocate(quantity=10)
        if not allocated.ok or allocated.value is None:
            return ObservedOutcome(
                False, "allocate-failed",
                "fixture allocation failed: %s" % getattr(
                    allocated, "detail", ""
                ),
            )
        allocation_id = allocated.value.allocation_id \
            if hasattr(allocated.value, "allocation_id") else allocated.value
        released = adapter.release(allocation_id)
        if released.ok:
            return ObservedOutcome(
                True, "allocation-released",
                "allocation active then released cleanly",
            )
        return _outcome(released)

    out.append(_vector(
        "003", "positive",
        "allocations are content-identified and releasable",
        "allocate -> release through the runtime contract.",
        ExpectedOutcome(True, frozenset({"allocation-released"})),
        _adp003,
        frozenset({"positive:core-behavior"}),
    ))

    # -- ADP-004: bind only bindable sessions ---------------------------------------------
    def _adp004(world: ConformanceWorld) -> ObservedOutcome:
        adapter = world.adapter
        requested_sid = world.session.requested(world.node_a, world.node_b)
        result = adapter.bind(requested_sid)
        if not result.ok:
            return _outcome(result)
        return ObservedOutcome(
            True, "unbindable-session-bound",
            "REQUESTED session bound to an adapter bearer",
        )

    out.append(_vector(
        "004", "negative",
        "session binding verifies the session is bindable (read-only W012)",
        "bind_session on a REQUESTED session fails with "
        "session-not-bindable.",
        ExpectedOutcome(False, frozenset({"session-not-bindable"})),
        _adp004,
        frozenset({"negative:binding-violation"}),
    ))

    # -- ADP-005: provider exception isolation -----------------------------------------------
    def _adp005(world: ConformanceWorld) -> ObservedOutcome:
        adapter = world.adapter
        runtime, adapter_id = adapter.runtime_with(
            ThrowingAdapter("allocate", RuntimeError("provider exploded"))
        )
        result = runtime.allocate(
            adapter_id, kind="bandwidth", quantity=1, unit="mbps",
            purpose="conformance", now=NOW,
        )
        if not result.ok:
            failure = getattr(result, "failure", None)
            reason = getattr(failure, "reason", None) if failure else None
            if reason == "adapter-failure":
                return ObservedOutcome(
                    False, "adapter-failure",
                    "provider exception isolated as a typed failure value",
                )
            return ObservedOutcome(False, reason or "isolated", result.detail)
        return ObservedOutcome(
            True, "exception-propagated-or-accepted",
            "throwing adapter produced ok=True",
        )

    out.append(_vector(
        "005", "negative",
        "adapter exceptions become typed failure values, never propagate",
        "An allocate() that raises RuntimeError yields ok=False with "
        "reason adapter-failure.",
        ExpectedOutcome(False, frozenset({"adapter-failure"})),
        _adp005,
        frozenset({
            "negative:provider-exception",
            "discriminating:adapter-isolation",
            "recovery:provider-exception",
        }),
    ))

    # -- ADP-006: contract-shape violation ------------------------------------------------------
    def _adp006(world: ConformanceWorld) -> ObservedOutcome:
        adapter = world.adapter
        runtime, adapter_id = adapter.runtime_with(MisshapenObserveAdapter())
        result = runtime.observe(adapter_id, now=NOW)
        if not result.ok:
            failure = getattr(result, "failure", None)
            reason = getattr(failure, "reason", None) if failure else None
            if reason in ("contract-violation", "adapter-failure"):
                return ObservedOutcome(
                    False, reason,
                    "contract-violating return shape isolated",
                )
            return ObservedOutcome(False, reason or "isolated", result.detail)
        return ObservedOutcome(
            True, "bad-shape-accepted",
            "contract-violating observe() return accepted",
        )

    out.append(_vector(
        "006", "negative",
        "contract return shapes are validated (fail-closed mediation)",
        "observe() returning a float metric is isolated as a "
        "contract-violation failure value.",
        ExpectedOutcome(False, frozenset({"contract-violation",
                                          "adapter-failure"})),
        _adp006,
        frozenset({"negative:provider-exception",
                   "recovery:provider-exception"}),
    ))

    # -- ADP-007: step budget hang model ----------------------------------------------------------
    def _adp007(world: ConformanceWorld) -> ObservedOutcome:
        adapter = world.adapter
        runtime, adapter_id = adapter.runtime_with(BudgetBurningAdapter())
        result = runtime.allocate(
            adapter_id, kind="bandwidth", quantity=1, unit="mbps",
            purpose="conformance", now=NOW,
        )
        if not result.ok:
            failure = getattr(result, "failure", None)
            reason = getattr(failure, "reason", None) if failure else None
            if reason == "budget-exhausted":
                return ObservedOutcome(
                    False, "budget-exhausted",
                    "unbounded work converted to a budget-exhausted failure",
                )
            return ObservedOutcome(False, reason or "isolated", result.detail)
        return ObservedOutcome(
            True, "hang-accepted", "budget-burning allocate returned ok=True"
        )

    out.append(_vector(
        "007", "negative",
        "the deterministic step budget is the hang model (no wall clock)",
        "An adapter burning its whole budget yields budget-exhausted.",
        ExpectedOutcome(False, frozenset({"budget-exhausted"})),
        _adp007,
        frozenset({"negative:provider-exception",
                   "recovery:provider-exception"}),
    ))

    # -- ADP-008: supervision thresholds + reported-never-authoritative health --------------------
    def _adp008(world: ConformanceWorld) -> ObservedOutcome:
        adapter = world.adapter
        runtime, adapter_id = adapter.runtime_with(
            ThrowingAdapter("allocate", RuntimeError("boom"))
        )
        for _ in range(2):
            runtime.allocate(
                adapter_id, kind="bandwidth", quantity=1, unit="mbps",
                purpose="conformance", now=NOW,
            )
        report = runtime.health(adapter_id, now=NOW)
        if report.computed_state == "DEGRADED" and \
                report.reported_state == "HEALTHY":
            return ObservedOutcome(
                True, "computed-degraded",
                "two consecutive failures degrade COMPUTED health while the "
                "adapter still reports healthy (reported is never "
                "authoritative)",
            )
        return ObservedOutcome(
            False, "health-mismatch",
            "computed=%s reported=%s" % (report.computed_state,
                                         report.reported_state),
        )

    out.append(_vector(
        "008", "positive",
        "health is computed from frozen thresholds; reports are advisory",
        "FAILURE_THRESHOLD_DEGRADED=2 consecutive failures -> computed "
        "DEGRADED despite a lying HEALTHY report.",
        ExpectedOutcome(True, frozenset({"computed-degraded"})),
        _adp008,
        frozenset({"positive:core-behavior",
                   "discriminating:adapter-isolation"}),
    ))

    # -- ADP-009: close fails closed with outstanding allocations -----------------------------------
    def _adp009(world: ConformanceWorld) -> ObservedOutcome:
        from adapters import AdapterError

        adapter = world.adapter
        allocated = adapter.allocate(quantity=10)
        if not allocated.ok:
            return ObservedOutcome(
                False, "fixture-allocate-failed", "allocation failed"
            )
        try:
            closed = adapter.close()
        except AdapterError as error:
            return ObservedOutcome(
                False, getattr(error, "reason", "allocation-state"),
                str(error),
            )
        if not closed.ok:
            return _outcome(closed)
        return ObservedOutcome(
            True, "closed-with-outstanding",
            "adapter closed despite an outstanding allocation",
        )

    out.append(_vector(
        "009", "negative",
        "teardown is explicit: outstanding capacity blocks close",
        "close_adapter with an ACTIVE allocation fails closed.",
        ExpectedOutcome(False, frozenset({"state-conflict",
                                          "allocation-state"})),
        _adp009,
        frozenset({"recovery:cleanup-failure"}),
    ))

    # -- ADP-010: deterministic allocation expiry ------------------------------------------------------
    def _adp010(world: ConformanceWorld) -> ObservedOutcome:
        adapter = world.adapter
        allocated = adapter.allocate(quantity=10, expires_at=LATER)
        if not allocated.ok:
            return ObservedOutcome(
                False, "fixture-allocate-failed", "allocation failed"
            )
        expired = adapter.runtime.expire_allocations(now=EVEN_LATER)
        if len(expired) == 1:
            return ObservedOutcome(
                True, "expired",
                "stale allocation deterministically expired",
            )
        return ObservedOutcome(
            False, "expiry-missed",
            "expire_allocations returned %d entries" % len(expired),
        )

    out.append(_vector(
        "010", "positive",
        "expired leases are reclaimed deterministically",
        "expire_allocations at a later instant expires the lease.",
        ExpectedOutcome(True, frozenset({"expired"})),
        _adp010,
        frozenset({"recovery:stale-future", "positive:core-behavior"}),
    ))

    # -- ADP-011: unknown adapter ------------------------------------------------------------------------
    def _adp011(world: ConformanceWorld) -> ObservedOutcome:
        from adapters import AdapterError

        try:
            result = world.adapter.runtime.observe(
                "adcos:adapter:access.generic.experimental:" + "0" * 16,
                now=NOW,
            )
        except AdapterError as error:
            if getattr(error, "reason", "") == "unknown-adapter":
                return ObservedOutcome(
                    False, "unknown-adapter", "unknown adapter rejected"
                )
            return ObservedOutcome(
                False, getattr(error, "reason", type(error).__name__),
                str(error),
            )
        if not result.ok:
            failure = getattr(result, "failure", None)
            reason = getattr(failure, "reason", None) if failure else None
            if reason == "unknown-adapter":
                return ObservedOutcome(
                    False, "unknown-adapter", "unknown adapter rejected"
                )
            return ObservedOutcome(False, reason or "isolated", result.detail)
        try:
            world.adapter.runtime.observe("not-an-adapter-id", now=NOW)
        except AdapterError as error:
            if getattr(error, "reason", "") == "unknown-adapter":
                return ObservedOutcome(
                    False, "unknown-adapter",
                    "malformed adapter id rejected as unknown",
                )
            return ObservedOutcome(
                False, getattr(error, "reason", type(error).__name__),
                str(error),
            )
        return ObservedOutcome(
            True, "unknown-accepted", "unknown adapter accepted"
        )

    out.append(_vector(
        "011", "negative",
        "operations on unknown adapters fail closed",
        "observe on an unregistered adapter id fails with "
        "unknown-adapter.",
        ExpectedOutcome(False, frozenset({"unknown-adapter"})),
        _adp011,
        frozenset({"negative:malformed-required-fields"}),
    ))

    # -- ADP-012: duplicate registration -------------------------------------------------------------------
    def _adp012(world: ConformanceWorld) -> ObservedOutcome:
        from adapters import AdapterError

        adapter = world.adapter
        try:
            adapter.runtime.register(
                adapter.descriptor(), ReferenceAdapter(), now=NOW
            )
        except AdapterError as error:
            if getattr(error, "reason", "") == "duplicate-adapter":
                return ObservedOutcome(
                    False, "duplicate-adapter",
                    "duplicate adapter registration rejected",
                )
            return ObservedOutcome(
                False, getattr(error, "reason", type(error).__name__),
                str(error),
            )
        return ObservedOutcome(
            True, "duplicate-accepted", "duplicate registration permitted"
        )

    out.append(_vector(
        "012", "negative",
        "adapter ids are unique per runtime",
        "Registering the same adapter_id twice raises "
        "AdapterError(duplicate-adapter).",
        ExpectedOutcome(False, frozenset({"duplicate-adapter"})),
        _adp012,
        frozenset({"negative:malformed-required-fields"}),
    ))

    # -- ADP-013: state envelope recovery round-trip ---------------------------------------------------------
    def _adp013(world: ConformanceWorld) -> ObservedOutcome:
        from adapters import (
            adapter_state_from_envelope,
            adapter_state_to_envelope,
            adapter_view,
            adapter_view_from_mapping,
        )

        adapter = world.adapter
        view = adapter_view(adapter.runtime, adapter.adapter_id, now=NOW)
        restored_view = adapter_view_from_mapping(view)
        if restored_view != view:
            return ObservedOutcome(
                False, "view-roundtrip-mismatch",
                "adapter view changed across the mapping round-trip",
            )
        envelope = adapter_state_to_envelope(
            view,
            message_type="adapter.state",
            message_id="msg-conformance-adapter-state",
            sender=world.node_a,
            issued_at="2030-01-01T00:00:00Z",
            expires_at="2030-01-01T01:00:00Z",
        )
        state = adapter_state_from_envelope(envelope)
        if state.get("adapter_id") == adapter.adapter_id:
            return ObservedOutcome(
                True, "state-envelope-recovered",
                "adapter state persisted to a WORK-003 envelope and "
                "recovered",
            )
        return ObservedOutcome(
            False, "state-envelope-mismatch",
            "recovered state for %r" % state.get("adapter_id"),
        )

    out.append(_vector(
        "013", "positive",
        "adapter state persists through the WORK-003 envelope (restart)",
        "adapter_state_to_envelope -> adapter_state_from_envelope "
        "recovers the state view.",
        ExpectedOutcome(True, frozenset({"state-envelope-recovered"})),
        _adp013,
        frozenset({"recovery:restart", "matrix:envelope-interop"}),
    ))

    # -- ADP-014: generic metrics surface ----------------------------------------------------------------------
    def _adp014(world: ConformanceWorld) -> ObservedOutcome:
        result = world.adapter.observe()
        if result.ok:
            return ObservedOutcome(
                True, "observed",
                "generic link metrics observed through the contract",
            )
        return _outcome(result)

    out.append(_vector(
        "014", "positive",
        "observe returns the frozen generic metric surface",
        "observe() over the reference adapter yields mediated samples.",
        ExpectedOutcome(True, frozenset({"observed"})),
        _adp014,
        frozenset({"positive:core-behavior"}),
    ))

    # -- ADP-015: allocation on closed adapter -------------------------------------------------------------------
    def _adp015(world: ConformanceWorld) -> ObservedOutcome:
        adapter = world.adapter
        # Build a dedicated adapter with no outstanding state, then close.
        runtime, adapter_id = adapter.runtime_with(
            ReferenceAdapter(), label="closeable-0"
        )
        closed = runtime.close_adapter(adapter_id, now=NOW)
        if not closed.ok:
            return _outcome(closed)
        result = runtime.allocate(
            adapter_id, kind="bandwidth", quantity=1, unit="mbps",
            purpose="conformance", now=NOW,
        )
        if not result.ok:
            failure = getattr(result, "failure", None)
            reason = getattr(failure, "reason", None) if failure else None
            if reason in ("adapter-closed", "not-open"):
                return ObservedOutcome(
                    False, reason, "closed adapter rejected the operation"
                )
            return ObservedOutcome(False, reason or "isolated", result.detail)
        return ObservedOutcome(
            True, "closed-adapter-accepted",
            "closed adapter accepted an allocation",
        )

    out.append(_vector(
        "015", "negative",
        "closed adapters reject further operations",
        "allocate after close fails with adapter-closed / not-open.",
        ExpectedOutcome(False, frozenset({"adapter-closed", "not-open"})),
        _adp015,
        frozenset({"negative:binding-violation", "recovery:cleanup-failure"}),
    ))

    return tuple(out)
