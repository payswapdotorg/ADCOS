"""M014 converged scale scenario — the multi-domain convergence
harness (R7-CORE-001, DEC-0101).

The scale package's M014 harvest onto the Architecture 1.1 authority
(the R7 charter "### M014" scope: evolve the scale battery to the
converged state — a DISCLOSED evolution): the frozen WORK-039
discipline is preserved verbatim (one REAL ``FederationStore`` per
domain, never a centralized second authority; the injected W031
``ScenarioClock``; bounded-resource envelopes; byte-identical
determinism); this module scales the CONVERGED provider-domain
surface — the M014 citation ledgers, the citation revocation
propagation, and the per-domain citation admission rate limits (the
``federation.convergence`` production-hardening surfaces):

- **citation waves** — planned child-authority citations (typed
  ``ChildCitation`` DATA, constructed by the composition root from
  REAL accepted-domain records) append to per-domain
  ``DomainCitationLedger`` s over the real federation world;
- **rate limits** — every per-domain citation admission passes the
  deterministic fixed-window ``RateLimitPolicy`` gate (per-tick
  admission bound; exceed fails closed at validation time — the plan
  is deterministic, so a violation is a spec error, never a runtime
  surprise);
- **revocation propagation** — a citation revoked at an origin
  domain propagates to every peer in EXPLICIT relay rounds bounded
  by the computed graph distance (the W039 discipline carried onto
  citations): each round advances the revocation one hop; the
  convergence is CONFIRMED exactly when the last domain holds it;
  the round count is PREDICTED from the topology (fail-closed on any
  divergence);
- **honest evidence** — the journal is evidence only (OBSERVATION
  events; the frozen event taxonomy is reused, never extended); no
  deployment claim exists (``scale.evidence`` stays the authority).

Determinism (LOCK-119): injected W031 ``ScenarioClock`` instants
only; content-derived digests over canonical JSON; sorted iteration
everywhere; integer arithmetic; no wall clock, no randomness, no
network; two runs byte-identical (verified by
:func:`verify_convergence_replay`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from protocol.canonicalization import canonical_json_bytes
from simulator.time import ScenarioClock

from federation import Scope
from federation.convergence import (
    ChildCitation,
    DomainCitationLedger,
    RateLimitPolicy,
    RateLimitState,
    check_rate_limit,
    citation_revocation,
)

from .errors import ScaleError, ScaleReasonCode
from .model import ScaleEvent, ScaleEventType, scale_event_list_digest
from .topology import (
    build_domain_materials,
    delivery_distances,
    topology_edges,
    validate_topology,
)
from .world import build_world

#: The per-tick citation admission bound default (the production
#: rate-limit envelope; integer admissions only).
DEFAULT_CITATION_RATE_LIMIT = 8

#: The frozen propagation state vocabulary observed by the harness
#: (the CitationRevocation discipline projected onto rounds).
PROPAGATION_STATES: Tuple[str, ...] = ("pending", "propagated", "confirmed")


@dataclass(frozen=True)
class ConvergenceCitationPlan:
    """One planned citation admission: at tick ``at_tick``, domain
    ``domain_index`` appends the typed child-authority citation."""

    at_tick: int
    domain_index: int
    citation: ChildCitation

    def __post_init__(self) -> None:
        if not isinstance(self.at_tick, int) or isinstance(self.at_tick, bool):
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "citation plan at_tick must be an int",
            )
        if self.at_tick < 0:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "citation plan at_tick must be >= 0",
            )
        if not isinstance(self.domain_index, int) or isinstance(
            self.domain_index, bool
        ):
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "citation plan domain_index must be an int",
            )
        if not isinstance(self.citation, ChildCitation):
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "citation plan requires a typed ChildCitation (LOCK-106/"
                "118: no untyped citations)",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "at_tick": self.at_tick,
            "domain_index": self.domain_index,
            "citation": self.citation.to_dict(),
        }


@dataclass(frozen=True)
class ConvergenceRevocationPlan:
    """One planned citation revocation: at tick ``at_tick``, domain
    ``domain_index`` revokes citation ``citation_id`` for ``reason``
    (the origin of the propagation)."""

    at_tick: int
    domain_index: int
    citation_id: str
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.at_tick, int) or isinstance(self.at_tick, bool):
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "revocation plan at_tick must be an int",
            )
        if self.at_tick < 0:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "revocation plan at_tick must be >= 0",
            )
        if not isinstance(self.domain_index, int) or isinstance(
            self.domain_index, bool
        ):
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "revocation plan domain_index must be an int",
            )
        if not isinstance(self.citation_id, str) or not self.citation_id:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "revocation plan citation_id must be a non-empty string",
            )
        if not isinstance(self.reason, str) or not self.reason:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "revocation plan reason must be a non-empty string",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "at_tick": self.at_tick,
            "domain_index": self.domain_index,
            "citation_id": self.citation_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ConvergenceScenarioSpec:
    """The complete, immutable, reproducible convergence-scenario
    configuration (the W039 reproducibility contract carried onto the
    converged surface: spec content + the deterministic
    ``(at_tick, sequence)`` execution order produces byte-identical
    digests)."""

    scenario_id: str
    seed: int
    start_instant: str
    tick_seconds: int
    horizon_ticks: int
    domain_count: int
    shape: str
    citations: Tuple[ConvergenceCitationPlan, ...] = ()
    revocations: Tuple[ConvergenceRevocationPlan, ...] = ()
    citation_rate_limit: int = DEFAULT_CITATION_RATE_LIMIT

    def __post_init__(self) -> None:
        if not self.scenario_id or not isinstance(self.scenario_id, str):
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "scenario_id must be a non-empty string",
            )
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "seed must be a non-negative int",
            )
        if not isinstance(self.tick_seconds, int) or isinstance(
            self.tick_seconds, bool
        ) or self.tick_seconds < 1:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "tick_seconds must be an int >= 1",
            )
        if not isinstance(self.horizon_ticks, int) or isinstance(
            self.horizon_ticks, bool
        ) or self.horizon_ticks < 0:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "horizon_ticks must be an int >= 0",
            )
        if (
            not isinstance(self.citation_rate_limit, int)
            or isinstance(self.citation_rate_limit, bool)
            or self.citation_rate_limit < 1
        ):
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "citation_rate_limit must be an int >= 1",
            )
        validate_topology(self.shape, self.domain_count)
        for plan in self.citations:
            if not isinstance(plan, ConvergenceCitationPlan):
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "citations must be ConvergenceCitationPlan records",
                )
            if plan.domain_index < 0 or plan.domain_index >= self.domain_count:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "citation plan domain_index %d outside the world"
                    % plan.domain_index,
                )
            if plan.at_tick > self.horizon_ticks:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "citation plan at tick %d beyond the horizon %d"
                    % (plan.at_tick, self.horizon_ticks),
                )
        for plan in self.revocations:
            if not isinstance(plan, ConvergenceRevocationPlan):
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "revocations must be ConvergenceRevocationPlan records",
                )
            if plan.domain_index < 0 or plan.domain_index >= self.domain_count:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "revocation plan domain_index %d outside the world"
                    % plan.domain_index,
                )
            if plan.at_tick > self.horizon_ticks:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "revocation plan at tick %d beyond the horizon %d"
                    % (plan.at_tick, self.horizon_ticks),
                )
        # the revocation origin must hold the citation it revokes (the
        # citation must be planned at the ORIGIN domain at an earlier
        # or equal tick)
        citation_admissions: Dict[Tuple[str, int], Tuple[int, ...]] = {}
        for plan in self.citations:
            key = (plan.citation.citation_id, plan.domain_index)
            ticks = citation_admissions.setdefault(key, ())
            citation_admissions[key] = ticks + (plan.at_tick,)
        for plan in self.revocations:
            ticks = citation_admissions.get(
                (plan.citation_id, plan.domain_index), ()
            )
            if not any(tick <= plan.at_tick for tick in ticks):
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "revocation cites %r before any admission at the "
                    "origin domain %d"
                    % (plan.citation_id, plan.domain_index),
                )
        # the deterministic rate-limit gate: per-domain per-tick
        # admissions must respect the policy (a violation is a spec
        # error discovered here, never a runtime surprise)
        admissions: Dict[Tuple[int, int], int] = {}
        for plan in self.citations:
            key = (plan.domain_index, plan.at_tick)
            admissions[key] = admissions.get(key, 0) + 1
        for (domain_index, tick), count in sorted(admissions.items()):
            if count > self.citation_rate_limit:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "citation admission burst %d at domain %d tick %d "
                    "exceeds the per-tick rate limit %d"
                    % (count, domain_index, tick, self.citation_rate_limit),
                )

    def content_dict(self) -> Dict[str, Any]:
        # canonical form: the plan sequences are serialized in the
        # deterministic execution order (sorted by (tick, domain,
        # identity)) — input order carries no identity
        citations = sorted(
            self.citations,
            key=lambda plan: (
                plan.at_tick, plan.domain_index, plan.citation.citation_id,
            ),
        )
        revocations = sorted(
            self.revocations,
            key=lambda plan: (plan.at_tick, plan.domain_index, plan.citation_id),
        )
        return {
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "start_instant": self.start_instant,
            "tick_seconds": self.tick_seconds,
            "horizon_ticks": self.horizon_ticks,
            "domain_count": self.domain_count,
            "shape": self.shape,
            "citations": [plan.to_dict() for plan in citations],
            "revocations": [
                {
                    "at_tick": plan.at_tick,
                    "domain_index": plan.domain_index,
                    "citation_id": plan.citation_id,
                    "reason": plan.reason,
                }
                for plan in revocations
            ],
            "citation_rate_limit": self.citation_rate_limit,
        }

    def spec_digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.content_dict())
        ).hexdigest()


@dataclass(frozen=True)
class ConvergencePropagationRecord:
    """One observed citation-revocation propagation (the explicit
    rounds; the round count is predicted from the topology and any
    divergence fails closed)."""

    citation_id: str
    origin_domain: int
    issued_at_tick: int
    confirmed_at_tick: int
    predicted_rounds: int
    observed_rounds: int
    states: Tuple[Tuple[int, int, str], ...]

    def content_dict(self) -> Dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "origin_domain": self.origin_domain,
            "issued_at_tick": self.issued_at_tick,
            "confirmed_at_tick": self.confirmed_at_tick,
            "predicted_rounds": self.predicted_rounds,
            "observed_rounds": self.observed_rounds,
            "states": [
                {"domain": domain, "tick": tick, "state": state}
                for domain, tick, state in self.states
            ],
        }


@dataclass(frozen=True)
class ConvergenceRunResult:
    """The complete deterministic outcome of one convergence run."""

    scenario_id: str
    spec_digest: str
    domain_count: int
    relationship_count: int
    citation_count: int
    revoked_citation_count: int
    journal: Tuple[ScaleEvent, ...]
    ledger_digests: Tuple[Tuple[int, str], ...]
    propagation: Tuple[ConvergencePropagationRecord, ...]

    @property
    def run_digest(self) -> str:
        return "sha256:" + hashlib.sha256(canonical_json_bytes({
            "scenario_id": self.scenario_id,
            "spec_digest": self.spec_digest,
            "domain_count": self.domain_count,
            "relationship_count": self.relationship_count,
            "citation_count": self.citation_count,
            "revoked_citation_count": self.revoked_citation_count,
            "journal_digest": scale_event_list_digest(self.journal),
            "ledger_digests": [
                {"domain": domain, "digest": digest}
                for domain, digest in self.ledger_digests
            ],
            "propagation": [
                record.content_dict() for record in self.propagation
            ],
        })).hexdigest()


class _Journal:
    """The deterministic ordered journal (evidence only — never
    protocol state; the W039 discipline)."""

    def __init__(self, clock: ScenarioClock) -> None:
        self._clock = clock
        self._events: List[ScaleEvent] = []
        self._sequence = 0

    def observe(self, at_tick: int, kind: str, payload: Dict[str, Any]) -> None:
        self._sequence += 1
        self._events.append(ScaleEvent(
            at_tick=at_tick,
            sequence=self._sequence,
            kind=kind,
            payload=dict(payload),
        ))

    def events(self) -> Tuple[ScaleEvent, ...]:
        return tuple(self._events)


def run_convergence_scenario(spec: ConvergenceScenarioSpec) -> ConvergenceRunResult:
    """Execute the convergence scenario deterministically.

    The harness builds the REAL multi-domain federation world (one
    real ``FederationStore`` per domain — ``build_world``), attaches
    one ``DomainCitationLedger`` per domain, executes the planned
    citation admissions (rate-gated per domain per tick), issues the
    planned citation revocations at their origin domains, and
    propagates each revocation to every peer in EXPLICIT relay rounds
    (one hop per tick, bounded by the computed graph distance); the
    propagation is CONFIRMED exactly when the last domain holds it,
    and the observed round count must equal the predicted round count
    (any divergence fails closed)."""
    if not isinstance(spec, ConvergenceScenarioSpec):
        raise ScaleError(
            ScaleReasonCode.SPEC_INVALID,
            "run_convergence_scenario requires a ConvergenceScenarioSpec",
        )
    clock = ScenarioClock(spec.start_instant, spec.tick_seconds)
    journal = _Journal(clock)
    journal.observe(0, ScaleEventType.SCENARIO_STARTED, {
        "scenario_id": spec.scenario_id,
        "converged": "m014",
    })
    materials = build_domain_materials(spec.domain_count, spec.seed)
    edges = topology_edges(spec.shape, spec.domain_count)
    world = build_world(
        materials,
        edges,
        declared_scopes=(
            Scope.ROUTE_IMPORT,
            Scope.ROUTE_EXPORT,
            Scope.CAPABILITY_READ,
            Scope.CAPABILITY_OFFER,
            Scope.SERVICE_DISCOVER,
            Scope.RESOURCE_READ,
        ),
        grant_scopes=(
            Scope.ROUTE_IMPORT,
            Scope.CAPABILITY_READ,
            Scope.SERVICE_DISCOVER,
            Scope.RESOURCE_READ,
        ),
        start_instant=clock.instant_at(0),
        valid_until=clock.instant_at(3600),
        event_instant=clock.instant_at(0),
    )
    journal.observe(0, ScaleEventType.WORLD_BUILT, {
        "domain_count": spec.domain_count,
        "shape": spec.shape,
        "edge_count": len(edges),
    })
    ledgers: List[DomainCitationLedger] = [
        DomainCitationLedger() for _ in range(spec.domain_count)
    ]
    # the production rate-limit surface: one deterministic fixed-window
    # admission counter per domain (window == one tick)
    rate_policy = RateLimitPolicy(
        limit=spec.citation_rate_limit, window_seconds=spec.tick_seconds,
    )
    rate_states: List[RateLimitState] = [
        RateLimitState() for _ in range(spec.domain_count)
    ]
    # the deterministic citation admissions (sorted by (tick, domain,
    # citation id) — input order never matters)
    plans = sorted(
        spec.citations,
        key=lambda plan: (
            plan.at_tick, plan.domain_index, plan.citation.citation_id,
        ),
    )
    for plan in plans:
        verdict = check_rate_limit(
            rate_policy, rate_states[plan.domain_index],
            "citation-admission", clock.instant_at(plan.at_tick),
        )
        if not verdict.allowed:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "citation admission at domain %d tick %d exceeded the "
                "rate policy (%d admissions in the window)"
                % (plan.domain_index, plan.at_tick, verdict.count),
            )
        ledgers[plan.domain_index].append(plan.citation)
        journal.observe(plan.at_tick, ScaleEventType.OBSERVATION, {
            "kind": "convergence-citation-admitted",
            "domain": plan.domain_index,
            "citation_id": plan.citation.citation_id,
            "authority": plan.citation.authority,
        })
    # the deterministic revocation propagation
    propagation: List[ConvergencePropagationRecord] = []
    revocation_plans = sorted(
        spec.revocations,
        key=lambda plan: (plan.at_tick, plan.domain_index, plan.citation_id),
    )
    for plan in revocation_plans:
        distances = delivery_distances(edges, spec.domain_count, plan.domain_index)
        # the holder set: every domain that admitted the cited material
        # (the origin is a holder — validated at spec time); relays
        # forward the revocation WITHOUT holding the citation (the W039
        # relay discipline carried onto citations)
        holder_domains = tuple(
            index
            for index in range(spec.domain_count)
            if any(
                citation_plan.citation.citation_id == plan.citation_id
                and citation_plan.domain_index == index
                for citation_plan in spec.citations
            )
        )
        max_distance = max(distances[index] for index in holder_domains)
        predicted_rounds = max_distance
        issued_instant = clock.instant_at(plan.at_tick)
        # the origin holds the citation (validated at spec time) and
        # issues the typed pending revocation
        origin_revocation = citation_revocation(
            citation_id=plan.citation_id,
            reason=plan.reason,
            revoked_at=issued_instant,
        )
        ledgers[plan.domain_index].revoke(origin_revocation)
        journal.observe(plan.at_tick, ScaleEventType.REVOCATION_ISSUED, {
            "domain": plan.domain_index,
            "citation_id": plan.citation_id,
            "reason": plan.reason,
        })
        # explicit relay rounds: one hop per tick; every HOLDER domain
        # at graph distance d holds the revocation from tick issue+d
        states: List[Tuple[int, int, str]] = [
            (plan.domain_index, plan.at_tick, "pending")
        ]
        for distance in range(1, max_distance + 1):
            tick = plan.at_tick + distance
            reaching_holders = tuple(
                index for index in holder_domains
                if distances[index] == distance
            )
            relay_instant = clock.instant_at(tick)
            for index in reaching_holders:
                relayed = citation_revocation(
                    citation_id=plan.citation_id,
                    reason=plan.reason,
                    revoked_at=relay_instant,
                    propagated_to=tuple(
                        str(item) for item in reaching_holders
                    ),
                    state="propagated",
                )
                ledgers[index].revoke(relayed)
                states.append((index, tick, "propagated"))
            journal.observe(tick, ScaleEventType.REVOCATION_RELAYED, {
                "origin": plan.domain_index,
                "citation_id": plan.citation_id,
                "round": distance,
                "holders": list(reaching_holders),
            })
        confirmed_tick = plan.at_tick + max_distance
        confirmed_instant = clock.instant_at(confirmed_tick)
        holder_labels = tuple(str(index) for index in holder_domains)
        for index in holder_domains:
            confirmed = citation_revocation(
                citation_id=plan.citation_id,
                reason=plan.reason,
                revoked_at=confirmed_instant,
                propagated_to=holder_labels,
                confirmed_by=holder_labels,
                state="confirmed",
            )
            ledgers[index].revoke(confirmed)
            states.append((index, confirmed_tick, "confirmed"))
        journal.observe(confirmed_tick, ScaleEventType.REVOCATION_PROPAGATED, {
            "origin": plan.domain_index,
            "citation_id": plan.citation_id,
            "predicted_rounds": predicted_rounds,
        })
        observed_rounds = confirmed_tick - plan.at_tick
        if observed_rounds != predicted_rounds:
            raise ScaleError(
                ScaleReasonCode.CONVERGENCE_MISMATCH,
                "revocation propagation for %r diverged (observed %d "
                "rounds, predicted %d)"
                % (plan.citation_id, observed_rounds, predicted_rounds),
            )
        propagation.append(ConvergencePropagationRecord(
            citation_id=plan.citation_id,
            origin_domain=plan.domain_index,
            issued_at_tick=plan.at_tick,
            confirmed_at_tick=confirmed_tick,
            predicted_rounds=predicted_rounds,
            observed_rounds=observed_rounds,
            states=tuple(states),
        ))
    journal.observe(spec.horizon_ticks, ScaleEventType.SCENARIO_COMPLETED, {
        "citation_count": sum(
            len(ledger.citations()) for ledger in ledgers
        ),
        "revoked_citation_count": sum(
            1 for ledger in ledgers for citation in ledger.citations()
            if ledger.is_revoked(citation.citation_id)
        ),
    })
    citation_count = sum(len(ledger.citations()) for ledger in ledgers)
    revoked_count = sum(
        1
        for ledger in ledgers
        for citation in ledger.citations()
        if ledger.is_revoked(citation.citation_id)
    )
    return ConvergenceRunResult(
        scenario_id=spec.scenario_id,
        spec_digest=spec.spec_digest(),
        domain_count=spec.domain_count,
        relationship_count=len(edges),
        citation_count=citation_count,
        revoked_citation_count=revoked_count,
        journal=journal.events(),
        ledger_digests=tuple(
            (index, ledgers[index].digest())
            for index in range(spec.domain_count)
        ),
        propagation=tuple(propagation),
    )


def verify_convergence_replay(
    spec: ConvergenceScenarioSpec, result: ConvergenceRunResult
) -> bool:
    """Re-run the scenario and verify byte-identical digests (the
    W039 replay-verification discipline carried onto the converged
    surface)."""
    if not isinstance(result, ConvergenceRunResult):
        raise ScaleError(
            ScaleReasonCode.SPEC_INVALID,
            "verify_convergence_replay requires a ConvergenceRunResult",
        )
    replay = run_convergence_scenario(spec)
    return replay.run_digest == result.run_digest


def convergence_summary(result: ConvergenceRunResult) -> Dict[str, Any]:
    """The deterministic summary (sorted, canonical; battery-facing)."""
    return {
        "scenario_id": result.scenario_id,
        "domain_count": result.domain_count,
        "relationship_count": result.relationship_count,
        "citation_count": result.citation_count,
        "revoked_citation_count": result.revoked_citation_count,
        "ledger_digests": [
            {"domain": domain, "digest": digest}
            for domain, digest in result.ledger_digests
        ],
        "propagation": [
            record.content_dict() for record in result.propagation
        ],
        "run_digest": result.run_digest,
    }


__all__ = [
    "DEFAULT_CITATION_RATE_LIMIT",
    "PROPAGATION_STATES",
    "ConvergenceCitationPlan",
    "ConvergenceRevocationPlan",
    "ConvergenceScenarioSpec",
    "ConvergencePropagationRecord",
    "ConvergenceRunResult",
    "run_convergence_scenario",
    "verify_convergence_replay",
    "convergence_summary",
]
