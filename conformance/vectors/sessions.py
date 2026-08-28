"""WORK-032 conformance vectors -- logical sessions (WORK-012).

Covers: access-independent session identity, lifecycle, expiry,
failover (reconnect with old+new path references -- the multipath/
session binding surface owned by the frozen W012 contract), replay
safety, and route/policy/intent/endpoint binding violations.

Note: the multipath coverage required by the W032 matrix rides this
area: W012's reconnect records META_OLD_PATH_ID / META_NEW_PATH_ID.
The multipath family (W013) is NOT a declared W032 dependency and is
never imported.
"""

from __future__ import annotations

from typing import Any, Callable, FrozenSet, Tuple

from sessions import (
    META_NEW_PATH_ID,
    META_OLD_PATH_ID,
    SessionError,
    SessionState,
)

from conformance.model import ConformanceVector, ExpectedOutcome, ObservedOutcome
from conformance.world import LATER, NOW, ConformanceWorld

from topology import (
    ClaimType,
    SourceClass,
    TopologyClaim,
    make_link_subject,
)

__all__ = ["vectors"]

_AREA = "sessions"
_AUTHORITY = "WORK-012"
_CONTRACT = "spec/architecture.md section 13 (sessions) / WORK-012"


def _vector(number: str, polarity: str, invariant: str,
            description: str, expected: ExpectedOutcome,
            execute: Callable[[ConformanceWorld], ObservedOutcome],
            tags: FrozenSet[str] = frozenset()) -> ConformanceVector:
    return ConformanceVector(
        vector_id="W032-CNF-SES-%s" % number,
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


def _result_outcome(result: Any) -> ObservedOutcome:
    return ObservedOutcome(bool(result.ok), result.code, result.detail)


def vectors() -> Tuple[ConformanceVector, ...]:
    out = []

    # -- SES-001: create + idempotent replay ----------------------------------
    def _ses001(world: ConformanceWorld) -> ObservedOutcome:
        session = world.session
        route = world.routing.decision(world.node_a, world.node_b, NOW)
        policy = world.routing.policy(NOW)
        first = session.create(
            route, policy, source=world.node_a, destination=world.node_b,
            instant=NOW,
        )
        events_before = len(session.events(first.session.session_id)) \
            if first.ok and first.session else -1
        second = session.create(
            route, policy, source=world.node_a, destination=world.node_b,
            instant=NOW,
        )
        events_after = len(session.events(first.session.session_id)) \
            if first.ok and first.session else -1
        if (first.ok and second.ok and second.code == "created"
                and events_before == events_after):
            return ObservedOutcome(
                True, "created",
                "exact-duplicate creation is idempotent (no new events)",
            )
        return ObservedOutcome(
            second.code == "created" and events_before == events_after,
            second.code,
            "replay outcome %s, events %d -> %d"
            % (second.code, events_before, events_after),
        )

    out.append(_vector(
        "001", "positive",
        "session creation is idempotent for exact duplicates",
        "Re-creating with identical binding material succeeds without "
        "appending any new events.",
        ExpectedOutcome(True, frozenset({"created"})),
        _ses001,
        frozenset({"recovery:replay-state", "positive:core-behavior"}),
    ))

    # -- SES-002: full lifecycle ------------------------------------------------
    def _ses002(world: ConformanceWorld) -> ObservedOutcome:
        session = world.session
        sid = session.established(world.node_a, world.node_b)
        # SUSPENDED is entered only via the explicit suspend operation.
        suspended = session.store.suspend(sid, event_instant=NOW)
        if not suspended.ok:
            return ObservedOutcome(
                False, suspended.code,
                "suspend failed: %s" % suspended.detail,
            )
        for new_state in (SessionState.RECONNECTING, SessionState.ESTABLISHED,
                          SessionState.TERMINATING, SessionState.TERMINATED):
            result = session.transition(sid, new_state, instant=NOW)
            if not result.ok:
                return ObservedOutcome(
                    False, result.code,
                    "lifecycle transition to %s failed: %s"
                    % (new_state, result.detail),
                )
        return ObservedOutcome(
            True, "created", "full legal lifecycle traversed",
        )

    out.append(_vector(
        "002", "positive",
        "the frozen lifecycle table permits the full legal traversal",
        "ESTABLISHED -> SUSPENDED -> ESTABLISHED -> TERMINATING -> "
        "TERMINATED all succeed.",
        ExpectedOutcome(True, frozenset({"created", "transitioned"})),
        _ses002,
        frozenset({"positive:core-behavior"}),
    ))

    # -- SES-003: route-not-selected ----------------------------------------------
    def _ses003(world: ConformanceWorld) -> ObservedOutcome:
        session = world.session
        routing = world.routing
        # A downed link yields a clean failure decision (ok=True, code
        # no-feasible-path, no selected path).
        graph = routing.graph(world.node_a, world.node_b)
        graph.merge(TopologyClaim(
            subject=make_link_subject(world.node_a, world.node_b),
            reporter=world.node_a,
            claim_type=ClaimType.LINK_STATE,
            value="down",
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at="2026-06-01T00:00:00Z",
            freshness_until="2026-12-31T23:59:59Z",
            sequence=2,
        ))
        failed = routing.evaluate(routing.context(
            world.node_a, world.node_b, NOW, graph=graph,
        ))
        decision = failed.decision
        if decision is None or decision.selected is not None:
            return ObservedOutcome(
                False, "fixture-no-failure-decision",
                "downed-link evaluation produced no clean failure decision",
            )
        result = session.create(
            decision, routing.policy(NOW), source=world.node_a,
            destination=world.node_b, instant=NOW,
        )
        if result.code == "route-not-selected":
            return _result_outcome(result)
        return ObservedOutcome(
            result.code == "route-not-selected", result.code,
            "non-selected route produced %s" % result.code,
        )

    out.append(_vector(
        "003", "negative",
        "sessions reference only SELECTED route decisions (never recompute)",
        "Creating from a policy-denied decision fails with "
        "route-not-selected.",
        ExpectedOutcome(False, frozenset({"route-not-selected"})),
        _ses003,
        frozenset({
            "negative:binding-violation",
            "discriminating:authority-boundary",
        }),
    ))

    # -- SES-004: tampered route decision --------------------------------------------
    def _ses004(world: ConformanceWorld) -> ObservedOutcome:
        import dataclasses

        session = world.session
        routing = world.routing
        route = routing.decision(world.node_a, world.node_b, NOW)
        policy = routing.policy(NOW)
        # The attack: mutate the decision content while keeping the id.
        tampered = dataclasses.replace(route, detail="tampered")
        result = session.create(
            tampered, policy, source=world.node_a, destination=world.node_b,
            instant=NOW,
        )
        if result.code == "route-tampered":
            return _result_outcome(result)
        return ObservedOutcome(
            result.code == "route-tampered", result.code,
            "tampered route produced %s" % result.code,
        )

    out.append(_vector(
        "004", "negative",
        "route decisions are tamper-evident",
        "A mutated RouteDecision body with the original id fails with "
        "route-tampered.",
        ExpectedOutcome(False, frozenset({"route-tampered"})),
        _ses004,
        frozenset({"negative:forged-provenance"}),
    ))

    # -- SES-005: policy binding mismatch ----------------------------------------------
    def _ses005(world: ConformanceWorld) -> ObservedOutcome:
        session = world.session
        routing = world.routing
        route = routing.decision(world.node_a, world.node_b, NOW)
        # A DIFFERENT genuine policy decision (distinct content: a
        # different evaluation instant yields a different decision id).
        other_policy = routing.policy(LATER)
        result = session.create(
            route, other_policy, source=world.node_a,
            destination=world.node_b, instant=NOW,
        )
        if result.code == "policy-binding-mismatch":
            return _result_outcome(result)
        return ObservedOutcome(
            result.code == "policy-binding-mismatch", result.code,
            "policy mismatch produced %s" % result.code,
        )

    out.append(_vector(
        "005", "negative",
        "the session binds the route's policy decision, not any decision",
        "Supplying a different genuine decision fails with "
        "policy-binding-mismatch.",
        ExpectedOutcome(False, frozenset({"policy-binding-mismatch"})),
        _ses005,
        frozenset({"negative:binding-violation"}),
    ))

    # -- SES-006: endpoint mismatch -----------------------------------------------------
    def _ses006(world: ConformanceWorld) -> ObservedOutcome:
        session = world.session
        routing = world.routing
        route = routing.decision(world.node_a, world.node_b, NOW)
        policy = routing.policy(NOW)
        result = session.create(
            route, policy, source=world.node_b, destination=world.node_a,
            instant=NOW,
        )
        if result.code == "endpoint-mismatch":
            return _result_outcome(result)
        return ObservedOutcome(
            result.code == "endpoint-mismatch", result.code,
            "swapped endpoints produced %s" % result.code,
        )

    out.append(_vector(
        "006", "negative",
        "session endpoints must match the route's endpoints",
        "Creating A->B route with B->A endpoints fails with "
        "endpoint-mismatch.",
        ExpectedOutcome(False, frozenset({"endpoint-mismatch"})),
        _ses006,
        frozenset({"negative:binding-violation"}),
    ))

    # -- SES-007: illegal transition ------------------------------------------------------
    def _ses007(world: ConformanceWorld) -> ObservedOutcome:
        session = world.session
        sid = session.established(world.node_a, world.node_b)
        result = session.transition(
            sid, SessionState.AUTHORIZED, instant=NOW
        )
        if result.code == "illegal-transition":
            return _result_outcome(result)
        return ObservedOutcome(
            result.code == "illegal-transition", result.code,
            "ESTABLISHED->AUTHORIZED produced %s" % result.code,
        )

    out.append(_vector(
        "007", "negative",
        "illegal lifecycle transitions fail closed",
        "ESTABLISHED -> AUTHORIZED is illegal.",
        ExpectedOutcome(False, frozenset({"illegal-transition"})),
        _ses007,
        frozenset({"negative:malformed-required-fields"}),
    ))

    # -- SES-008: terminal state ----------------------------------------------------------
    def _ses008(world: ConformanceWorld) -> ObservedOutcome:
        session = world.session
        sid = session.established(world.node_a, world.node_b)
        session.terminate(sid, instant=NOW)
        result = session.transition(sid, SessionState.ESTABLISHED,
                                    instant=NOW)
        if result.code == "terminal-state":
            return _result_outcome(result)
        return ObservedOutcome(
            result.code == "terminal-state", result.code,
            "transition after termination produced %s" % result.code,
        )

    out.append(_vector(
        "008", "negative",
        "terminal sessions never leave the terminal state",
        "Transitioning a TERMINATED session fails with terminal-state.",
        ExpectedOutcome(False, frozenset({"terminal-state"})),
        _ses008,
        frozenset({"negative:malformed-required-fields"}),
    ))

    # -- SES-009: terminate idempotence ------------------------------------------------------
    def _ses009(world: ConformanceWorld) -> ObservedOutcome:
        session = world.session
        sid = session.established(world.node_a, world.node_b)
        first = session.terminate(sid, instant=NOW)
        second = session.terminate(sid, instant=NOW)
        if first.ok and second.ok and second.code == "already-terminated":
            return ObservedOutcome(
                True, "already-terminated",
                "re-termination is an explicit idempotent outcome",
            )
        return ObservedOutcome(
            second.code == "already-terminated", second.code,
            "re-termination produced %s" % second.code,
        )

    out.append(_vector(
        "009", "positive",
        "termination is idempotent with an explicit code",
        "Second terminate returns already-terminated.",
        ExpectedOutcome(True, frozenset({"already-terminated"})),
        _ses009,
        frozenset({"positive:core-behavior", "recovery:replay-state"}),
    ))

    # -- SES-010: reconnect records old+new path (multipath binding surface) ------------------
    def _ses010(world: ConformanceWorld) -> ObservedOutcome:
        session = world.session
        routing = world.routing
        sid = session.established(world.node_a, world.node_b, NOW)
        session.transition(sid, SessionState.RECONNECTING, instant=NOW)
        # The new route is computed under the session's RETAINED policy
        # decision (policy binding never changes silently: W012/W031).
        retained_policy = routing.policy(NOW)
        new_route = routing.evaluate(routing.context(
            world.node_a, world.node_b, LATER, policy=retained_policy,
        )).decision
        if new_route is None:
            return ObservedOutcome(
                False, "fixture-no-decision", "reconnect route failed"
            )
        result = session.reconnect(
            sid, new_route, instant=LATER,
            new_policy_decision=retained_policy,
        )
        if not result.ok:
            return _result_outcome(result)
        events = session.events(sid)
        reconnect_events = [
            e for e in events
            if META_OLD_PATH_ID in dict(e.metadata or ())
        ]
        if not reconnect_events:
            return ObservedOutcome(
                False, "no-reconnect-metadata",
                "reconnect event does not record old+new path references",
            )
        metadata = dict(reconnect_events[-1].metadata or ())
        if META_OLD_PATH_ID in metadata and META_NEW_PATH_ID in metadata:
            return ObservedOutcome(
                True, "reconnected",
                "reconnect records both old and new path references",
            )
        return ObservedOutcome(
            False, "incomplete-reconnect-metadata",
            "missing %s or %s" % (META_OLD_PATH_ID, META_NEW_PATH_ID),
        )

    out.append(_vector(
        "010", "positive",
        "reconnect records old+new path references (session-path binding)",
        "The W012 reconnect event carries META_OLD_PATH_ID and "
        "META_NEW_PATH_ID -- the multipath binding surface of the frozen "
        "contract.",
        ExpectedOutcome(True, frozenset({"reconnected"})),
        _ses010,
        frozenset({"positive:core-behavior", "matrix:multipath-binding"}),
    ))

    # -- SES-011: reconnect from non-RECONNECTING state ---------------------------------------
    def _ses011(world: ConformanceWorld) -> ObservedOutcome:
        session = world.session
        routing = world.routing
        sid = session.established(world.node_a, world.node_b)
        new_route = routing.decision(world.node_a, world.node_b, LATER)
        result = session.reconnect(sid, new_route, instant=LATER)
        if result.code == "not-reconnecting":
            return _result_outcome(result)
        return ObservedOutcome(
            result.code == "not-reconnecting", result.code,
            "reconnect from ESTABLISHED produced %s" % result.code,
        )

    out.append(_vector(
        "011", "negative",
        "reconnect is legal only from RECONNECTING",
        "Reconnecting an ESTABLISHED session fails with not-reconnecting.",
        ExpectedOutcome(False, frozenset({"not-reconnecting"})),
        _ses011,
        frozenset({"negative:binding-violation"}),
    ))

    # -- SES-012: tampered event id --------------------------------------------------------------
    def _ses012(world: ConformanceWorld) -> ObservedOutcome:
        from sessions import SessionError, SessionEvent

        session = world.session
        sid = session.established(world.node_a, world.node_b)
        genuine = session.events(sid)[-1]
        # The attack: same content shape, forged event id.  (The event
        # dataclass itself is tamper-evident: a mismatched id fails at
        # CONSTRUCTION, before any store interaction.)
        try:
            forged = SessionEvent(
                event_id="sha256:" + "f" * 64,
                session_id=genuine.session_id,
                sequence=genuine.sequence + 5,
                previous_state=genuine.previous_state,
                new_state=genuine.new_state,
                event_type=genuine.event_type,
                event_instant=NOW,
            )
        except SessionError as error:
            return ObservedOutcome(
                False, getattr(error, "code", "event-tampered"),
                str(error),
            )
        try:
            result = session.store.append_event(sid, forged)
        except SessionError as error:
            return ObservedOutcome(
                False, getattr(error, "code", "event-tampered"),
                str(error),
            )
        if result.code in ("event-tampered", "sequence-gap",
                           "event-state-mismatch", "event-id"):
            return _result_outcome(result)
        return ObservedOutcome(
            result.code in ("event-tampered", "sequence-gap",
                            "event-state-mismatch", "event-id"),
            result.code,
            "forged event produced %s" % result.code,
        )

    out.append(_vector(
        "012", "negative",
        "event ids are content-derived; forged ids fail closed",
        "Appending an event with a forged id is rejected (event tampering).",
        ExpectedOutcome(False, frozenset({
            "event-tampered", "sequence-gap", "event-state-mismatch",
            "event-id",
        })),
        _ses012,
        frozenset({"negative:forged-provenance", "recovery:replay-state"}),
    ))

    # -- SES-013: extension events require the registered authority --------------------------------------------
    def _ses013(world: ConformanceWorld) -> ObservedOutcome:
        from sessions import SessionEvent

        session = world.session
        sid = session.established(world.node_a, world.node_b)
        current = session.get(sid)
        last = session.events(sid)[-1]
        # A genuine state-preserving extension event with a content-derived
        # id, appended through the PUBLIC path: only the registered
        # extension commit capability may commit extension events, so the
        # public append path must fail closed (the state machine cannot be
        # bypassed to smuggle one in).
        event = SessionEvent(
            event_id="",
            session_id=sid,
            sequence=last.sequence + 1,
            previous_state=current.state,
            new_state=current.state,
            event_type="extension.conformance.sampled",
            event_instant=NOW,
            metadata=(("k", "v"),),
        )
        result = session.store.append_event(sid, event)
        if not result.ok:
            return _result_outcome(result)
        return ObservedOutcome(
            True, "extension-smuggled",
            "unregistered caller committed an extension event",
        )

    out.append(_vector(
        "013", "negative",
        "extension events can only be committed by the registered capability",
        "A well-formed state-preserving extension event appended through "
        "the public path is rejected -- the state machine is not a bypass "
        "for unregistered extension authority.",
        ExpectedOutcome(False, frozenset({"illegal-transition",
                                          "extension-authority-required",
                                          "invalid-input"})),
        _ses013,
        frozenset({"negative:unknown-extensions",
                   "negative:hidden-authority-access"}),
    ))

    # -- SES-014: cross-session event injection ----------------------------------------------------
    def _ses014(world: ConformanceWorld) -> ObservedOutcome:
        session = world.session
        sid_a = session.established(world.node_a, world.node_b)
        sid_b = session.established(world.node_a, world.node_c)
        event_b = session.events(sid_b)[-1]
        result = session.store.append_event(sid_a, event_b)
        if result.code in ("event-binding-mismatch", "event-tampered",
                           "sequence-conflict"):
            return _result_outcome(result)
        return ObservedOutcome(
            result.code in ("event-binding-mismatch", "event-tampered",
                            "sequence-conflict"), result.code,
            "cross-session injection produced %s" % result.code,
        )

    out.append(_vector(
        "014", "negative",
        "events from another session never inject into this one",
        "Appending session B's event to session A fails closed.",
        ExpectedOutcome(False, frozenset({
            "event-binding-mismatch", "event-tampered", "sequence-conflict",
            "invalid-input",
        })),
        _ses014,
        frozenset({"recovery:cross-authority-injection"}),
    ))

    return tuple(out)
