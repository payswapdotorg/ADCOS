"""WORK-032 conformance vectors -- evidence-aware topology (WORK-007).

Covers: topology dimensions, self-attribution, claim provenance
(remote claims never become authoritative), poisoning resistance,
stale/removal convergence, sequence watermarks, same-sequence conflict
preservation, forged claim ids, and the capability-statement ingest
bridge (W005 -> W007) with signature verification.
"""

from __future__ import annotations

from typing import Any, Callable, FrozenSet, Tuple

from protocol import parse_instant

from conformance.model import ConformanceVector, ExpectedOutcome, ObservedOutcome
from conformance.world import NOW, T0, T1, ConformanceWorld

from topology import (
    ClaimType,
    MergeRejectedError,
    SourceClass,
    TopologyError,
    make_link_subject,
)

__all__ = ["vectors"]

_AREA = "topology"
_AUTHORITY = "WORK-007"
_CONTRACT = "spec/architecture.md section 10 (topology) / WORK-007"


def _vector(number: str, polarity: str, invariant: str,
            description: str, expected: ExpectedOutcome,
            execute: Callable[[ConformanceWorld], ObservedOutcome],
            tags: FrozenSet[str] = frozenset()) -> ConformanceVector:
    return ConformanceVector(
        vector_id="W032-CNF-TOP-%s" % number,
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


def _now() -> Any:
    return parse_instant(NOW)


def vectors() -> Tuple[ConformanceVector, ...]:
    out = []

    # -- TOP-001: self-advertisement becomes authoritative --------------------
    def _top001(world: ConformanceWorld) -> ObservedOutcome:
        topo = world.topology
        claim = topo.claim(
            subject=world.node_b, reporter=world.node_b,
            claim_type=ClaimType.ADVERTISES, value=_KNOWN_CAP_VALUE,
            source_class=SourceClass.SELF_ADVERTISEMENT,
        )
        outcome = topo.merge(claim)
        if not outcome.accepted:
            return ObservedOutcome(
                False, outcome.code, outcome.detail
            )
        authoritative = topo.authoritative(world.node_b, now=_now())
        if any(c.claim_id == claim.claim_id for c in authoritative):
            return ObservedOutcome(
                True, "authoritative-self-claim",
                "self-advertisement is authoritative",
            )
        return ObservedOutcome(
            False, "self-claim-not-authoritative",
            "self-advertisement missing from the authoritative set",
        )

    out.append(_vector(
        "001", "positive",
        "only self-attributed self-advertisements are authoritative",
        "A SELF_ADVERTISEMENT advertises claim merges and is returned by "
        "get_authoritative_claims.",
        ExpectedOutcome(True, frozenset({"authoritative-self-claim"})),
        _top001,
        frozenset({"positive:core-behavior"}),
    ))

    # -- TOP-002: remote claim poisoning ---------------------------------------
    def _top002(world: ConformanceWorld) -> ObservedOutcome:
        topo = world.topology
        # The attack: node A claims what node B advertises (remote reporter).
        poisoned = topo.claim(
            subject=world.node_b, reporter=world.node_a,
            claim_type=ClaimType.ADVERTISES, value=_KNOWN_CAP_VALUE,
            source_class=SourceClass.REMOTE_CLAIM,
        )
        outcome = topo.merge(poisoned)
        if not outcome.accepted:
            return ObservedOutcome(
                False, outcome.code, "remote claim merge rejected outright"
            )
        authoritative = topo.authoritative(world.node_b, now=_now())
        leaked = [c for c in authoritative if c.reporter == world.node_a]
        if leaked:
            return ObservedOutcome(
                True, "provenance-collapse",
                "remote claim became authoritative for the subject",
            )
        return ObservedOutcome(
            False, "provenance-contained",
            "remote claim recorded but never authoritative",
        )

    out.append(_vector(
        "002", "negative",
        "a remote claim never becomes the subject's authoritative claim",
        "REMOTE_CLAIM advertises from another reporter: accepted as "
        "non-authoritative evidence only (provenance containment).",
        ExpectedOutcome(False, frozenset({"provenance-contained"})),
        _top002,
        frozenset({
            "negative:topology-poisoning",
            "discriminating:provenance",
            "recovery:cross-authority-injection",
        }),
    ))

    # -- TOP-003: idempotent replay ---------------------------------------------
    def _top003(world: ConformanceWorld) -> ObservedOutcome:
        topo = world.topology
        claim = topo.claim(
            subject=world.node_b, reporter=world.node_b,
            claim_type=ClaimType.ADVERTISES, value=_KNOWN_CAP_VALUE,
            source_class=SourceClass.SELF_ADVERTISEMENT,
        )
        first = topo.merge(claim)
        second = topo.merge(claim)
        if first.accepted and second.code == "idempotent":
            return ObservedOutcome(
                True, "idempotent",
                "identical claim replay is idempotent (no new state)",
            )
        return ObservedOutcome(
            second.code == "idempotent", second.code,
            "replay outcome %s" % second.code,
        )

    out.append(_vector(
        "003", "positive",
        "exact-duplicate claim merges are idempotent",
        "Merging the identical claim twice yields the idempotent code.",
        ExpectedOutcome(True, frozenset({"idempotent"})),
        _top003,
        frozenset({"recovery:replay-state", "positive:core-behavior"}),
    ))

    # -- TOP-004: replay-stale watermark ------------------------------------------
    def _top004(world: ConformanceWorld) -> ObservedOutcome:
        topo = world.topology
        newer = topo.claim(
            subject=world.node_b, reporter=world.node_b,
            claim_type=ClaimType.ADVERTISES, value=_KNOWN_CAP_VALUE,
            source_class=SourceClass.SELF_ADVERTISEMENT, sequence=2,
        )
        older = topo.claim(
            subject=world.node_b, reporter=world.node_b,
            claim_type=ClaimType.ADVERTISES, value=_KNOWN_CAP_VALUE,
            source_class=SourceClass.SELF_ADVERTISEMENT, sequence=1,
        )
        topo.merge(newer)
        outcome = topo.merge(older)
        if outcome.code == "replay-stale":
            return ObservedOutcome(
                False, "replay-stale",
                "older sequence after newer is replay-stale",
            )
        return ObservedOutcome(
            outcome.code == "replay-stale", outcome.code,
            "stale merge outcome %s" % outcome.code,
        )

    out.append(_vector(
        "004", "negative",
        "per-key sequence watermarks reject stale replays",
        "sequence 1 after sequence 2 is rejected as replay-stale.",
        ExpectedOutcome(False, frozenset({"replay-stale"})),
        _top004,
        frozenset({"negative:replay", "recovery:replay-state"}),
    ))

    # -- TOP-005: same-sequence conflict preserved ---------------------------------
    def _top005(world: ConformanceWorld) -> ObservedOutcome:
        topo = world.topology
        subject = make_link_subject(world.node_a, world.node_b)
        first = topo.claim(
            subject=subject, reporter=world.node_a,
            claim_type=ClaimType.LINK_STATE, value="up",
            source_class=SourceClass.SELF_ADVERTISEMENT, sequence=5,
        )
        conflicting = topo.claim(
            subject=subject, reporter=world.node_a,
            claim_type=ClaimType.LINK_STATE, value="down",
            source_class=SourceClass.SELF_ADVERTISEMENT, sequence=5,
        )
        topo.merge(first)
        outcome = topo.merge(conflicting)
        if outcome.code == "conflict-preserved":
            return ObservedOutcome(
                False, "conflict-preserved",
                "same-sequence conflict preserved, no arrival-order winner",
            )
        return ObservedOutcome(
            outcome.code == "conflict-preserved", outcome.code,
            "conflict outcome %s" % outcome.code,
        )

    out.append(_vector(
        "005", "negative",
        "same-sequence conflicts are preserved (no arrival-order winner)",
        "Conflicting value at the same sequence is rejected as "
        "conflict-preserved.",
        ExpectedOutcome(False, frozenset({"conflict-preserved"})),
        _top005,
        frozenset({"recovery:version-conflict"}),
    ))

    # -- TOP-006: forged claim id ---------------------------------------------------
    def _top006(world: ConformanceWorld) -> ObservedOutcome:
        topo = world.topology
        # The attack: present structurally valid content with a forged id.
        # (Construction itself is tamper-evident: a mismatched claim_id
        # fails closed before any merge is attempted.)
        try:
            topo.claim(
                subject=world.node_b, reporter=world.node_b,
                claim_type=ClaimType.ADVERTISES, value=_KNOWN_CAP_VALUE,
                source_class=SourceClass.SELF_ADVERTISEMENT,
                claim_id="sha256:" + "f" * 64,
            )
        except TopologyError as error:
            return ObservedOutcome(
                False, "forged-claim-id-rejected",
                "%s: %s" % (getattr(error, "code", "claim-id"), error),
            )
        return ObservedOutcome(
            True, "forged-claim-id-accepted",
            "claim with mismatched content id constructed",
        )

    out.append(_vector(
        "006", "negative",
        "claim ids are content-derived; mismatched ids fail closed",
        "A claim carrying a forged claim_id is rejected at merge.",
        ExpectedOutcome(False, frozenset({"forged-claim-id-rejected"})),
        _top006,
        frozenset({"negative:forged-provenance",
                   "discriminating:provenance"}),
    ))

    # -- TOP-007: link state worst-observed convergence ------------------------------
    def _top007(world: ConformanceWorld) -> ObservedOutcome:
        topo = world.topology
        subject = make_link_subject(world.node_a, world.node_b)
        topo.merge(topo.claim(
            subject=subject, reporter=world.node_a,
            claim_type=ClaimType.LINK_STATE, value="up",
            source_class=SourceClass.SELF_ADVERTISEMENT,
        ))
        topo.merge(topo.claim(
            subject=subject, reporter=world.node_c,
            claim_type=ClaimType.LINK_STATE, value="degraded",
            source_class=SourceClass.DIRECT_OBSERVATION,
        ))
        state = topo.link_state(world.node_a, world.node_b, now=_now())
        if state == "degraded":
            return ObservedOutcome(
                True, "worst-observed",
                "link state converges to worst-observed across reporters",
            )
        return ObservedOutcome(
            state == "degraded", state,
            "unexpected link state %r" % state,
        )

    out.append(_vector(
        "007", "positive",
        "link state is the worst observation across reporters",
        "up (self) + degraded (direct observation) -> DEGRADED.",
        ExpectedOutcome(True, frozenset({"worst-observed"})),
        _top007,
        frozenset({"positive:core-behavior"}),
    ))

    # -- TOP-008: stale advertisement --------------------------------------------------
    def _top008(world: ConformanceWorld) -> ObservedOutcome:
        topo = world.topology
        topo.merge(topo.claim(
            subject=world.node_b, reporter=world.node_b,
            claim_type=ClaimType.ADVERTISES, value=_KNOWN_CAP_VALUE,
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at="2026-01-01T00:00:00Z",
            freshness_until="2026-02-01T00:00:00Z",
        ))
        state = topo.graph.get_advertisement_state(
            world.node_b, now=_now()
        )
        if state == "stale":
            return ObservedOutcome(
                False, "stale", "advertisement converged to STALE"
            )
        return ObservedOutcome(
            state == "stale", state, "unexpected state %r" % state
        )

    out.append(_vector(
        "008", "negative",
        "advertisements converge to STALE past their freshness window",
        "freshness_until in the past -> AdvertisementState.STALE.",
        ExpectedOutcome(False, frozenset({"stale"})),
        _top008,
        frozenset({"negative:expired-future-data", "recovery:stale-future"}),
    ))

    # -- TOP-009: remote identity claim cannot drive IdentityState ---------------------
    def _top009(world: ConformanceWorld) -> ObservedOutcome:
        topo = world.topology
        topo.merge(topo.claim(
            subject=world.node_c, reporter=world.node_a,
            claim_type=ClaimType.IDENTITY, value="known",
            source_class=SourceClass.REMOTE_CLAIM,
        ))
        state = topo.identity_state(world.node_c, now=_now())
        if state == "known":
            return ObservedOutcome(
                True, "remote-identity-accepted",
                "remote identity claim drove IdentityState",
            )
        return ObservedOutcome(
            False, "remote-identity-inert",
            "remote identity claim is inert; state %r" % state,
        )

    out.append(_vector(
        "009", "negative",
        "remote identity claims cannot drive IdentityState",
        "A REMOTE_CLAIM identity claim leaves the subject not-KNOWN.",
        ExpectedOutcome(False, frozenset({"remote-identity-inert"})),
        _top009,
        frozenset({"negative:topology-poisoning",
                   "recovery:cross-authority-injection"}),
    ))

    # -- TOP-010: self REMOVED claim converges -------------------------------------------
    def _top010(world: ConformanceWorld) -> ObservedOutcome:
        topo = world.topology
        topo.merge(topo.claim(
            subject=world.node_c, reporter=world.node_c,
            claim_type=ClaimType.IDENTITY, value="known",
            source_class=SourceClass.SELF_ADVERTISEMENT,
        ))
        topo.merge(topo.claim(
            subject=world.node_c, reporter=world.node_c,
            claim_type=ClaimType.IDENTITY, value="removed",
            source_class=SourceClass.SELF_ADVERTISEMENT, sequence=2,
        ))
        state = topo.identity_state(world.node_c, now=_now())
        if state == "removed":
            return ObservedOutcome(
                True, "removed-converged",
                "self REMOVED claim converges IdentityState to REMOVED",
            )
        return ObservedOutcome(
            state == "removed", state, "unexpected state %r" % state
        )

    out.append(_vector(
        "010", "positive",
        "self-attributed removal converges identity state",
        "Self REMOVED claim (higher sequence) -> IdentityState.REMOVED.",
        ExpectedOutcome(True, frozenset({"removed-converged"})),
        _top010,
        frozenset({"positive:core-behavior", "recovery:stale-future"}),
    ))

    # -- TOP-011: signed capability statement ingest (genuine) ----------------------------
    def _top011(world: ConformanceWorld) -> ObservedOutcome:
        from topology import ingest_capability_statement

        caps = world.capability
        signed = caps.sign(
            caps.statement(capability_id=_KNOWN_CAP_VALUE,
                           provider=world.node_b),
            world.identity.operational_refs[world.node_b],
        )
        outcome = ingest_capability_statement(
            world.topology.graph, signed, now=_now(),
            store=world.identity.store,
            provider=world.identity.provider,
            credential=world.identity.operational_refs[world.node_b],
        )
        if outcome.accepted:
            return ObservedOutcome(
                True, "ingest-accepted",
                "genuinely signed statement ingested as a self-claim",
            )
        return ObservedOutcome(
            False, outcome.code, outcome.detail
        )

    out.append(_vector(
        "011", "positive",
        "the W005->W007 ingest bridge accepts genuine signed statements",
        "ingest_capability_statement with a verified statement merges the "
        "self-attributed advertises claim.",
        ExpectedOutcome(True, frozenset({"ingest-accepted"})),
        _top011,
        frozenset({"positive:core-behavior", "matrix:envelope-interop"}),
    ))

    # -- TOP-012: forged signature ingest rejected ------------------------------------------
    def _top012(world: ConformanceWorld) -> ObservedOutcome:
        from topology import ingest_capability_statement

        caps = world.capability
        signed = caps.sign(
            caps.statement(capability_id=_KNOWN_CAP_VALUE,
                           provider=world.node_b),
            world.identity.operational_refs[world.node_b],
        )
        # The attack: tamper the signature (forged provenance).
        tampered = _replace(signed, signature="ff" * 4)
        try:
            outcome = ingest_capability_statement(
                world.topology.graph, tampered, now=_now(),
                store=world.identity.store,
                provider=world.identity.provider,
                credential=world.identity.operational_refs[world.node_b],
            )
        except TopologyError as error:
            code = getattr(error, "code", "ingest")
            return ObservedOutcome(False, code, str(error))
        if not outcome.accepted and outcome.code == "verification-failed":
            return ObservedOutcome(
                False, "verification-failed",
                "statement with forged signature rejected at ingest",
            )
        return ObservedOutcome(
            bool(outcome.accepted), outcome.code,
            "forged-signature ingest outcome %s" % outcome.code,
        )

    out.append(_vector(
        "012", "negative",
        "ingest verifies statement signatures (forged provenance fails)",
        "ingest_capability_statement with a tampered signature raises "
        "TopologyError and merges nothing.",
        ExpectedOutcome(False, frozenset({"ingest", "verification-failed"})),
        _top012,
        frozenset({"negative:forged-provenance",
                   "discriminating:provenance"}),
    ))

    # -- TOP-013: malformed claim rejected -----------------------------------------------------
    def _top013(world: ConformanceWorld) -> ObservedOutcome:
        try:
            world.topology.claim(
                subject="", reporter=world.node_a,
                claim_type=ClaimType.REACHABLE, value="true",
                source_class=SourceClass.DIRECT_OBSERVATION,
            )
        except TopologyError as error:
            return ObservedOutcome(
                False, getattr(error, "code", "invalid"), str(error)
            )
        return ObservedOutcome(
            True, "malformed-claim-accepted", "empty-subject claim constructed"
        )

    out.append(_vector(
        "013", "negative",
        "claims with malformed subjects fail closed at construction",
        "TopologyClaim with an empty subject raises TopologyError.",
        ExpectedOutcome(False, frozenset({"invalid", "subject",
                                          "malformed-claim-rejected"})),
        _top013,
        frozenset({"negative:malformed-required-fields"}),
    ))

    return tuple(out)


_KNOWN_CAP_VALUE = "capability.core.store-and-forward"


def _replace(obj: Any, **changes: Any) -> Any:
    import dataclasses

    return dataclasses.replace(obj, **changes)
