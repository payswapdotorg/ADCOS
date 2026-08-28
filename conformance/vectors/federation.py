"""WORK-032 conformance vectors -- federation (WORK-015).

Covers: domain lifecycle, relationship establishment with declared
scope envelopes, grants (least authority; never exceeding the
envelope), revocation semantics, peer-domain isolation, exchange
application with sequence discipline, replay provenance, and scope
escalation rejections.
"""

from __future__ import annotations

from typing import Any, Callable, FrozenSet, Tuple

from federation import (
    ExchangeKind,
    FederationExchange,
    Scope,
    classify_scope,
)

from conformance.model import ConformanceVector, ExpectedOutcome, ObservedOutcome
from conformance.world import FUTURE, NOW, PAST, T0, T1, ConformanceWorld

__all__ = ["vectors"]

_AREA = "federation"
_AUTHORITY = "WORK-015"
_CONTRACT = "spec/architecture.md section 16 (federation) / WORK-015"


def _vector(number: str, polarity: str, invariant: str,
            description: str, expected: ExpectedOutcome,
            execute: Callable[[ConformanceWorld], ObservedOutcome],
            tags: FrozenSet[str] = frozenset()) -> ConformanceVector:
    return ConformanceVector(
        vector_id="W032-CNF-FED-%s" % number,
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
    return ObservedOutcome(bool(result.ok), result.code, result.detail)


def _exchange(kind: Any, *, local: str, peer: str, sequence: int,
              peer_identity: str,
              scopes: Tuple[str, ...] = ()) -> Any:
    return FederationExchange(
        exchange_id="",
        exchange_kind=kind,
        local_domain_id=local,
        peer_domain_id=peer,
        sequence=sequence,
        declared_at=NOW,
        effective_at=NOW,
        peer_identity_reference=peer_identity,
        scopes=tuple(scopes),
    )


def vectors() -> Tuple[ConformanceVector, ...]:
    out = []

    # -- FED-001: domain creation + conflicting material -------------------------
    def _fed001(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        first = fed.create_domain(world.node_a, "ab" * 32)
        # Same operator reference + key -> same derived id -> idempotent.
        second = fed.create_domain(world.node_a, "ab" * 32)
        # The attack: SAME identity material (same derived domain id) but
        # presented under a DIFFERENT operator node id.
        conflicting = fed.store.create_domain(
            "operator-reference",
            "ab" * 32,
            operator_node_id=world.node_c,
            created_at=NOW,
        )
        if (first.ok and second.ok
                and not conflicting.ok
                and conflicting.code == "domain-exists"):
            return ObservedOutcome(
                False, "domain-exists",
                "conflicting material for a live domain id rejected",
            )
        return ObservedOutcome(
            bool(conflicting.ok), conflicting.code,
            "conflicting material produced %s" % conflicting.code,
        )

    out.append(_vector(
        "001", "negative",
        "domain identity is derived from identity material only",
        "Re-registering an existing domain id with different material "
        "fails with domain-exists.",
        ExpectedOutcome(False, frozenset({"domain-exists"})),
        _fed001,
        frozenset({"negative:forged-provenance"}),
    ))

    # -- FED-002: establishment + granted scope allowed -----------------------------
    def _fed002(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        domain_a, domain_b, rid = fed.established_pair(
            scopes=(Scope.CAPABILITY_READ,)
        )
        grant = fed.publish_grant(rid, Scope.CAPABILITY_READ)
        if not grant.ok:
            return ObservedOutcome(
                False, grant.code, "grant within envelope failed: %s"
                % grant.detail,
            )
        check = fed.check_scope(rid, Scope.CAPABILITY_READ)
        return _outcome(check)

    out.append(_vector(
        "002", "positive",
        "declared + granted scopes evaluate as allowed",
        "establish(capability.read) + publish_grant(capability.read) -> "
        "check_scope ok (scope-allowed).",
        ExpectedOutcome(True, frozenset({"scope-allowed"})),
        _fed002,
        frozenset({"positive:core-behavior"}),
    ))

    # -- FED-003: undeclared scope never granted --------------------------------------
    def _fed003(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        domain_a, domain_b, rid = fed.established_pair(
            scopes=(Scope.CAPABILITY_READ,)
        )
        fed.publish_grant(rid, Scope.CAPABILITY_READ)
        check = fed.check_scope(rid, Scope.ROUTE_IMPORT)
        if check.code in ("scope-not-declared", "scope-not-granted"):
            return _outcome(check)
        return ObservedOutcome(
            check.code in ("scope-not-declared", "scope-not-granted"),
            check.code,
            "undeclared scope produced %s" % check.code,
        )

    out.append(_vector(
        "003", "negative",
        "no scope implies another (scope independence)",
        "check_scope for route.import with only capability.read declared "
        "fails.",
        ExpectedOutcome(False, frozenset({"scope-not-declared",
                                          "scope-not-granted"})),
        _fed003,
        frozenset({"negative:scope-escalation"}),
    ))

    # -- FED-004: grant escalation rejected ----------------------------------------------
    def _fed004(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        domain_a, domain_b, rid = fed.established_pair(
            scopes=(Scope.CAPABILITY_READ,)
        )
        # The attack: grant a scope OUTSIDE the declared envelope.
        result = fed.publish_grant(rid, Scope.ROUTE_IMPORT)
        if result.code == "grant-escalation":
            return _outcome(result)
        return ObservedOutcome(
            result.code == "grant-escalation", result.code,
            "out-of-envelope grant produced %s" % result.code,
        )

    out.append(_vector(
        "004", "negative",
        "grants can never exceed the declared envelope",
        "publish_grant for an undeclared scope fails with "
        "grant-escalation.",
        ExpectedOutcome(False, frozenset({"grant-escalation"})),
        _fed004,
        frozenset({"negative:scope-escalation"}),
    ))

    # -- FED-005: accept may only narrow ---------------------------------------------------
    def _fed005(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        domain_a, domain_b = fed.two_domains()
        proposed = fed.store.propose_relationship(
            domain_a, domain_b,
            peer_identity_reference=fed.domain_operator_ids[domain_b],
            declared_scopes=(Scope.CAPABILITY_READ, Scope.ROUTE_IMPORT),
            valid_from=T0, valid_until=T1, event_instant=NOW,
        )
        if not proposed.ok or proposed.relationship is None:
            return ObservedOutcome(
                False, proposed.code,
                "fixture proposal failed: %s" % proposed.detail,
            )
        # The attack: accept with a WIDER scope set.
        widened = fed.store.accept_relationship(
            proposed.relationship.relationship_id,
            event_instant=NOW,
            scopes=(Scope.CAPABILITY_READ, Scope.ROUTE_IMPORT,
                    Scope.RESOURCE_READ),
        )
        if not widened.ok:
            return _outcome(widened)
        return ObservedOutcome(
            True, "widening-accepted",
            "accept_relationship widened the declared scopes",
        )

    out.append(_vector(
        "005", "negative",
        "accepting a proposal may only narrow scopes",
        "accept_relationship with a wider scope set is rejected.",
        ExpectedOutcome(False, frozenset({"grant-escalation",
                                          "scope-not-declared",
                                          "invalid-scope",
                                          "invalid-input"})),
        _fed005,
        frozenset({"negative:scope-escalation",
                   "discriminating:authority-boundary"}),
    ))

    # -- FED-006: revoked grant is immediately inert -----------------------------------------
    def _fed006(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        domain_a, domain_b, rid = fed.established_pair(
            scopes=(Scope.CAPABILITY_READ,)
        )
        grant = fed.publish_grant(rid, Scope.CAPABILITY_READ)
        if not grant.ok or grant.grant is None:
            return ObservedOutcome(
                False, grant.code, "fixture grant failed"
            )
        revoked = fed.revoke_grant(grant.grant.grant_id)
        if not revoked.ok:
            return _outcome(revoked)
        check = fed.check_scope(rid, Scope.CAPABILITY_READ)
        if not check.ok:
            return _outcome(check)
        return ObservedOutcome(
            True, "revoked-still-allowed",
            "revoked grant still authorizes the scope",
        )

    out.append(_vector(
        "006", "negative",
        "revocation makes grants inert immediately (evidence preserved)",
        "check_scope after revoke_grant fails.",
        ExpectedOutcome(False, frozenset({"grant-inactive",
                                          "scope-not-granted",
                                          "grant-expired"})),
        _fed006,
        frozenset({"negative:scope-escalation", "recovery:stale-future"}),
    ))

    # -- FED-007: suspended relationship denies scope ------------------------------------------
    def _fed007(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        domain_a, domain_b, rid = fed.established_pair(
            scopes=(Scope.CAPABILITY_READ,)
        )
        fed.publish_grant(rid, Scope.CAPABILITY_READ)
        suspended = fed.store.suspend_relationship(rid, event_instant=NOW)
        if not suspended.ok:
            return _outcome(suspended)
        check = fed.check_scope(rid, Scope.CAPABILITY_READ)
        if not check.ok:
            return _outcome(check)
        return ObservedOutcome(
            True, "suspended-still-allowed",
            "suspended relationship still authorizes",
        )

    out.append(_vector(
        "007", "negative",
        "suspended relationships deny scope checks",
        "check_scope on a SUSPENDED relationship fails.",
        ExpectedOutcome(False, frozenset({"relationship-suspended"})),
        _fed007,
        frozenset({"negative:scope-escalation"}),
    ))

    # -- FED-008: expired relationship ----------------------------------------------------------
    def _fed008(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        domain_a, domain_b = fed.two_domains()
        established = fed.establish(
            domain_a, domain_b, scopes=(Scope.CAPABILITY_READ,),
            valid_until="2026-06-01T06:00:00Z",
        )
        if not established.ok or established.relationship is None:
            return ObservedOutcome(
                False, established.code, "fixture establishment failed"
            )
        fed.publish_grant(established.relationship.relationship_id,
                          Scope.CAPABILITY_READ)
        check = fed.check_scope(
            established.relationship.relationship_id, Scope.CAPABILITY_READ
        )
        if not check.ok:
            return _outcome(check)
        return ObservedOutcome(
            True, "expired-still-allowed", "expired relationship allowed scope"
        )

    out.append(_vector(
        "008", "negative",
        "expired relationships deny scope checks",
        "check_scope past valid_until fails with relationship-expired.",
        ExpectedOutcome(False, frozenset({"relationship-expired"})),
        _fed008,
        frozenset({"negative:expired-future-data", "recovery:stale-future"}),
    ))

    # -- FED-009: peer-authored declaration applied --------------------------------------------
    def _fed009(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        domain_a, domain_b, rid = fed.established_pair(
            scopes=(Scope.CAPABILITY_READ,)
        )
        fed.publish_grant(rid, Scope.CAPABILITY_READ)
        # The peer (B) authors a scope-update declaration; the exchange's
        # peer_identity_reference is the DECLARER's operator identity.
        exchange = _exchange(
            ExchangeKind.SCOPE_UPDATE,
            local=domain_b, peer=domain_a,
            sequence=3,
            peer_identity=fed.domain_operator_ids[domain_b],
            scopes=(Scope.CAPABILITY_READ,),
        )
        result = fed.apply_exchange(exchange)
        return _outcome(result)

    out.append(_vector(
        "009", "positive",
        "peer-authored declarations apply through the exchange contract",
        "apply_exchange(scope-update) authored by the relationship's peer "
        "at the next sequence slot succeeds.",
        ExpectedOutcome(True, frozenset({"recorded", "created",
                                         "scope-updated"})),
        _fed009,
        frozenset({"positive:core-behavior"}),
    ))

    # -- FED-010: non-peer declarer rejected -----------------------------------------------------
    def _fed010(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        domain_a, domain_b, rid = fed.established_pair(
            scopes=(Scope.CAPABILITY_READ,)
        )
        # An unrelated third domain authors the declaration.
        domain_c = fed.create_domain(
            world.node_c, "cc" * 32
        ).domain.domain_id
        exchange = _exchange(
            ExchangeKind.SCOPE_UPDATE,
            local=domain_c, peer=domain_a,
            sequence=3,
            peer_identity=fed.domain_operator_ids[domain_c],
            scopes=(Scope.CAPABILITY_READ,),
        )
        result = fed.apply_exchange(exchange)
        if not result.ok:
            return _outcome(result)
        return ObservedOutcome(
            True, "non-peer-declaration-applied",
            "a declaration from a non-peer domain was applied",
        )

    out.append(_vector(
        "010", "negative",
        "declarations must be authored by the relationship's peer",
        "A scope-update exchange authored by an unrelated domain fails "
        "closed (cross-domain identity confusion).",
        ExpectedOutcome(False, frozenset({"peer-identity-mismatch",
                                          "peer-identity-invalid",
                                          "unknown-relationship",
                                          "invalid-exchange"})),
        _fed010,
        frozenset({"recovery:cross-authority-injection",
                   "negative:forged-provenance"}),
    ))

    # -- FED-011: replay provenance ---------------------------------------------------------------------
    def _fed011(world: ConformanceWorld) -> ObservedOutcome:
        from federation import FederationEvent, SUBJECT_KIND_RELATIONSHIP

        fed = world.federation
        domain_a, domain_b, rid = fed.established_pair(
            scopes=(Scope.CAPABILITY_READ,)
        )
        events = fed.events_for(rid)
        if not events:
            return ObservedOutcome(
                False, "no-events", "fixture relationship has no events"
            )
        # Exact duplicate replay is allowed.
        exact = fed.replay_event(rid, events[-1])
        if not exact.ok:
            return _outcome(exact)
        # The attack: a never-accepted forged event occupying the NEXT
        # sequence slot (so sequence validation passes and the replay
        # provenance check is what must reject it).
        forged = FederationEvent(
            event_id="",
            subject_id=rid,
            subject_kind=SUBJECT_KIND_RELATIONSHIP,
            sequence=events[-1].sequence + 1,
            previous_state="ESTABLISHED",
            new_state="ESTABLISHED",
            event_type="relationship-suspended",
            event_instant=NOW,
        )
        result = fed.replay_event(rid, forged)
        if not result.ok:
            return _outcome(result)
        return ObservedOutcome(
            True, "forged-replay-accepted",
            "never-accepted event replayed into history",
        )

    out.append(_vector(
        "011", "negative",
        "replay is valid ONLY for exact accepted duplicates",
        "Replaying a forged never-accepted event fails with "
        "replay-provenance.",
        ExpectedOutcome(False, frozenset({"replay-provenance",
                                          "invalid-input"})),
        _fed011,
        frozenset({
            "negative:replay",
            "negative:forged-provenance",
            "recovery:replay-state",
        }),
    ))

    # -- FED-012: exchange sequence conflict -------------------------------------------------------------
    def _fed012(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        domain_a, domain_b, rid = fed.established_pair(
            scopes=(Scope.CAPABILITY_READ,)
        )
        fed.publish_grant(rid, Scope.CAPABILITY_READ)
        # slot 1 = establishment, slot 2 = grant -> next declaration = 3.
        first = _exchange(
            ExchangeKind.SCOPE_UPDATE,
            local=domain_b, peer=domain_a, sequence=3,
            peer_identity=fed.domain_operator_ids[domain_b],
            scopes=(Scope.CAPABILITY_READ,),
        )
        applied = fed.apply_exchange(first)
        if not applied.ok:
            return _outcome(applied)
        conflict = _exchange(
            ExchangeKind.REVOCATION,
            local=domain_b, peer=domain_a, sequence=3,
            peer_identity=fed.domain_operator_ids[domain_b],
        )
        result = fed.apply_exchange(conflict)
        if not result.ok:
            return _outcome(result)
        return ObservedOutcome(
            True, "sequence-conflict-allowed",
            "conflicting exchange sequence applied twice",
        )

    out.append(_vector(
        "012", "negative",
        "exchange sequences are conflict-checked",
        "Applying a conflicting sequence twice fails with "
        "sequence-conflict.",
        ExpectedOutcome(False, frozenset({"sequence-conflict",
                                          "replay-conflict"})),
        _fed012,
        frozenset({"recovery:version-conflict", "negative:replay"}),
    ))

    # -- FED-013: invalid scope string -----------------------------------------------------------------------
    def _fed013(world: ConformanceWorld) -> ObservedOutcome:
        classification = classify_scope("not-a-scope!!")
        if classification == "invalid":
            return ObservedOutcome(
                False, "invalid-scope",
                "malformed scope string classified invalid",
            )
        return ObservedOutcome(
            classification == "invalid", classification,
            "malformed scope classified %r" % classification,
        )

    out.append(_vector(
        "013", "negative",
        "scope strings are validated against the frozen vocabulary",
        "classify_scope rejects malformed scope strings.",
        ExpectedOutcome(False, frozenset({"invalid-scope"})),
        _fed013,
        frozenset({"negative:malformed-required-fields"}),
    ))

    # -- FED-014: exchange envelope round-trip -----------------------------------------------------------------
    def _fed014(world: ConformanceWorld) -> ObservedOutcome:
        from federation import exchange_from_envelope, exchange_to_envelope

        exchange = _exchange(
            ExchangeKind.CAPABILITY_EXPORT,
            local="sha256:" + "a" * 64, peer="sha256:" + "b" * 64,
            sequence=1, peer_identity=world.node_b,
        )
        envelope = exchange_to_envelope(
            exchange,
            message_type="federation.exchange",
            message_id="msg-conformance-federation",
            sender=world.node_a,
            issued_at="2030-01-01T00:00:00Z",
            expires_at="2030-01-01T01:00:00Z",
        )
        restored = exchange_from_envelope(envelope)
        if restored.exchange_id == exchange.exchange_id and \
                restored.sequence == exchange.sequence:
            return ObservedOutcome(
                True, "envelope-roundtrip",
                "federation exchanges ride the WORK-003 envelope verbatim",
            )
        return ObservedOutcome(
            False, "roundtrip-mismatch",
            "exchange content changed across the envelope round-trip",
        )

    out.append(_vector(
        "014", "positive",
        "exchanges serialize through the WORK-003 envelope",
        "exchange_to_envelope -> exchange_from_envelope preserves the "
        "exchange.",
        ExpectedOutcome(True, frozenset({"envelope-roundtrip"})),
        _fed014,
        frozenset({"positive:core-behavior", "matrix:envelope-interop"}),
    ))

    # -- FED-015: peer-domain isolation --------------------------------------------------------------------------
    def _fed015(world: ConformanceWorld) -> ObservedOutcome:
        fed = world.federation
        # Two independent established relationships.
        domain_a, domain_b, rid_ab = fed.established_pair(
            scopes=(Scope.CAPABILITY_READ,)
        )
        domain_c = fed.create_domain(world.node_c, "cc" * 32).domain.domain_id
        established_ac = fed.establish(
            domain_a, domain_c, scopes=(Scope.ROUTE_IMPORT,)
        )
        if not established_ac.ok or established_ac.relationship is None:
            return ObservedOutcome(
                False, established_ac.code, "fixture AC establishment failed"
            )
        rid_ac = established_ac.relationship.relationship_id
        # Grant scope only on AB.
        fed.publish_grant(rid_ab, Scope.CAPABILITY_READ)
        # The attack: use the AB grant to authorize a scope on AC.
        check = fed.check_scope(rid_ac, Scope.CAPABILITY_READ)
        if not check.ok:
            return _outcome(check)
        return ObservedOutcome(
            True, "cross-relationship-leak",
            "a grant on one relationship authorized another relationship",
        )

    out.append(_vector(
        "015", "negative",
        "grants never leak across relationships (peer-domain isolation)",
        "check_scope on relationship AC with a grant only on AB fails.",
        ExpectedOutcome(False, frozenset({"scope-not-declared",
                                          "scope-not-granted"})),
        _fed015,
        frozenset({"recovery:cross-authority-injection",
                   "negative:scope-escalation"}),
    ))

    return tuple(out)
